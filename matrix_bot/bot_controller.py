"""Contrôleur principal du bot Werewolf."""

import asyncio
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime

from nio import AsyncClient, InviteMemberEvent

from matrix_bot.matrix_client import MatrixClientWrapper
from matrix_bot.room_manager import RoomManager
from matrix_bot.scheduler import GameScheduler, wait_until_sunday_noon
from matrix_bot.message_handler import MessageHandler
from matrix_bot.notifications import NotificationManager
from matrix_bot.integration_test import IntegrationTester

from game.game_manager import GameManager
from game.leaderboard import LeaderboardManager
from commands.command_handler import CommandHandler
from models.enums import GamePhase, Team, RoleType
from models.player import Player
from utils.message_distortion import MessageDistorter

logger = logging.getLogger(__name__)


class WerewolfBot:
    """Bot Matrix pour gérer une partie de Loup-Garou."""
    
    def __init__(
        self,
        homeserver: str,
        user_id: str,
        access_token: str,
        space_id: str,
        lobby_room_id: str,
        password: str = None,
        test_user_id: str = None,
        test_user_password: str = None,
        test_user_token: str = None,
        test_user2_id: str = None,
        test_user2_password: str = None,
        test_user2_token: str = None,
        runtests: bool = False
    ):
        # Configuration
        self.homeserver = homeserver
        self.user_id = user_id
        self.space_id = space_id
        self.lobby_room_id = lobby_room_id
        
        # Configuration des comptes de test
        self._test_user_id = test_user_id
        self._test_user_password = test_user_password
        self._test_user_token = test_user_token
        self._test_user2_id = test_user2_id
        self._test_user2_password = test_user2_password
        self._test_user2_token = test_user2_token
        self.runtests = runtests
        # Composants
        self.client = MatrixClientWrapper(homeserver, user_id, access_token, password=password)
        self.room_manager = RoomManager(self.client, space_id)
        
        # Horaires depuis le .env (ou valeurs par défaut)
        from datetime import time as dtime
        self._night_hour = int(os.getenv('NIGHT_START_HOUR', '21'))
        self._day_hour = int(os.getenv('DAY_START_HOUR', '8'))
        self._vote_hour = int(os.getenv('VOTE_START_HOUR', '19'))
        self._max_days = int(os.getenv('GAME_MAX_DURATION_DAYS', '7'))
        
        self.scheduler = GameScheduler(
            night_start=dtime(self._night_hour, 0),
            day_start=dtime(self._day_hour, 0),
            vote_start=dtime(self._vote_hour, 0),
            max_days=self._max_days,
        )
        self.message_handler: Optional[MessageHandler] = None
        self.notification_manager: Optional[NotificationManager] = None
        self.message_distorter = MessageDistorter()
        
        # Configuration
        self.distort_little_girl_messages = os.getenv('LITTLE_GIRL_DISTORT_MESSAGES', 'true').lower() == 'true'
        self.mentaliste_advance_hours = float(os.getenv('MENTALISTE_ADVANCE_HOURS', '2'))
        
        # Jeu
        self.game_manager = GameManager()
        self.command_handler = CommandHandler(self.game_manager)
        self.leaderboard_manager = LeaderboardManager(self.game_manager.db)
        
        # Lier les callbacks Matrix au game manager
        # NOTE: Les méthodes _remove_wolf_from_room et _mute_player sont async,
        # mais le game_manager les appelle depuis du code sync.
        # On wrappe avec ensure_future pour que les coroutines s'exécutent réellement.
        self.game_manager.on_remove_wolf_from_room = lambda uid: asyncio.ensure_future(self._remove_wolf_from_room(uid))
        self.game_manager.on_mute_player = lambda uid: asyncio.ensure_future(self._mute_player(uid))
        
        # État
        self.registered_players: Dict[str, str] = {}  # matrix_id -> display_name
        self._accepting_registrations = True
        self._wolves_in_room: set = set()  # user_ids des loups dans le salon
        self._sorciere_notified = False  # Si la Sorcière a été notifiée du wolf target
        self._wolf_votes_locked = False  # True quand tous les loups ont voté (vote verrouillé)
        self.running = False
    
    async def start(self):
        """Démarre le bot."""
        logger.info("Démarrage du bot Werewolf...")
        
        # Connexion à Matrix
        connected = await self.client.connect()
        if not connected:
            logger.critical("❌ Impossible de se connecter à Matrix. Arrêt du bot.")
            return
        logger.info("Connecté à Matrix")
        
        # Vérifier les permissions
        perms_ok = await self.client.verify_permissions(self.lobby_room_id, self.space_id)
        if not perms_ok:
            logger.warning("⚠️ Des permissions sont manquantes. Le bot continue mais peut rencontrer des erreurs.")
        
        # Auto-accepter toutes les invitations (DMs des joueurs, etc.)
        self.client.client.add_event_callback(self._on_invite, InviteMemberEvent)
        logger.info("✅ Auto-accept des invitations activé")
        
        # Tests d'intégration au premier lancement (BDD vide)
        if self.game_manager.db.is_first_run() and self.runtests:
            await self._run_integration_tests()
        
        # Initialiser les handlers
        self.message_handler = MessageHandler(self.client.client, self.user_id)
        self.message_handler.on_command = self._handle_command
        self.message_handler.on_registration = self._handle_registration
        self.message_handler.on_wolf_message = self._handle_wolf_message
        self.message_handler.on_village_message = self._handle_village_message
        
        self.notification_manager = NotificationManager(self.room_manager)
        
        # Message de bienvenue dans le lobby (horaires dynamiques depuis .env)
        await self.client.send_message(
            self.lobby_room_id,
            f"🐺 **Bot Loup-Garou démarré !**\n\n"
            f"Tapez `/inscription` pour participer à la prochaine partie.\n"
            f"La partie démarrera **Dimanche à midi**.\n\n"
            f"📋 Règles:\n"
            f"• 1 jour IRL = 1 jour + 1 nuit de jeu\n"
            f"• Nuit: {self._night_hour}h → {self._day_hour}h\n"
            f"• Jour: {self._day_hour}h → {self._vote_hour}h\n"
            f"• Vote: {self._vote_hour}h → {self._night_hour}h\n"
            f"• Durée max: {self._max_days} jours",
            formatted=True
        )
        
        self.running = True
        
        # Lancer le sync Matrix en arrière-plan pour recevoir les événements
        # (messages, invitations, etc.)
        self._sync_task = asyncio.create_task(
            self.client.client.sync_forever(timeout=30000, full_state=True)
        )
        logger.info("✅ Sync Matrix démarré en arrière-plan")
        
        # Boucle principale
        await self._run_game_loop()
    
    async def stop(self):
        """Arrête le bot."""
        logger.info("Arrêt du bot...")
        self.running = False
        self.scheduler.stop()
        
        # Arrêter la tâche de sync
        if hasattr(self, '_sync_task') and self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        
        await self.client.disconnect()
    
    async def _run_integration_tests(self):
        """Exécute les tests d'intégration au premier lancement."""
        if not self._test_user_id or not self._test_user_token:
            logger.warning(
                "⚠️ Premier lancement détecté mais MATRIX_TESTUSER_ID / "
                "MATRIX_TESTUSER_TOKEN non configurés. Tests d'intégration ignorés."
            )
            return
        if not self._test_user2_id or not self._test_user2_token:
            logger.warning(
                "⚠️ MATRIX_TESTUSER2_ID / MATRIX_TESTUSER2_TOKEN non configurés. "
                "Tests d'intégration ignorés."
            )
            return

        logger.info("🧪 Premier lancement détecté — exécution des tests d'intégration...")
        tester = IntegrationTester(
            bot_client=self.client,
            space_id=self.space_id,
            lobby_room_id=self.lobby_room_id,
            test_user_id=self._test_user_id,
            test_user_token=self._test_user_token,
            test_user2_id=self._test_user2_id,
            test_user2_token=self._test_user2_token,
            homeserver=self.homeserver,
        )
        success = await tester.run_all()
        if success:
            logger.info("🎉 Tests d'intégration réussis — le bot est opérationnel.")
        else:
            logger.error(
                "⛔ Certains tests d'intégration ont échoué. "
                "Le bot démarre quand même mais des fonctionnalités peuvent être cassées."
            )

    async def _run_game_loop(self):
        """Boucle principale du jeu."""
        try:
            while self.running:
                # Attendre le Dimanche midi
                logger.info("En attente du prochain Dimanche midi...")
                await self._wait_for_game_start()
                
                if not self.running:
                    break
                
                # Démarrer une partie
                await self._start_game()
                
                # Lancer le scheduler
                self.scheduler.start_game(datetime.now())
                self.scheduler.on_night_start = self._on_night_start
                self.scheduler.on_day_start = self._on_day_start
                self.scheduler.on_vote_start = self._on_vote_start
                
                # Exécuter le scheduler
                await self.scheduler.run()
                
                # Fin de partie
                await self._end_game()
                
                # Nettoyer pour la prochaine
                self.registered_players.clear()
                
        except Exception as e:
            logger.error(f"Erreur dans la boucle de jeu: {e}")
            raise
    
    async def _wait_for_game_start(self):
        """Attend le Dimanche midi en gérant les inscriptions."""
        # Créer une tâche pour attendre dimanche
        wait_task = asyncio.create_task(wait_until_sunday_noon())
        
        # Pendant ce temps, gérer les inscriptions
        while not wait_task.done():
            await asyncio.sleep(60)  # Check toutes les minutes
            
            # Afficher le nombre d'inscrits régulièrement
            if len(self.registered_players) > 0:
                logger.info(f"{len(self.registered_players)} joueur(s) inscrit(s)")
        
        await wait_task
    
    async def _start_game(self):
        """Démarre une nouvelle partie."""
        logger.info(f"Démarrage de la partie avec {len(self.registered_players)} joueurs")
        
        if len(self.registered_players) < 5:
            await self.client.send_message(
                self.lobby_room_id,
                "❌ Pas assez de joueurs inscrits (minimum 5). "
                "Partie annulée, réinscrivez-vous pour la semaine prochaine.",
                formatted=True
            )
            return
        
        # Créer les joueurs
        player_ids = list(self.registered_players.keys())
        
        # Démarrer le jeu
        result = self.game_manager.start_game(player_ids)
        if not result.get("success"):
            await self.client.send_message(
                self.lobby_room_id,
                f"❌ Impossible de lancer la partie : {result.get('message', 'erreur inconnue')}",
                formatted=True
            )
            return
        
        # Annoncer dans le lobby que la partie démarre
        await self.client.send_message(
            self.lobby_room_id,
            "🎮 **La partie commence !** Les salons de jeu ont été créés.\n"
            "Rendez-vous dans le salon **Village** pour jouer.\n\n"
            "Les inscriptions sont fermées jusqu'à la fin de la partie.",
            formatted=True
        )
        # Bloquer les nouvelles inscriptions
        self._accepting_registrations = False
        
        # Créer les salons de jeu
        await self.room_manager.create_all_rooms(player_ids)
        
        # Configurer le message_handler pour écouter le village
        if self.message_handler:
            self.message_handler.village_room_id = self.room_manager.village_room
        
        # Annoncer dans le village avec la liste des rôles
        roles_message = self._build_roles_announcement()
        await self.room_manager.send_to_village(roles_message)
        
        # Créer salons spéciaux (loups uniquement — le couple sera créé après la 1ère nuit)
        await self._create_special_rooms()
        
        # Envoyer les rôles en DM
        await self._send_role_notifications()
    
    async def _create_special_rooms(self):
        """Crée les salons spéciaux (loups seulement au départ)."""
        # Salon des loups
        wolf_players = [
            p for p in self.game_manager.players.values()
            if p.role.can_vote_with_wolves()
        ]
        
        if wolf_players:
            wolf_ids = [p.user_id for p in wolf_players]
            wolves_room_id = await self.room_manager.create_wolves_room(wolf_ids)
            
            # Configurer le message_handler pour écouter le salon des loups
            if wolves_room_id and self.message_handler:
                self.message_handler.wolves_room_id = wolves_room_id
        
        # Le salon du couple sera créé après la résolution de la première nuit
        # (quand Cupidon aura désigné les amoureux et que les deux sont vivants)
    
    async def _create_couple_room_if_needed(self):
        """Crée le salon du couple si Cupidon a marié deux joueurs et qu'ils sont tous les deux vivants."""
        if self.room_manager.couple_room:
            return  # Déjà créé
        
        # Trouver les amoureux vivants
        lovers = [
            p for p in self.game_manager.players.values()
            if p.lover and p.is_alive and p.lover.is_alive
        ]
        
        if len(lovers) == 2:
            lover_ids = [p.user_id for p in lovers]
            await self.room_manager.create_couple_room(lover_ids)
            
            # Notifier le couple
            if self.notification_manager:
                await self.notification_manager.send_couple_notification(
                    lovers[0].user_id, lovers[1].user_id
                )
    
    async def _send_role_notifications(self):
        """Envoie les informations de rôle à chaque joueur via DM Matrix depuis le bot."""
        for player in self.game_manager.players.values():
            await self.notification_manager.send_role_assignment(
                player.user_id,
                player.role
            )
    
    def _build_roles_announcement(self) -> str:
        """Construit l'annonce des rôles en jeu au début de la partie."""
        summary = self.game_manager.get_roles_summary()
        nb_players = len(self.game_manager.players)
        
        message = "🎮 **La partie commence !**\n\n"
        message += f"👥 **{nb_players} joueurs** participent.\n\n"
        message += "📋 **Rôles en jeu :**\n\n"
        
        for rt, info in sorted(summary.items(), key=lambda x: x[0].value):
            team = info['team']
            if team == Team.MECHANT:
                emoji = "🐺"
            elif team == Team.GENTIL:
                emoji = "🏘️"
            elif team == Team.COUPLE:
                emoji = "💕"
            else:
                emoji = "❓"
            
            message += f"{emoji} **{info['name']}** ×{info['count']}\n"
            message += f"   _{info['description']}_\n\n"
        
        message += f"🌙 La première nuit commence à **{self._night_hour}h00**.\n"
        message += "Consultez vos **messages privés** (DM du bot) pour découvrir votre rôle."
        
        return message
    
    async def _on_night_start(self, phase: GamePhase):
        """Appelé au début de chaque nuit (21h).
        
        Résout d'abord le vote du village (si on était en phase VOTE),
        puis démarre la nuit.
        """
        logger.info("🌙 Début de la nuit")
        
        # ── 1. Résoudre le vote du village (VOTE → NIGHT) ──
        if self.game_manager.phase == GamePhase.VOTE:
            vote_result = self.game_manager.end_vote_phase()
            
            eliminated = vote_result.get("eliminated")
            all_deaths = vote_result.get("all_deaths", [])
            if eliminated:
                await self.room_manager.send_to_village(
                    f"🗳️ **Résultat du vote :** **{eliminated.display_name}** "
                    f"a été éliminé par le village !\n"
                    f"Son rôle était : _{eliminated.role.name}_"
                )
                # Ajouter au cimetière
                await self.room_manager.add_to_dead(eliminated.user_id)
                
                # Annoncer les morts d'amoureux
                for dead in all_deaths:
                    if dead != eliminated:
                        await self.room_manager.send_to_village(
                            f"💔 **{dead.display_name}** meurt de chagrin (amoureux/se) !\n"
                            f"Son rôle était : _{dead.role.name}_"
                        )
                        await self.room_manager.add_to_dead(dead.user_id)
            else:
                await self.room_manager.send_to_village(
                    "🗳️ **Résultat du vote :** Pas d'élimination "
                    "(égalité ou aucun vote)."
                )
            
            # Vérifier victoire après le vote
            if vote_result.get("winner"):
                await self._announce_victory(vote_result["winner"])
                self.scheduler.stop()
                return
        
        # ── 2. Démarrer la nuit ──
        self.game_manager.set_phase(GamePhase.NIGHT)
        
        await self.room_manager.send_to_village(
            "🌙 **La nuit tombe sur le village...**\n\n"
            "Tout le monde s'endort. Les rôles nocturnes peuvent agir.\n"
            "Les loups-garous se réveillent pour choisir leur victime."
        )
        
        # Rappeler les actions nocturnes
        for player in self.game_manager.players.values():
            if player.is_alive:
                await self.notification_manager.send_night_reminder(
                    player.user_id,
                    player.role
                )
    
    async def _on_day_start(self, phase: GamePhase):
        """Appelé au début de chaque jour."""
        logger.info("☀️ Début du jour")
        
        self.game_manager.set_phase(GamePhase.NIGHT)  # Remettre en NIGHT pour resolve_night
        
        # Résolution de la nuit
        results = self.game_manager.resolve_night()
        
        # Après la première nuit, créer le salon du couple si nécessaire
        await self._create_couple_room_if_needed()
        
        # Gérer la conversion Loup Noir
        if results.get('converted'):
            await self._handle_conversion(results['converted'])
        
        # Annoncer les morts
        message = "☀️ **Le jour se lève sur le village...**\n\n"
        
        if results['deaths']:
            message += "💀 Cette nuit, les victimes sont:\n"
            for player_id in results['deaths']:
                player = self.game_manager.get_player(player_id)
                if player:
                    message += f"• **{player.display_name}** — _{player.role.name}_\n"
                    # Ajouter au cimetière
                    await self.room_manager.add_to_dead(player_id)
        else:
            message += "🎉 Personne n'est mort cette nuit !\n"
        
        # Montreur d'ours
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role and 
                player.role.role_type == RoleType.MONTREUR_OURS):
                if player.role.check_for_wolves(self.game_manager):
                    message += "\n🐻 **L'ours du montreur d'ours grogne !** Un loup est assis à côté de lui...\n"
        
        message += "\n💬 Les villageois peuvent discuter jusqu'à 19h."
        
        await self.room_manager.send_to_village(message)
        
        # Réinitialiser le flag sorcière
        self._sorciere_notified = False
        self._wolf_votes_locked = False
        
        # Vérifier victoire
        if results.get('winner'):
            await self._announce_victory(results['winner'])
            self.scheduler.stop()
        else:
            await self._check_victory()
    
    async def _handle_conversion(self, converted_user_id: str):
        """Gère l'ajout d'un joueur converti au salon des loups."""
        player = self.game_manager.get_player(converted_user_id)
        if not player:
            return
        
        logger.info(f"🐺 {player.display_name} a été converti en loup-garou par le Loup Noir")
        
        # Ajouter au salon des loups
        if self.room_manager.wolves_room:
            try:
                await self.client.invite_user(self.room_manager.wolves_room, converted_user_id)
                self._wolves_in_room.add(converted_user_id)
                
                # Notifier le joueur converti
                await self.client.send_dm(
                    converted_user_id,
                    "🐺 **Vous avez été infecté par le Loup Noir !**\n\n"
                    "Vous êtes désormais un **Loup-Garou**. Vous rejoignez la meute.\n"
                    "Votez avec les loups chaque nuit dans le salon des loups."
                )
                
                # Notifier les loups
                await self.client.send_message(
                    self.room_manager.wolves_room,
                    f"🐺 **{player.display_name}** a été converti et rejoint la meute !",
                    formatted=True
                )
            except Exception as e:
                logger.error(f"Erreur lors de l'ajout du converti au salon des loups: {e}")
    
    async def _notify_mentaliste(self):
        """Envoie la prédiction du Mentaliste sur l'issue du vote en cours."""
        # Trouver le mentaliste vivant
        mentaliste = None
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role and 
                player.role.role_type == RoleType.MENTALISTE):
                mentaliste = player
                break
        
        if not mentaliste:
            return
        
        # Récupérer le joueur le plus voté actuellement
        most_voted = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=False)
        
        if not most_voted:
            await self.client.send_dm(
                mentaliste.user_id,
                "🔮 **Intuition du Mentaliste**\n\n"
                "Personne n'a encore reçu de votes... Impossible de prédire l'issue."
            )
            return
        
        # Prédire l'issue
        outcome = mentaliste.role.predict_vote_outcome(self.game_manager, most_voted)
        
        if outcome == "positif":
            emoji = "✅"
            description = "**positif** — le joueur le plus voté est du côté des loups."
        elif outcome == "négatif":
            emoji = "❌"
            description = "**négatif** — le joueur le plus voté est du côté du village."
        else:
            emoji = "⚖️"
            description = "**neutre** — impossible de déterminer."
        
        hours_text = f"{self.mentaliste_advance_hours:.0f}h" if self.mentaliste_advance_hours == int(self.mentaliste_advance_hours) else f"{self.mentaliste_advance_hours}h"
        
        await self.client.send_dm(
            mentaliste.user_id,
            f"🔮 **Intuition du Mentaliste** ({hours_text} avant la fin du vote)\n\n"
            f"{emoji} Le vote semble être {description}\n\n"
            f"💡 Cette information est basée sur les votes actuels — le résultat peut encore changer."
        )
        
        logger.info(f"Mentaliste notifié: issue du vote = {outcome}")
    
    async def _notify_sorciere_wolf_target(self):
        """Notifie la Sorcière de la cible des loups (appelé après le vote des loups).
        
        La Sorcière doit toujours recevoir cette information, même si le Garde
        protège la cible. Elle ne sait pas ce que fait le Garde.
        """
        if self._sorciere_notified:
            return
        
        # Trouver la sorcière vivante
        sorciere = None
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role and 
                player.role.role_type.value == 'SORCIERE'):
                sorciere = player
                break
        
        if not sorciere:
            return
        
        # Récupérer la cible des loups depuis le vote manager
        wolf_target = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=True)
        if not wolf_target:
            await self.client.send_dm(
                sorciere.user_id,
                "🌙 **Les loups n'ont pas choisi de victime cette nuit.**\n\n"
                "Vous pouvez tout de même utiliser votre potion de mort si vous le souhaitez.\n"
                "• `/sorciere-tue {pseudo}` — Empoisonner quelqu'un"
            )
        else:
            msg = (
                f"🌙 **Les loups ont choisi de dévorer** **{wolf_target.display_name}** **cette nuit.**\n\n"
            )
            if sorciere.role.has_life_potion:
                msg += f"• `/sorciere-sauve {wolf_target.pseudo}` — Utiliser votre potion de vie pour le/la sauver\n"
            else:
                msg += "• _(Potion de vie déjà utilisée)_\n"
            
            if sorciere.role.has_death_potion:
                msg += "• `/sorciere-tue {pseudo}` — Utiliser votre potion de mort\n"
            else:
                msg += "• _(Potion de mort déjà utilisée)_\n"
            
            msg += "\n💡 Vous pouvez utiliser les deux potions la même nuit."
            
            await self.client.send_dm(sorciere.user_id, msg)
        
        self._sorciere_notified = True
    
    async def _on_vote_start(self, phase: GamePhase):
        """Appelé au début de la phase de vote."""
        logger.info("🗳️ Début des votes")
        
        # start_vote_phase() reset les votes du village et met la phase à VOTE
        self.game_manager.start_vote_phase()
        
        await self.room_manager.send_to_village(
            "🗳️ **Phase de vote !**\n\n"
            "Les villageois doivent voter pour éliminer un suspect.\n"
            "Utilisez `/vote {pseudo}` pour voter.\n\n"
            "⏰ Vous avez jusqu'à **21h00**."
        )
        
        # Planifier la notification du Mentaliste X heures avant la fin du vote (21h)
        asyncio.create_task(self._schedule_mentaliste_notification())
    
    async def _schedule_mentaliste_notification(self):
        """Envoie la prédiction du Mentaliste X heures avant la fin du vote."""
        from datetime import datetime, time as dt_time, timedelta
        
        # Fin du vote = 21h (début de la nuit)
        vote_end = datetime.combine(datetime.now().date(), self.scheduler.night_start)
        if vote_end < datetime.now():
            vote_end += timedelta(days=1)
        
        # Moment de notification = vote_end - MENTALISTE_ADVANCE_HOURS
        notify_time = vote_end - timedelta(hours=self.mentaliste_advance_hours)
        wait_seconds = (notify_time - datetime.now()).total_seconds()
        
        if wait_seconds > 0:
            logger.info(f"Mentaliste: notification dans {wait_seconds:.0f}s ({self.mentaliste_advance_hours}h avant fin du vote)")
            await asyncio.sleep(wait_seconds)
        
        # Vérifier qu'on est toujours en phase de vote
        if self.game_manager.phase != GamePhase.VOTE:
            return
        
        await self._notify_mentaliste()
    
    async def _end_game(self):
        """Termine la partie et nettoie les salons."""
        logger.info("Fin de la partie")
        
        self.game_manager.set_phase(GamePhase.ENDED)
        
        # Supprimer tous les salons de jeu (village, loups, couple, cimetière)
        await self.room_manager.cleanup_rooms()
        
        # Réouvrir les inscriptions dans le lobby
        self._accepting_registrations = True
        
        # Message dans le lobby
        await self.client.send_message(
            self.lobby_room_id,
            "🎮 **Partie terminée !**\n\n"
            "Les salons de jeu ont été supprimés.\n"
            "Tapez `/inscription` pour participer à la prochaine partie Dimanche prochain.",
            formatted=True
        )
    
    async def _check_victory(self):
        """Vérifie si une équipe a gagné."""
        winner = self.game_manager.check_victory()
        
        if winner:
            await self._announce_victory(winner)
            self.scheduler.stop()
    
    async def _announce_victory(self, winner: Team):
        """Annonce la victoire."""
        team_names = {
            Team.GENTIL: "🏘️ **Les Villageois**",
            Team.MECHANT: "🐺 **Les Loups-Garous**",
        }
        
        # Loup Blanc solo ou égalité
        if winner == Team.NEUTRE:
            living = self.game_manager.get_living_players()
            if living and living[0].role and living[0].role.role_type.value == "LOUP_BLANC":
                team_display = "🐺⚪ **Le Loup Blanc**"
            else:
                team_display = "☠️ **Personne** (égalité)"
        elif winner == Team.COUPLE:
            cupidon = self.game_manager.get_cupidon_player()
            if cupidon:
                team_display = "💕 **Le Couple + Cupidon**"
            else:
                team_display = "💕 **Le Couple**"
        else:
            team_display = team_names.get(winner, winner.value)
        
        message = f"🎉 **Partie terminée !**\n\n{team_display} a gagné !\n\n"
        
        # Révéler tous les rôles
        message += "📋 **Rôles:**\n"
        for player in self.game_manager.players.values():
            status = "💀" if not player.is_alive else "✅"
            message += f"{status} **{player.display_name}**: {player.role.name}\n"
        
        await self.room_manager.send_to_village(message)
    
    async def _handle_registration(self, room_id: str, user_id: str):
        """Gère l'inscription d'un joueur."""
        if room_id != self.lobby_room_id:
            return
        
        if not self._accepting_registrations:
            await self.client.send_message(
                room_id,
                "❌ Les inscriptions sont fermées, une partie est en cours.\n"
                "Réessayez après la fin de la partie.",
                formatted=True
            )
            return
        
        if user_id in self.registered_players:
            await self.client.send_message(
                room_id,
                f"✅ {user_id} est déjà inscrit !",
                formatted=True
            )
            return
        
        # Récupérer le nom d'affichage
        display_name = self.message_handler.extract_user_id(user_id)
        
        self.registered_players[user_id] = display_name
        logger.info(f"Nouveau joueur inscrit: {display_name}")
        
        await self.client.send_message(
            room_id,
            f"✅ **{display_name}** est inscrit !\n"
            f"Total: **{len(self.registered_players)}** joueur(s)",
            formatted=True
        )
    
    async def _handle_command(
        self,
        room_id: str,
        user_id: str,
        command: str,
        args: list
    ) -> dict:
        """Gère une commande de jeu avec validation du contexte (salon + rôle)."""
        # Commandes de leaderboard (accessibles à tous, partout)
        if command == 'leaderboard' or command == 'top':
            message = self.leaderboard_manager.get_leaderboard_message()
            await self.client.send_message(room_id, message, formatted=True)
            return {'success': True}
        
        if command == 'stats':
            if args:
                target_id = args[0]
                message = self.leaderboard_manager.get_player_stats_message(target_id, target_id)
            else:
                pseudo = self.message_handler.extract_user_id(user_id)
                message = self.leaderboard_manager.get_player_stats_message(user_id, pseudo)
            await self.client.send_message(room_id, message, formatted=True)
            return {'success': True}
        
        if command == 'roles':
            message = self.leaderboard_manager.get_role_stats_message()
            await self.client.send_message(room_id, message, formatted=True)
            return {'success': True}
        
        # Vérifier que le joueur est dans la partie
        if user_id not in self.game_manager.players:
            return {'success': False, 'error': 'Vous ne participez pas à cette partie'}
        
        player = self.game_manager.players[user_id]
        
        # ── Validation du contexte salon/commande ──
        is_village = self.room_manager.is_village_room(room_id)
        is_wolves = self.room_manager.is_wolves_room(room_id)
        is_dm = self.room_manager.is_dm_room(room_id)
        
        # Commandes de vote : contexte obligatoire
        if command == 'vote':
            if self.game_manager.phase == GamePhase.NIGHT and is_wolves:
                # Vote loup → dans le salon des loups uniquement
                # Vérifier si les votes sont verrouillés
                if self._wolf_votes_locked:
                    await self.client.send_message(
                        room_id,
                        "❌ Les votes sont **verrouillés**. Tous les loups ont déjà voté.",
                        formatted=True
                    )
                    return {'success': False, 'error': 'Votes verrouillés'}
                # OK, sera traité par command_handler
            elif self.game_manager.phase == GamePhase.VOTE and is_village:
                # Vote village → dans le salon du village uniquement
                pass  # OK
            elif self.game_manager.phase == GamePhase.NIGHT and not is_wolves:
                await self.client.send_dm(
                    user_id,
                    "❌ Utilisez `/vote` dans le **salon des loups** pour voter la nuit."
                )
                return {'success': False, 'error': 'Mauvais salon'}
            elif self.game_manager.phase == GamePhase.VOTE and not is_village:
                await self.client.send_dm(
                    user_id,
                    "❌ Utilisez `/vote` dans le **salon du village** pour voter."
                )
                return {'success': False, 'error': 'Mauvais salon'}
            else:
                await self.client.send_dm(user_id, "❌ Ce n'est pas le moment de voter.")
                return {'success': False, 'error': 'Phase incorrecte'}
        
        # Dictateur : commande de JOUR uniquement, en DM
        if command == 'dictateur':
            if not is_dm:
                await self.client.send_dm(
                    user_id,
                    "❌ La commande **/dictateur** doit être utilisée en **message privé** avec le bot."
                )
                return {'success': False, 'error': 'Commande privée uniquement'}
            if self.game_manager.phase != GamePhase.DAY and self.game_manager.phase != GamePhase.VOTE:
                await self.client.send_dm(user_id, "❌ Le Dictateur ne peut agir que **pendant le jour**.")
                return {'success': False, 'error': 'Phase incorrecte'}
        
        # Commandes nocturnes privées : uniquement en DM, la nuit
        night_dm_commands = [
            'voyante', 'sorciere-sauve', 'sorciere-tue', 'garde', 'cupidon',
            'medium', 'enfant', 'corbeau', 'curse', 'tuer',
            'voleur-tirer', 'voleur-choisir', 'voleur-echange', 'lg',
            'convertir'
        ]
        if command in night_dm_commands:
            if not is_dm:
                await self.client.send_dm(
                    user_id,
                    f"❌ La commande **/{command}** doit être utilisée en **message privé** avec le bot."
                )
                return {'success': False, 'error': 'Commande privée uniquement'}
            if self.game_manager.phase != GamePhase.NIGHT:
                # Exception pour le chasseur (peut tirer de jour aussi)
                if command != 'tuer' or not player.role or player.role.role_type.value != 'CHASSEUR':
                    await self.client.send_dm(user_id, "❌ Cette commande n'est utilisable que **la nuit**.")
                    return {'success': False, 'error': 'Phase incorrecte'}
        
        # Exécuter la commande via execute_command (passe les args bruts)
        try:
            result = self.command_handler.execute_command(
                user_id=user_id,
                command=command,
                args=args
            )
            
            # Envoyer confirmation au joueur en DM
            if result['success']:
                msg = result.get('message', f"Commande **/{command}** exécutée avec succès")
                await self.client.send_dm(user_id, f"✅ {msg}")
            else:
                await self.client.send_dm(
                    user_id,
                    f"❌ Erreur: {result.get('message', 'Commande invalide')}"
                )
            
            # Après un vote loup réussi, vérifier si tous les loups ont voté
            # pour notifier la Sorcière de la cible
            if (result['success'] and command == 'vote' 
                and self.game_manager.phase == GamePhase.NIGHT):
                await self._check_wolf_vote_complete()
            
            return result
        
        except Exception as e:
            logger.error(f"Erreur commande {command}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _check_wolf_vote_complete(self):
        """Vérifie si tous les loups ont voté et notifie la Sorcière le cas échéant.
        
        Quand tous les loups ont voté :
        - Les votes sont verrouillés (plus de changement possible)
        - La Sorcière est notifiée de la cible (gain de temps)
        """
        # Compter les loups vivants
        living_wolves = [
            p for p in self.game_manager.players.values()
            if p.is_alive and p.role and p.role.can_vote_with_wolves()
        ]
        
        # Vérifier si tous ont voté
        wolf_votes = self.game_manager.vote_manager.wolf_votes
        wolves_who_voted = [w for w in living_wolves if w.user_id in wolf_votes]
        
        if len(wolves_who_voted) >= len(living_wolves) and living_wolves:
            # Verrouiller les votes
            self._wolf_votes_locked = True
            
            # Notifier les loups que le vote est acquérit
            target = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=True)
            if target and self.room_manager.wolves_room:
                await self.client.send_message(
                    self.room_manager.wolves_room,
                    f"🔒 **Vote verrouillé !** La meute a décidé de dévorer **{target.display_name}** cette nuit.",
                    formatted=True
                )
            
            # Notifier la Sorcière
            await self._notify_sorciere_wolf_target()
    
    async def _remove_wolf_from_room(self, user_id: str):
        """Retire un loup mort du salon des loups."""
        if self.room_manager.wolves_room:
            try:
                await self.client.kick_user(self.room_manager.wolves_room, user_id)
                logger.info(f"Loup {user_id} retiré du salon des loups")
            except Exception as e:
                logger.error(f"Erreur lors du retrait du loup: {e}")
    
    async def _mute_player(self, user_id: str):
        """Mute un joueur mort dans le village et l'expulse du couple et des loups.
        
        Un joueur mort :
        - NE PEUT PLUS PARLER au village (power level -1)
        - Est EXPULSÉ du salon des loups (s'il y était)
        - Est EXPULSÉ du salon du couple (s'il y était)
        - Est ajouté au cimetière (géré par _on_day_start)
        - Peut toujours LIRE les messages du village
        """
        # 1. Muter dans le village (ne peut plus envoyer de messages)
        if self.room_manager.village_room:
            try:
                await self.client.set_power_level(
                    self.room_manager.village_room, user_id, -1
                )
                logger.info(f"☠️ {user_id} muté dans le village (power level -1)")
            except Exception as e:
                logger.error(f"Erreur mute village pour {user_id}: {e}")
        
        # 2. Expulser du salon des loups (s'il y est)
        if self.room_manager.wolves_room:
            try:
                members = await self.client.get_room_members(self.room_manager.wolves_room)
                if user_id in members:
                    await self.client.kick_user(
                        self.room_manager.wolves_room, user_id,
                        "Vous êtes mort. 💀"
                    )
                    logger.info(f"☠️ {user_id} expulsé du salon des loups")
            except Exception as e:
                logger.error(f"Erreur expulsion loups pour {user_id}: {e}")
        
        # 3. Expulser du salon du couple (s'il y est)
        if self.room_manager.couple_room:
            try:
                members = await self.client.get_room_members(self.room_manager.couple_room)
                if user_id in members:
                    await self.client.kick_user(
                        self.room_manager.couple_room, user_id,
                        "Vous êtes mort. 💀"
                    )
                    logger.info(f"☠️ {user_id} expulsé du salon du couple")
            except Exception as e:
                logger.error(f"Erreur expulsion couple pour {user_id}: {e}")
    
    async def _on_invite(self, room, event):
        """Auto-accepte toutes les invitations reçues par le bot.
        
        Permet aux joueurs d'envoyer des commandes en DM au bot.
        """
        # Ne traiter que les invitations destinées au bot
        if event.state_key != self.user_id:
            return
        if event.membership != "invite":
            return
        
        try:
            await self.client.client.join(room.room_id)
            logger.info(f"✅ Invitation acceptée : {room.room_id} (invité par {event.sender})")
        except Exception as e:
            logger.error(f"❌ Impossible d'accepter l'invitation pour {room.room_id}: {e}")
    
    async def _handle_wolf_message(self, message: str, sender: str):
        """Gère un message envoyé dans le salon des loups pour le transmettre à la Petite Fille."""
        # Vérifier que le jeu est en cours et que c'est la nuit
        if self.game_manager.phase != GamePhase.NIGHT:
            return
        
        # Trouver la Petite Fille
        little_girl = None
        for player in self.game_manager.players.values():
            if player.role.name == "Petite Fille" and player.is_alive:
                little_girl = player
                break
        
        # Si pas de Petite Fille vivante, ne rien faire
        if not little_girl:
            return
        
        try:
            # Préparer le message (avec ou sans distorsion)
            if self.distort_little_girl_messages:
                formatted_message = self.message_distorter.format_wolf_message_for_little_girl(
                    message,
                    distort=True
                )
            else:
                formatted_message = self.message_distorter.format_wolf_message_for_little_girl(
                    message,
                    distort=False
                )
            
            # Envoyer en DM à la Petite Fille
            await self.client.send_dm(little_girl.user_id, formatted_message)
            logger.debug(f"Message des loups transmis à la Petite Fille (distorsion: {self.distort_little_girl_messages})")
            
        except Exception as e:
            logger.error(f"Erreur lors de la transmission à la Petite Fille: {e}")
    
    async def _handle_village_message(self, message: str, sender: str):
        """Gère un message envoyé dans le salon du village.
        
        Vérifie si le Loup Bavard a dit son mot imposé.
        """
        # Ne vérifier que pendant le jour / vote
        if self.game_manager.phase not in (GamePhase.DAY, GamePhase.VOTE):
            return
        
        player = self.game_manager.get_player(sender)
        if not player or not player.is_alive:
            return
        
        # Vérifier si c'est le Loup Bavard
        if player.role and player.role.role_type == RoleType.LOUP_BAVARD:
            if player.role.check_message_for_word(message):
                logger.debug(f"Loup Bavard {player.pseudo} a dit le mot imposé !")

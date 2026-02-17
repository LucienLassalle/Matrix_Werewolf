"""Contrôleur principal du bot Werewolf.

La logique est répartie en trois fichiers via des mixins :
- bot_controller.py  : cycle de vie, boucle de jeu, commandes, UI
- phase_handlers.py  : transitions de phase (nuit → jour → vote)
- role_handlers.py   : événements liés aux rôles spéciaux
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from nio import AsyncClient, InviteMemberEvent

from matrix_bot.matrix_client import MatrixClientWrapper
from matrix_bot.room_manager import RoomManager
from matrix_bot.scheduler import GameScheduler, wait_until_new_game, day_name_fr
from matrix_bot.message_handler import MessageHandler
from matrix_bot.notifications import NotificationManager
from matrix_bot.integration_test import IntegrationTester
from matrix_bot.phase_handlers import PhaseHandlersMixin
from matrix_bot.role_handlers import RoleHandlersMixin
from matrix_bot.ui_builders import UIBuildersMixin
from matrix_bot.command_router import CommandRouterMixin

from game.game_manager import GameManager
from game.leaderboard import LeaderboardManager
from commands.command_handler import CommandHandler
from models.enums import GamePhase, Team, RoleType
from models.player import Player
from utils.message_distortion import MessageDistorter

logger = logging.getLogger(__name__)


class WerewolfBot(PhaseHandlersMixin, RoleHandlersMixin, UIBuildersMixin, CommandRouterMixin):
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
        # Préfixe de commande (lu une seule fois depuis .env)
        self.command_prefix = os.getenv('COMMAND_PREFIX', '!')
        
        # Composants
        self.client = MatrixClientWrapper(homeserver, user_id, access_token, password=password)
        self.room_manager = RoomManager(self.client, space_id, command_prefix=self.command_prefix)
        
        # Horaires depuis le .env (ou valeurs par défaut)
        from datetime import time as dtime
        self._night_hour = int(os.getenv('NIGHT_START_HOUR', '21'))
        self._day_hour = int(os.getenv('DAY_START_HOUR', '8'))
        self._vote_hour = int(os.getenv('VOTE_START_HOUR', '19'))
        self._max_days = int(os.getenv('GAME_MAX_DURATION_DAYS', '7'))
        self._game_start_day = int(os.getenv('GAME_START_DAY', '6'))   # 0=Lundi … 6=Dimanche
        self._game_start_hour = int(os.getenv('GAME_START_HOUR', '12'))
        
        # Le scheduler lit lui-même le .env pour ses horaires
        self.scheduler = GameScheduler()
        self.message_handler: Optional[MessageHandler] = None
        self.notification_manager: Optional[NotificationManager] = None
        self.message_distorter = MessageDistorter()
        
        # Configuration
        self.distort_little_girl_messages = os.getenv('LITTLE_GIRL_DISTORT_MESSAGES', 'true').lower() == 'true'
        self.mentaliste_advance_hours = float(os.getenv('MENTALISTE_ADVANCE_HOURS', '2'))
        self._cupidon_wins_with_couple = os.getenv('CUPIDON_WINS_WITH_COUPLE', 'true').lower() == 'true'
        
        # Jeu
        self.game_manager = GameManager()
        self.game_manager.cupidon_wins_with_couple = self._cupidon_wins_with_couple
        self.command_handler = CommandHandler(self.game_manager, command_prefix=self.command_prefix)
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
        self._mayor_succession_task: Optional[asyncio.Task] = None  # Timeout succession maire
        self._vote_reminder_task: Optional[asyncio.Task] = None  # Rappels de vote
        self._chasseur_timeout_tasks: Dict[str, asyncio.Task] = {}  # Timeout tir du chasseur (user_id → task)
        self._last_vote_snapshot: Dict[str, str] = {}  # Snapshot des votes pour détecter les changements
        self._game_events: List[str] = []  # Historique des événements pour le récap de fin
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
        self.message_handler = MessageHandler(self.client.client, self.user_id, command_prefix=self.command_prefix)
        self.message_handler.on_command = self._handle_command
        self.message_handler.on_registration = self._handle_registration
        self.message_handler.on_wolf_message = self._handle_wolf_message
        self.message_handler.on_village_message = self._handle_village_message
        
        self.notification_manager = NotificationManager(self.room_manager, command_prefix=self.command_prefix)
        
        # Restaurer les inscriptions depuis la BDD (crash-safe)
        saved_registrations = self.game_manager.db.load_registrations()
        if saved_registrations:
            self.registered_players.update(saved_registrations)
            logger.info(f"♻️ {len(saved_registrations)} inscription(s) restaurée(s) depuis la BDD")
        
        # Détecter si une partie était en cours (crash mid-game)
        if self.game_manager.db.has_active_game():
            logger.warning(
                "⚠️ Une partie était en cours avant le crash/redémarrage. "
                "L'état mid-game ne peut pas être restauré. "
                "Nettoyage de l'ancien état..."
            )
            self.game_manager.db.clear_current_game()
            await self.client.send_message(
                self.lobby_room_id,
                "⚠️ **Le bot a redémarré** — la partie précédente n'a pas pu être "
                "récupérée.\n\n"
                f"Tapez `{self.command_prefix}inscription` pour vous réinscrire à la prochaine partie.",
                formatted=True
            )
        
        # Message de bienvenue dans le lobby (horaires dynamiques depuis .env)
        jour = day_name_fr(self._game_start_day)
        welcome_msg = (
            f"🐺 **Bot Loup-Garou démarré !**\n\n"
            f"Tapez `{self.command_prefix}inscription` pour participer à la prochaine partie.\n"
            f"La partie démarrera **{jour} à {self._game_start_hour}h**.\n\n"
            f"📋 Règles:\n"
            f"• 1 jour IRL = 1 jour + 1 nuit de jeu\n"
            f"• Nuit: {self._night_hour}h → {self._day_hour}h\n"
            f"• Jour: {self._day_hour}h → {self._vote_hour}h\n"
            f"• Vote: {self._vote_hour}h → {self._night_hour}h\n"
            f"• Durée max: {self._max_days} jours"
        )
        if self.registered_players:
            names = ", ".join(self.registered_players.values())
            welcome_msg += (
                f"\n\n♻️ **{len(self.registered_players)}** inscription(s) restaurée(s) : "
                f"{names}"
            )
        await self.client.send_message(
            self.lobby_room_id,
            welcome_msg,
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
                # Attendre le prochain lancement de partie
                jour = day_name_fr(self._game_start_day)
                logger.info(f"En attente du prochain {jour} {self._game_start_hour}h...")
                await self._wait_for_game_start()
                
                if not self.running:
                    break
                
                # Démarrer une partie
                game_started = await self._start_game()
                
                if not game_started:
                    # Pas assez de joueurs ou erreur → nettoyer et recommencer
                    self.registered_players.clear()
                    self.game_manager.db.clear_registrations()
                    continue
                
                # Lancer le scheduler
                self.scheduler.start_game(datetime.now())
                self.scheduler.on_night_start = self._on_night_start
                self.scheduler.on_day_start = self._on_day_start
                self.scheduler.on_vote_start = self._on_vote_start
                
                logger.info(
                    "Scheduler configuré — Nuit: %sh, Jour: %sh, Vote: %sh, "
                    "Phase actuelle: %s",
                    self._night_hour, self._day_hour, self._vote_hour,
                    self.game_manager.phase.value,
                )
                
                # Exécuter le scheduler
                await self.scheduler.run()
                
                logger.info("Scheduler terminé — fin de partie")
                
                # Fin de partie
                await self._end_game()
                
                # Nettoyer pour la prochaine
                self.registered_players.clear()
                self._game_events.clear()
                self._wolves_in_room.clear()
                self.game_manager.reset()
                
        except Exception as e:
            logger.error(f"Erreur dans la boucle de jeu: {e}")
            raise
    
    async def _wait_for_game_start(self):
        """Attend le prochain jour/heure configuré dans le .env en gérant les inscriptions.

        Le bot vérifie toutes les 30 secondes :
        - Si un fichier sentinelle ``force_start.signal`` existe → lancement immédiat.
        - Si des inscriptions ont été ajoutées/retirées en BDD via ``admin_cli.py``
          → synchronisation automatique de ``self.registered_players``.
        """
        signal_path = Path(os.getenv("FORCE_START_SIGNAL", "force_start.signal"))

        # Créer une tâche pour attendre le prochain lancement
        wait_task = asyncio.create_task(
            wait_until_new_game(self._game_start_day, self._game_start_hour)
        )

        # Pendant ce temps, gérer les inscriptions et surveiller le signal
        while not wait_task.done():
            await asyncio.sleep(30)  # Check toutes les 30 secondes

            # Vérifier le signal de force-start
            if signal_path.exists():
                logger.info("🚀 Signal force-start détecté — lancement immédiat !")
                try:
                    signal_path.unlink()
                except OSError:
                    pass
                wait_task.cancel()
                try:
                    await wait_task
                except asyncio.CancelledError:
                    pass
                break

            # Synchroniser les inscriptions depuis la BDD
            # (couvre les ajouts/retraits faits via admin_cli.py)
            db_regs = self.game_manager.db.load_registrations()
            if db_regs != self.registered_players:
                added = set(db_regs) - set(self.registered_players)
                removed = set(self.registered_players) - set(db_regs)
                self.registered_players = dict(db_regs)
                if added:
                    logger.info(
                        f"📥 Inscription(s) ajoutée(s) via admin : "
                        f"{', '.join(db_regs[uid] for uid in added)}"
                    )
                if removed:
                    logger.info(
                        f"📤 Inscription(s) retirée(s) via admin : "
                        f"{', '.join(str(uid) for uid in removed)}"
                    )

            # Log périodique
            if len(self.registered_players) > 0:
                logger.info(f"{len(self.registered_players)} joueur(s) inscrit(s)")

        await asyncio.gather(wait_task, return_exceptions=True)
    
    async def _start_game(self) -> bool:
        """Démarre une nouvelle partie.
        
        Returns:
            True si la partie a bien démarré, False sinon.
        """
        # Synchroniser les inscriptions depuis la BDD
        # (inclut les ajouts/retraits faits via admin_cli.py)
        db_regs = self.game_manager.db.load_registrations()
        if db_regs:
            self.registered_players = dict(db_regs)

        logger.info(f"Démarrage de la partie avec {len(self.registered_players)} joueurs")
        
        if len(self.registered_players) < 5:
            await self.client.send_message(
                self.lobby_room_id,
                "❌ Pas assez de joueurs inscrits (minimum 5). "
                "Partie annulée, réinscrivez-vous pour la semaine prochaine.",
                formatted=True
            )
            return False
        
        # Créer les joueurs avec leurs display_names enregistrés
        for uid, display_name in self.registered_players.items():
            if uid not in self.game_manager.players:
                self.game_manager.add_player(display_name, uid)
                # Mettre aussi le display_name (peut différer du pseudo)
                player = self.game_manager.players[uid]
                player.display_name = display_name
        
        player_ids = list(self.registered_players.keys())
        
        # Démarrer le jeu (mode bot : pas de nuit immédiate)
        # player_ids=None car les joueurs sont déjà ajoutés ci-dessus
        result = self.game_manager.start_game(immediate_night=False)
        if not result.get("success"):
            await self.client.send_message(
                self.lobby_room_id,
                f"❌ Impossible de lancer la partie : {result.get('message', 'erreur inconnue')}",
                formatted=True
            )
            return False
        
        # Réinitialiser les événements
        self._game_events = []
        
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
        
        # Vider les inscriptions de la BDD (elles sont désormais dans game_manager.players)
        self.game_manager.db.clear_registrations()
        
        # Créer les salons de jeu
        await self.room_manager.create_all_rooms(player_ids)
        
        # Configurer le message_handler pour écouter le village
        if self.message_handler:
            self.message_handler.village_room_id = self.room_manager.village_room
        
        # Annoncer dans le village avec la liste des rôles
        roles_message = self._build_roles_announcement()
        await self.room_manager.send_to_village(roles_message)

        # Annoncer l'ordre d'assise (cercle) — utile pour le Montreur d'Ours
        seating_message = self._build_seating_message()
        await self.room_manager.send_to_village(seating_message)
        
        # Créer salons spéciaux (loups uniquement — le couple sera créé après la 1ère nuit)
        await self._create_special_rooms()
        
        # Envoyer les rôles en DM
        await self._send_role_notifications()
        
        return True
    
    async def _create_special_rooms(self):
        """Crée les salons spéciaux (loups seulement au départ)."""
        # Salon des loups
        wolf_players = [
            p for p in self.game_manager.players.values()
            if p.role and p.role.can_vote_with_wolves()
        ]
        
        if wolf_players:
            wolf_ids = [p.user_id for p in wolf_players]
            wolves_room_id = await self.room_manager.create_wolves_room(wolf_ids)
            
            # Suivre les loups présents dans le salon
            self._wolves_in_room = set(wolf_ids)
            
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
            
            # Notifier le couple (avec le pseudo et rôle du partenaire)
            if self.notification_manager:
                await self.notification_manager.send_couple_notification(
                    lovers[0], lovers[1]
                )
    
    async def _send_role_notifications(self):
        """Envoie les informations de rôle à chaque joueur via DM Matrix depuis le bot."""
        for player in self.game_manager.players.values():
            await self.notification_manager.send_role_assignment(
                player.user_id,
                player.role
            )

        # Envoyer la cible au Mercenaire en DM
        for player in self.game_manager.players.values():
            if (player.role
                    and player.role.role_type == RoleType.MERCENAIRE
                    and getattr(player, 'target', None)):
                await self.notification_manager.send_mercenaire_target(
                    player.user_id,
                    player.target.pseudo
                )
    
    # ── Mute / Cleanup ────────────────────────────────────────────────

    async def _remove_wolf_from_room(self, user_id: str):
        """Passe un loup mort en lecture seule dans le salon des loups.

        Mode spectateur : le loup mort peut toujours LIRE les messages
        mais ne peut plus ÉCRIRE (power level -1).
        """
        if self.room_manager.wolves_room:
            try:
                await self.client.set_power_level(
                    self.room_manager.wolves_room, user_id, -1
                )
                self._wolves_in_room.discard(user_id)
                logger.info(f"🐺☠️ {user_id} en lecture seule dans le salon des loups (spectateur)")
            except Exception as e:
                logger.error(f"Erreur lors du passage en lecture seule du loup: {e}")

    async def _mute_player(self, user_id: str):
        """Mute un joueur mort : lecture seule partout, muté dans le couple.
        
        Mode spectateur — un joueur mort :
        - NE PEUT PLUS PARLER au village (power level -1) → peut LIRE
        - NE PEUT PLUS PARLER dans le salon des loups (power level -1) → peut LIRE
        - NE PEUT PLUS PARLER dans le salon du couple (power level -1) → peut LIRE
        - Est INVITÉ au Cimetière pour discuter avec les autres morts
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
        
        # 2. Muter dans le salon des loups (spectateur : lecture seule)
        if self.room_manager.wolves_room and user_id in self._wolves_in_room:
            try:
                await self.client.set_power_level(
                    self.room_manager.wolves_room, user_id, -1
                )
                self._wolves_in_room.discard(user_id)
                logger.info(f"☠️ {user_id} muté dans le salon des loups (spectateur)")
            except Exception as e:
                logger.error(f"Erreur mute loups pour {user_id}: {e}")
        
        # 3. Muter dans le salon du couple (spectateur : lecture seule)
        if self.room_manager.couple_room:
            try:
                members = await self.client.get_room_members(self.room_manager.couple_room)
                if user_id in members:
                    await self.client.set_power_level(
                        self.room_manager.couple_room, user_id, -1
                    )
                    logger.info(f"☠️ {user_id} muté dans le salon du couple (spectateur)")
            except Exception as e:
                logger.error(f"Erreur mute couple pour {user_id}: {e}")
        
        # 4. Inviter au cimetière
        try:
            await self.room_manager.add_to_dead(user_id)
            logger.info(f"☠️ {user_id} invité au cimetière")
        except Exception as e:
            logger.error(f"Erreur invitation cimetière pour {user_id}: {e}")
    
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
            if (player.role and player.role.role_type == RoleType.PETITE_FILLE
                    and player.is_alive):
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

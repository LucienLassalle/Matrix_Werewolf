"""Mixin pour le routage des commandes et l'inscription.

Contient la validation du contexte (salon, phase, rôle) et le
dispatch vers command_handler, ainsi que le flow d'inscription.
"""

import asyncio
import logging
from typing import Dict, TYPE_CHECKING

from models.enums import GamePhase, RoleType

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class CommandRouterMixin:
    """Mixin gérant l'inscription et le routage des commandes."""

    def _track_journal_event(self: 'WerewolfBot', command: str, args: list,
                             result: dict, player):
        """Enregistre un événement dans le journal de fin de partie.

        Appelé après chaque commande réussie pour tracer les actions
        secrètes (voyante, sorcière, garde…) qui seront révélées
        dans la chronologie de fin de partie.
        """
        night = self.game_manager.night_count
        day = self.game_manager.day_count
        name = player.display_name

        # Résoudre la cible depuis les args
        target_name = None
        if args:
            t = self.game_manager.get_player_by_pseudo(args[0])
            if t:
                target_name = t.display_name

        if command == 'cupidon' and len(args) >= 2:
            t1 = self.game_manager.get_player_by_pseudo(args[0])
            t2 = self.game_manager.get_player_by_pseudo(args[1])
            if t1 and t2:
                self._game_events.append(
                    f"Nuit {night} — 💕 **Cupidon** lie "
                    f"**{t1.display_name}** et **{t2.display_name}**"
                )

        elif command == 'enfant' and target_name:
            self._game_events.append(
                f"Nuit {night} — 🧒 **L'Enfant Sauvage** choisit "
                f"**{target_name}** comme mentor"
            )

        elif command == 'sorciere-sauve' and target_name:
            self._game_events.append(
                f"Nuit {night} — 🧪 **La Sorcière** utilise la potion "
                f"de vie sur **{target_name}**"
            )

        elif command == 'sorciere-tue' and target_name:
            self._game_events.append(
                f"Nuit {night} — ☠️ **La Sorcière** empoisonne "
                f"**{target_name}**"
            )

        elif command == 'garde' and target_name:
            self._game_events.append(
                f"Nuit {night} — 🛡️ **Le Garde** protège "
                f"**{target_name}**"
            )

        elif command == 'voyante' and target_name:
            role_info = result.get('role')
            aura_info = result.get('aura')
            if role_info:
                self._game_events.append(
                    f"Nuit {night} — 🔮 **La Voyante** observe "
                    f"**{target_name}** → {role_info}"
                )
            elif aura_info:
                self._game_events.append(
                    f"Nuit {night} — 🔮 **La Voyante d'Aura** observe "
                    f"**{target_name}** → {aura_info}"
                )

        elif command == 'corbeau' and target_name:
            self._game_events.append(
                f"Nuit {night} — 🐦 **Le Corbeau** maudit "
                f"**{target_name}** (+2 votes)"
            )

        elif command == 'medium' and target_name:
            self._game_events.append(
                f"Nuit {night} — 👻 **Le Médium** consulte "
                f"l'esprit de **{target_name}**"
            )

        elif command == 'detective' and len(args) >= 2:
            t1 = self.game_manager.get_player_by_pseudo(args[0])
            t2 = self.game_manager.get_player_by_pseudo(args[1])
            if t1 and t2:
                self._game_events.append(
                    f"Nuit {night} — 🕵️ **Le Détective** interroge "
                    f"**{t1.display_name}** et **{t2.display_name}**"
                )

        elif command == 'voleur-echange' and target_name:
            new_role = result.get('new_role')
            role_label = new_role.name if new_role else '?'
            self._game_events.append(
                f"Nuit {night} — 🎭 **Le Voleur** échange son rôle "
                f"avec **{target_name}** → {role_label}"
            )

        elif command == 'voleur-choisir':
            new_role = result.get('new_role')
            role_label = new_role.name if new_role else '?'
            self._game_events.append(
                f"Nuit {night} — 🎭 **Le Voleur** choisit le rôle "
                f"**{role_label}**"
            )

        elif command == 'lg':
            self._game_events.append(
                f"Nuit {night} — 🐺 **{name}** (Loup Voyant) "
                f"rejoint la meute"
            )

        elif command == 'convertir':
            self._game_events.append(
                f"Nuit {night} — 🐺 **Le Loup Noir** active la conversion"
            )

        elif command == 'dictateur':
            if result.get('armed'):
                self._game_events.append(
                    f"Nuit {night} — ⚔️ **Le Dictateur {name}** prend le pouvoir"
                )
            elif target_name:
                pass  # Déjà tracé dans _process_command_deaths

        elif command == 'tuer' and target_name:
            # Loup Blanc kill (Chasseur tracé dans _process_command_deaths)
            if (player.role and
                    player.role.role_type == RoleType.LOUP_BLANC):
                self._game_events.append(
                    f"Nuit {night} — 🐺⚪ **Le Loup Blanc** élimine "
                    f"**{target_name}**"
                )

        elif command == 'assassin' and target_name:
            self._game_events.append(
                f"Nuit {night} — 🗡️ **L'Assassin** vise "
                f"**{target_name}**"
            )

        elif command == 'pyromane' and target_name:
            self._game_events.append(
                f"Nuit {night} — 🔥 **Le Pyromane** asperge "
                f"**{target_name}**"
            )

        elif command == 'pyromane-brule':
            self._game_events.append(
                f"Nuit {night} — 🔥 **Le Pyromane** embrase ses cibles"
            )

        elif command == 'geolier' and target_name:
            self._game_events.append(
                f"Jour {day} — 🔒 **Le Geôlier** choisit "
                f"**{target_name}** comme prisonnier"
            )

        elif command == 'maire':
            new_mayor = result.get('new_mayor')
            if new_mayor:
                self._game_events.append(
                    f"👑 **{name}** désigne "
                    f"**{new_mayor.display_name}** comme nouveau maire"
                )

    async def _handle_registration(self: 'WerewolfBot', room_id: str, user_id: str):
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

        # Persister l'inscription en BDD (crash-safe)
        self.game_manager.db.save_registration(user_id, display_name)

        logger.info(f"Nouveau joueur inscrit: {display_name}")

        await self.client.send_message(
            room_id,
            f"✅ **{display_name}** est inscrit !\n"
            f"Total: **{len(self.registered_players)}** joueur(s)",
            formatted=True
        )

    async def _handle_command(
        self: 'WerewolfBot',
        room_id: str,
        user_id: str,
        command: str,
        args: list,
        event_id: str = None
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
            is_village_or_wolves = (
                self.room_manager.is_village_room(room_id)
                or self.room_manager.is_wolves_room(room_id)
            )
            if is_village_or_wolves:
                await self.client.send_message(
                    room_id,
                    "📌 Consultez le **message épinglé** dans le salon du village "
                    "pour voir les rôles en jeu.",
                    formatted=True
                )
                return {'success': True}
            # Lobby ou DM : afficher tous les rôles disponibles du bot
            message = self._build_roles_list_message()
            await self.client.send_message(room_id, message, formatted=True)
            return {'success': True}

        if command == 'votes':
            if self.game_manager.phase != GamePhase.VOTE:
                await self.client.send_message(
                    room_id,
                    "❌ Ce n'est pas la phase de vote.",
                    formatted=True
                )
                return {'success': False, 'error': 'Phase incorrecte'}
            if not self.room_manager.is_village_room(room_id):
                await self.client.send_message(
                    room_id,
                    f"❌ Utilisez `{self.command_prefix}votes` dans le **salon du village**.",
                    formatted=True
                )
                return {'success': False, 'error': 'Mauvais salon'}
            summary = self.game_manager.vote_manager.get_vote_summary()
            await self.client.send_message(
                room_id,
                f"📊 **Votes en cours :**\n\n{summary}",
                formatted=True
            )
            return {'success': True}

        if command == 'votes-maire':
            if not self.game_manager.can_vote_mayor():
                await self.client.send_message(
                    room_id,
                    "❌ L'élection du maire n'est pas en cours.",
                    formatted=True
                )
                return {'success': False, 'error': 'Élection non disponible'}
            if not self.room_manager.is_village_room(room_id):
                await self.client.send_message(
                    room_id,
                    f"❌ Utilisez `{self.command_prefix}votes-maire` dans le **salon du village**.",
                    formatted=True
                )
                return {'success': False, 'error': 'Mauvais salon'}
            summary = self.game_manager.vote_manager.get_mayor_vote_summary()
            await self.client.send_message(
                room_id,
                f"👑 **Votes pour le maire :**\n\n{summary}",
                formatted=True
            )
            return {'success': True}

        # Commande aide — liste de toutes les commandes
        if command == 'help' or command == 'aide':
            message = self._build_help_message()
            await self.client.send_message(room_id, message, formatted=True)
            return {'success': True}

        # Commande statut — état actuel de la partie
        if command == 'statut':
            message = self._build_statut_message()
            await self.client.send_message(room_id, message, formatted=True)
            return {'success': True}

        # Commande joueurs — liste des joueurs
        if command == 'joueurs':
            message = self._build_joueurs_message()
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
                if self._wolf_votes_locked:
                    await self.client.send_message(
                        room_id,
                        "❌ Les votes sont **verrouillés**. Tous les loups ont déjà voté.",
                        formatted=True
                    )
                    return {'success': False, 'error': 'Votes verrouillés'}
            elif self.game_manager.phase == GamePhase.VOTE and is_village:
                pass  # OK
            elif self.game_manager.phase == GamePhase.NIGHT and not is_wolves:
                await self.client.send_dm(
                    user_id,
                    f"❌ Utilisez `{self.command_prefix}vote` dans le **salon des loups** pour voter la nuit."
                )
                return {'success': False, 'error': 'Mauvais salon'}
            elif self.game_manager.phase == GamePhase.VOTE and not is_village:
                await self.client.send_dm(
                    user_id,
                    f"❌ Utilisez `{self.command_prefix}vote` dans le **salon du village** pour voter."
                )
                return {'success': False, 'error': 'Mauvais salon'}
            else:
                await self.client.send_dm(user_id, "❌ Ce n'est pas le moment de voter.")
                return {'success': False, 'error': 'Phase incorrecte'}

        # Commande vote-maire : uniquement au village, pendant DAY/VOTE, si l'élection est ouverte
        if command == 'vote-maire':
            if not self.game_manager.can_vote_mayor():
                await self.client.send_dm(user_id, "❌ L'élection du maire n'est pas en cours.")
                return {'success': False, 'error': 'Élection non disponible'}
            if not is_village:
                await self.client.send_dm(
                    user_id,
                    f"❌ Utilisez `{self.command_prefix}vote-maire` dans le **salon du village**."
                )
                return {'success': False, 'error': 'Mauvais salon'}

        # Dictateur : commande au village (tout le monde voit le coup d'etat)
        if command == 'dictateur':
            if not is_village:
                await self.client.send_dm(
                    user_id,
                    f"❌ La commande **{self.command_prefix}dictateur** doit être utilisée dans le **salon du village**."
                )
                return {'success': False, 'error': 'Mauvais salon'}
            if self.game_manager.phase not in (GamePhase.NIGHT, GamePhase.DAY, GamePhase.VOTE):
                await self.client.send_dm(
                    user_id,
                    "❌ Le Dictateur ne peut agir que **la nuit** (pour armer) ou **le jour** (pour frapper)."
                )
                return {'success': False, 'error': 'Phase incorrecte'}
            if self.game_manager.night_count < 1:
                await self.client.send_dm(user_id, "❌ La première nuit n'a pas encore eu lieu.")
                return {'success': False, 'error': 'Première nuit requise'}

        # Maire : désignation du successeur, DM uniquement
        if command == 'maire':
            if not is_dm:
                await self.client.send_dm(
                    user_id,
                    f"❌ La commande **{self.command_prefix}maire** doit être utilisée en **message privé** avec le bot."
                )
                return {'success': False, 'error': 'Commande privée uniquement'}

        # Geolier : selection du prisonnier, DM uniquement, de jour
        if command == 'geolier':
            if not is_dm:
                await self.client.send_dm(
                    user_id,
                    f"❌ La commande **{self.command_prefix}geolier** doit être utilisée en **message privé** avec le bot."
                )
                return {'success': False, 'error': 'Commande privée uniquement'}
            if self.game_manager.phase != GamePhase.DAY:
                await self.client.send_dm(user_id, "❌ Le Geolier ne peut agir que **pendant le jour**.")
                return {'success': False, 'error': 'Phase incorrecte'}

        # Geolier : execution du prisonnier, DM uniquement, la nuit
        if command == 'geolier-tuer':
            if not is_dm:
                await self.client.send_dm(
                    user_id,
                    f"❌ La commande **{self.command_prefix}geolier-tuer** doit être utilisée en **message privé** avec le bot."
                )
                return {'success': False, 'error': 'Commande privée uniquement'}
            if self.game_manager.phase != GamePhase.NIGHT:
                await self.client.send_dm(user_id, "❌ Le Geolier ne peut executer que **pendant la nuit**.")
                return {'success': False, 'error': 'Phase incorrecte'}

        # Commandes nocturnes privées : uniquement en DM, la nuit
        night_dm_commands = [
            'voyante', 'sorciere-sauve', 'sorciere-tue', 'garde', 'cupidon',
            'medium', 'enfant', 'corbeau', 'curse', 'tuer',
            'voleur-tirer', 'voleur-choisir', 'voleur-echange', 'lg',
            'convertir', 'assassin', 'pyromane', 'pyromane-brule', 'detective',
            'geolier-tuer'
        ]
        if command in night_dm_commands:
            if not is_dm:
                await self.client.send_dm(
                    user_id,
                    f"❌ La commande **{self.command_prefix}{command}** doit être utilisée en **message privé** avec le bot."
                )
                return {'success': False, 'error': 'Commande privée uniquement'}
            if self.game_manager.phase != GamePhase.NIGHT:
                # Exception pour le chasseur (peut tirer de jour aussi)
                if command != 'tuer' or not player.role or player.role.role_type != RoleType.CHASSEUR:
                    await self.client.send_dm(user_id, "❌ Cette commande n'est utilisable que **la nuit**.")
                    return {'success': False, 'error': 'Phase incorrecte'}

        # Prisonnier : aucune action possible (sauf !msg)
        if player.is_jailed and command != 'msg':
            await self.client.send_dm(user_id, "❌ Vous etes emprisonne et ne pouvez pas agir.")
            return {'success': False, 'error': 'Emprisonne'}

        # Relai des messages du geolier (DM)
        if command == 'msg':
            if not is_dm:
                await self.client.send_dm(
                    user_id,
                    f"❌ La commande **{self.command_prefix}msg** doit être utilisée en **message privé** avec le bot."
                )
                return {'success': False, 'error': 'Commande privée uniquement'}
            if not args:
                await self.client.send_dm(user_id, f"❌ Usage : {self.command_prefix}msg {{message}}")
                return {'success': False, 'error': 'Args manquants'}

            jailer, prisoner = self.game_manager.get_jailer_and_prisoner()
            if not jailer or not prisoner:
                await self.client.send_dm(user_id, "❌ Il n'y a pas d'interrogatoire en cours.")
                return {'success': False, 'error': 'Pas de prisonnier'}

            if user_id not in {jailer.user_id, prisoner.user_id}:
                await self.client.send_dm(user_id, "❌ Vous n'etes pas concerne par l'interrogatoire.")
                return {'success': False, 'error': 'Non autorise'}

            message = ' '.join(args).strip()
            if user_id == jailer.user_id:
                await self.client.send_dm(
                    prisoner.user_id,
                    f"🔒 **Message du geolier :**\n{message}"
                )
            else:
                await self.client.send_dm(
                    jailer.user_id,
                    f"🔒 **Message du prisonnier :**\n{message}"
                )

            await self.client.send_dm(user_id, "✅ Message envoye.")
            return {'success': True}

        # Exécuter la commande via execute_command (passe les args bruts)
        try:
            result = self.command_handler.execute_command(
                user_id=user_id,
                command=command,
                args=args
            )

            # Envoyer confirmation au joueur en DM
            if result['success']:
                msg = result.get('message', f"Commande **{self.command_prefix}{command}** exécutée avec succès")
                await self.client.send_dm(user_id, f"✅ {msg}")
            else:
                await self.client.send_dm(
                    user_id,
                    f"❌ Erreur: {result.get('message', 'Commande invalide')}"
                )

            # ── Journal de fin de partie : tracer les actions secrètes ──
            if result['success']:
                self._track_journal_event(command, args, result, player)

            # Après un vote loup réussi, vérifier si tous les loups ont voté
            if (result['success'] and command == 'vote'
                and self.game_manager.phase == GamePhase.NIGHT):
                await self._check_wolf_vote_complete()

            # Après un vote-maire, annoncer la progression
            if (result['success'] and command == 'vote-maire'
                and self.game_manager.can_vote_mayor()):
                await self._check_mayor_election_progress()

            # Après !cupidon réussi, créer immédiatement le salon du couple
            # et notifier les amoureux (ils se "réveillent" pendant la nuit)
            if result.get('success') and command == 'cupidon':
                await self._create_couple_room_if_needed()

            # Après !lg, vérifier si le Loup Voyant doit rejoindre le salon
            if result.get('success') and command == 'lg':
                await self._check_loup_voyant_room()

            # Dictateur : annoncer publiquement quand le pouvoir est arme
            if result.get('success') and command == 'dictateur' and result.get('armed'):
                await self.room_manager.send_to_village(
                    f"⚔️ **Le Dictateur {player.display_name}** a pris le pouvoir, "
                    "il va tuer quelqu'un."
                )

            # Voleur échange : notifier la cible et gérer les salons
            if (result.get('success') and command == 'voleur-echange'
                    and result.get('swapped_target')):
                swapped = result['swapped_target']
                await self.client.send_dm(
                    swapped.user_id,
                    "🔄 **Votre rôle a changé !**\n\n"
                    "Le **Voleur** a échangé son rôle avec le vôtre.\n"
                    f"Vous êtes maintenant: **{swapped.role.name}**\n\n"
                    "Votre ancien pouvoir a été transféré au Voleur."
                )
                # Gérer les salons loups après l'échange
                await self._handle_voleur_swap_rooms(player, swapped)

            # Voleur choisir : si le nouveau rôle est un loup, ajouter au salon
            if (result.get('success') and command == 'voleur-choisir'):
                await self._check_voleur_new_role_rooms(player)

            # Annuler le timeout du chasseur si tir réussi
            if result.get('success') and command == 'tuer':
                self._cancel_chasseur_timeout(user_id)
                if player.role and player.role.role_type == RoleType.CHASSEUR:
                    try:
                        await self.room_manager.add_to_dead(user_id)
                        logger.info("☠️ %s invité au cimetière (tir du Chasseur)", user_id)
                    except Exception as e:
                        logger.error(
                            "Erreur invitation cimetière (tir du Chasseur) pour %s: %s",
                            user_id,
                            e,
                        )

            # Traiter les morts instantanées (Chasseur, Dictateur)
            if result.get('success') and result.get('deaths'):
                await self._process_command_deaths(result, command, user_id)

            # Maire succession : annoncer le nouveau maire
            if result.get('success') and command == 'maire':
                new_mayor = result.get('new_mayor')
                if new_mayor:
                    # Annuler le timeout
                    if self._mayor_succession_task and not self._mayor_succession_task.done():
                        self._mayor_succession_task.cancel()
                    # Annoncer dans le village
                    await self.room_manager.send_to_village(
                        f"👑 **{new_mayor.display_name}** est le nouveau maire !\n"
                        f"Désigné par le maire sortant."
                    )
                    # Informer le nouveau maire
                    await self.client.send_dm(
                        new_mayor.user_id,
                        self._NEW_MAYOR_DM
                    )

            return result

        except Exception as e:
            logger.error(f"Erreur commande {command}: {e}")
            return {'success': False, 'error': str(e)}

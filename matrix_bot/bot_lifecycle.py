"""Mixin de cycle de vie du bot."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from nio import InviteMemberEvent

from models.enums import GamePhase, RoleType
from matrix_bot.scheduler import wait_until_new_game, day_name_fr
from matrix_bot.integration_test import IntegrationTester
from matrix_bot.message_handler import MessageHandler
from matrix_bot.notifications import NotificationManager

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class BotLifecycleMixin:
    """Cycle de vie principal du bot."""

    async def start(self: 'WerewolfBot'):
        """Démarre le bot."""
        logger.info("Démarrage du bot Werewolf...")

        connected = await self.client.connect()
        if not connected:
            logger.critical("❌ Impossible de se connecter à Matrix. Arrêt du bot.")
            return
        logger.info("Connecté à Matrix")

        perms_ok = await self.client.verify_permissions(self.lobby_room_id, self.space_id)
        if not perms_ok:
            logger.warning("⚠️ Des permissions sont manquantes. Le bot continue mais peut rencontrer des erreurs.")

        self.client.client.add_event_callback(self._on_invite, InviteMemberEvent)
        logger.info("✅ Auto-accept des invitations activé")

        if self.game_manager.db.is_first_run() and self.runtests:
            await self._run_integration_tests()

        self.message_handler = MessageHandler(
            self.client.client,
            self.user_id,
            command_prefix=self.command_prefix,
        )
        self.message_handler.on_command = self._handle_command
        self.message_handler.on_registration = self._handle_registration
        self.message_handler.on_wolf_message = self._handle_wolf_message
        self.message_handler.on_village_message = self._handle_village_message

        self.notification_manager = NotificationManager(
            self.room_manager,
            command_prefix=self.command_prefix,
        )

        saved_registrations = self.game_manager.db.load_registrations()
        if saved_registrations:
            self.registered_players.update(saved_registrations)
            logger.info(
                "♻️ %s inscription(s) restaurée(s) depuis la BDD",
                len(saved_registrations),
            )

        self._restored_game = False
        if self.game_manager.db.has_active_game():
            restored = await self._restore_game_state()
            if restored:
                self._restored_game = True
                await self.client.send_message(
                    self.lobby_room_id,
                    "♻️ **Le bot a redémarré** — la partie en cours a été restaurée avec succès !\n\n"
                    f"Phase actuelle : **{self.game_manager.phase.value}**, "
                    f"Jour {self.game_manager.day_count}, Nuit {self.game_manager.night_count}\n"
                    f"Joueurs : {len(self.game_manager.players)}",
                    formatted=True,
                )
            else:
                logger.warning("Restauration échouée — nettoyage de l'ancien état")
                self.game_manager.db.clear_current_game()
                await self.client.send_message(
                    self.lobby_room_id,
                    "⚠️ **Le bot a redémarré** — la partie précédente n'a pas pu être "
                    "récupérée.\n\n"
                    f"Tapez `{self.command_prefix}inscription` pour vous réinscrire à la prochaine partie.",
                    formatted=True,
                )

        jour = day_name_fr(self._game_start_day)
        wolf_deadline = self.scheduler.wolf_vote_deadline.strftime('%Hh%M')
        welcome_msg = (
            f"🐺 **Bot Loup-Garou démarré !**\n\n"
            f"Tapez `{self.command_prefix}inscription` pour participer à la prochaine partie.\n"
            f"La partie démarrera **{jour} à {self._game_start_hour}h**.\n\n"
            f"📋 Règles:\n"
            f"• 1 jour IRL = 1 jour + 1 nuit de jeu\n"
            f"• Nuit: {self._night_hour}h → {self._day_hour}h\n"
            f"  └ Loups: jusqu'à {wolf_deadline} | Sorcière: {wolf_deadline} → {self._day_hour}h\n"
            f"• Jour: {self._day_hour}h → {self._night_hour}h\n"
            f"• Vote: {self._vote_hour}h → {self._night_hour}h\n"
            f"• Durée max: {self._max_days} jours"
        )
        if self.disabled_roles:
            from models.role import ROLE_DISPLAY_NAMES
            disabled_names = ', '.join(
                ROLE_DISPLAY_NAMES.get(rt, rt.value)
                for rt in sorted(self.disabled_roles, key=lambda r: r.value)
            )
            welcome_msg += f"\n\n🚫 **Rôles désactivés :** {disabled_names}"
        if self.registered_players:
            names = ", ".join(self.registered_players.values())
            welcome_msg += (
                f"\n\n♻️ **{len(self.registered_players)}** inscription(s) restaurée(s) : "
                f"{names}"
            )
        await self.client.send_message(
            self.lobby_room_id,
            welcome_msg,
            formatted=True,
        )

        self.running = True

        self._sync_task = asyncio.create_task(
            self.client.client.sync_forever(timeout=30000, full_state=True)
        )
        logger.info("✅ Sync Matrix démarré en arrière-plan")

        await self._run_game_loop()

    async def stop(self: 'WerewolfBot'):
        """Arrête le bot."""
        logger.info("Arrêt du bot...")
        self.running = False
        self.scheduler.stop()

        if hasattr(self, '_sync_task') and self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        await self.client.disconnect()

    async def _run_integration_tests(self: 'WerewolfBot'):
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

    async def _restore_game_state(self: 'WerewolfBot') -> bool:
        """Restaure l'état complet d'une partie après un crash/redémarrage."""
        try:
            logger.info("♻️ Tentative de restauration de la partie en cours...")

            if not self.game_manager.load_state():
                logger.error("Échec de la restauration du GameManager")
                return False

            saved_rooms = self.game_manager.db.load_room_state()
            if saved_rooms:
                self.room_manager.village_room = saved_rooms.get('village')
                self.room_manager.wolves_room = saved_rooms.get('wolves')
                self.room_manager.couple_room = saved_rooms.get('couple')
                self.room_manager.dead_room = saved_rooms.get('dead')
            else:
                logger.warning("Aucun salon Matrix sauvegardé — la restauration reste possible mais limitée")

            if self.message_handler and self.room_manager.village_room:
                self.message_handler.village_room_id = self.room_manager.village_room

            self._accepting_registrations = False

            self._wolves_in_room = {
                p.user_id for p in self.game_manager.players.values()
                if p.role and p.role.can_vote_with_wolves() and p.is_alive
            }

            self.registered_players = {
                p.user_id: p.display_name
                for p in self.game_manager.players.values()
            }

            self.game_manager.on_remove_wolf_from_room = (
                lambda uid: asyncio.ensure_future(self._remove_wolf_from_room(uid))
            )
            self.game_manager.on_mute_player = (
                lambda uid: asyncio.ensure_future(self._mute_player(uid))
            )

            logger.info(
                "✅ Partie restaurée : phase=%s, jour=%d, nuit=%d, joueurs=%d",
                self.game_manager.phase.value,
                self.game_manager.day_count,
                self.game_manager.night_count,
                len(self.game_manager.players),
            )
            return True

        except Exception as e:
            logger.error("Erreur lors de la restauration de la partie: %s", e, exc_info=True)
            return False

    async def _run_game_loop(self: 'WerewolfBot'):
        """Boucle principale du jeu."""
        try:
            while self.running:
                if self._restored_game:
                    self._restored_game = False
                    logger.info("♻️ Reprise de la partie restaurée...")
                else:
                    jour = day_name_fr(self._game_start_day)
                    logger.info("En attente du prochain %s %sh...", jour, self._game_start_hour)
                    await self._wait_for_game_start()

                    if not self.running:
                        break

                    game_started = await self._start_game()

                    if not game_started:
                        self.registered_players.clear()
                        self.game_manager.db.clear_registrations()
                        continue

                self.scheduler.start_game(datetime.now())
                self.scheduler.on_night_start = self._on_night_start
                self.scheduler.on_day_start = self._on_day_start
                self.scheduler.on_vote_start = self._on_vote_start

                logger.info(
                    "Scheduler configuré — Nuit: %sh, Jour: %sh, Vote: %sh, "
                    "Phase actuelle: %s",
                    self._night_hour,
                    self._day_hour,
                    self._vote_hour,
                    self.game_manager.phase.value,
                )

                self._kill_signal_task = asyncio.create_task(self._monitor_kill_signal())
                await self.scheduler.run()

                logger.info("Scheduler terminé — fin de partie")

                if self._kill_signal_task and not self._kill_signal_task.done():
                    self._kill_signal_task.cancel()

                await self._end_game()

                self.registered_players.clear()
                self._game_events.clear()
                self._wolves_in_room.clear()
                self.game_manager.reset()

        except Exception as e:
            logger.error("Erreur dans la boucle de jeu: %s", e)
            raise

    async def _wait_for_game_start(self: 'WerewolfBot'):
        """Attend le prochain jour/heure configuré dans le .env."""
        signal_path = Path(os.getenv("FORCE_START_SIGNAL", "force_start.signal"))

        wait_task = asyncio.create_task(
            wait_until_new_game(self._game_start_day, self._game_start_hour)
        )

        while not wait_task.done():
            await asyncio.sleep(30)

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

            db_regs = self.game_manager.db.load_registrations()
            if db_regs != self.registered_players:
                added = set(db_regs) - set(self.registered_players)
                removed = set(self.registered_players) - set(db_regs)
                self.registered_players = dict(db_regs)
                if added:
                    logger.info(
                        "📥 Inscription(s) ajoutée(s) via admin : %s",
                        ", ".join(db_regs[uid] for uid in added),
                    )
                if removed:
                    logger.info(
                        "📤 Inscription(s) retirée(s) via admin : %s",
                        ", ".join(str(uid) for uid in removed),
                    )

            if len(self.registered_players) > 0:
                logger.info("%s joueur(s) inscrit(s)", len(self.registered_players))

        await asyncio.gather(wait_task, return_exceptions=True)

    async def _monitor_kill_signal(self: 'WerewolfBot'):
        """Surveille le fichier sentinelle kill.signal pendant une partie."""
        import json as _json

        signal_path = Path(os.getenv("KILL_SIGNAL", "kill.signal"))

        try:
            while self.running and self.game_manager.phase != GamePhase.ENDED:
                await asyncio.sleep(10)

                if not signal_path.exists():
                    continue

                try:
                    payload = _json.loads(signal_path.read_text())
                    signal_path.unlink()
                except (OSError, _json.JSONDecodeError) as exc:
                    logger.error("Erreur lecture kill.signal: %s", exc)
                    continue

                user_id = payload.get("user_id")
                reason = payload.get("reason", "Tué par un administrateur")

                if not user_id:
                    logger.warning("kill.signal sans user_id — ignoré")
                    continue

                player = self.game_manager.get_player(user_id)
                if not player:
                    logger.warning("kill.signal: joueur %s introuvable", user_id)
                    continue

                if not player.is_alive:
                    logger.warning("kill.signal: joueur %s déjà mort.e.", user_id)
                    continue

                logger.info(
                    "💀 Admin kill: %s (%s) — %s",
                    player.display_name,
                    user_id,
                    reason,
                )

                self._admin_kill_reason = reason

                all_deaths = self.game_manager.kill_player(player, killed_during_day=True)

                await self._process_command_deaths(
                    {'deaths': all_deaths},
                    'admin-kill',
                    user_id,
                )

        except asyncio.CancelledError:
            logger.debug("Surveillance kill.signal arrêtée")
        except Exception as e:
            logger.error("Erreur dans _monitor_kill_signal: %s", e, exc_info=True)

    async def _start_game(self: 'WerewolfBot') -> bool:
        """Démarre une nouvelle partie."""
        db_regs = self.game_manager.db.load_registrations()
        if db_regs:
            self.registered_players = dict(db_regs)

        logger.info("Démarrage de la partie avec %s joueurs", len(self.registered_players))

        if len(self.registered_players) < 5:
            await self.client.send_message(
                self.lobby_room_id,
                "❌ Pas assez de joueurs inscrits (minimum 5). "
                "Partie annulée, réinscrivez-vous pour la semaine prochaine.",
                formatted=True,
            )
            return False

        for uid, display_name in self.registered_players.items():
            if uid not in self.game_manager.players:
                self.game_manager.add_player(display_name, uid)
                player = self.game_manager.players[uid]
                player.display_name = display_name

        player_ids = list(self.registered_players.keys())

        result = self.game_manager.start_game(immediate_night=False)
        if not result.get("success"):
            await self.client.send_message(
                self.lobby_room_id,
                f"❌ Impossible de lancer la partie : {result.get('message', 'erreur inconnue')}",
                formatted=True,
            )
            return False

        self._game_events = []

        await self.client.send_message(
            self.lobby_room_id,
            "🎮 **La partie commence !** Les salons de jeu ont été créés.\n"
            "Rendez-vous dans le salon **Village** pour jouer.\n\n"
            "Les inscriptions sont fermées jusqu'à la fin de la partie.",
            formatted=True,
        )
        self._accepting_registrations = False

        self.game_manager.db.clear_registrations()

        await self.room_manager.create_all_rooms(player_ids)

        if self.message_handler:
            self.message_handler.village_room_id = self.room_manager.village_room

        roles_message = self._build_roles_announcement()
        roles_event_id = await self.room_manager.send_to_village(roles_message)
        if roles_event_id and self.room_manager.village_room:
            await self.client.pin_message(self.room_manager.village_room, roles_event_id)

        seating_message = self._build_seating_message()
        seating_message_event_id = await self.room_manager.send_to_village(seating_message)
        if seating_message_event_id and self.room_manager.village_room:
            await self.client.pin_message(self.room_manager.village_room, seating_message_event_id)

        await self._create_special_rooms()

        await self._send_role_notifications()

        self._save_room_state()

        return True

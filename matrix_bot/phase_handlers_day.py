"""Gestion des callbacks de jour."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from models.enums import GamePhase, RoleType

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class PhaseDayHandlersMixin:
    """Callbacks de jour et helpers associes."""

    async def _on_day_start(self: 'WerewolfBot', phase: GamePhase):
        """Appelé au début de chaque jour."""
        logger.info("☀️ Début du jour")

        if self._wolf_deadline_task and not self._wolf_deadline_task.done():
            self._wolf_deadline_task.cancel()

        await self._release_jailer_day()

        if self.game_manager.night_count < 1:
            logger.info("Pas de nuit à résoudre (première nuit pas encore jouée) — transition ignorée")
            return

        if not self._sorciere_notified:
            await self._notify_sorciere_wolf_target()

        self.game_manager.set_phase(GamePhase.NIGHT)

        await self._create_couple_room_if_needed()

        results = self.game_manager.resolve_night()

        if results.get('converted'):
            await self._handle_conversion(results['converted'])

        if results.get('saved'):
            for saved_id in results['saved']:
                saved_player = self.game_manager.get_player(saved_id)
                if saved_player:
                    self._game_events.append(
                        f"Nuit {self.game_manager.night_count} — 🛡️ **{saved_player.display_name}** "
                        f"sauvé par la protection du Garde"
                    )

        await self._check_enfant_sauvage_conversion()

        message = "☀️ **Le jour se lève sur le village...**\n\n"

        if results['deaths']:
            message += "💀 Cette nuit, les victimes sont:\n"
            for player_id in results['deaths']:
                player = self.game_manager.get_player(player_id)
                if player:
                    message += f"• **{player.display_name}** — **{player.role.name}**\n"
                    self._game_events.append(
                        f"Nuit {self.game_manager.night_count} — 💀 **{player.display_name}** "
                        f"tué durant la nuit ({player.role.name})"
                    )
                    await self.room_manager.add_to_dead(player_id)
        else:
            message += "🎉 Personne n'est mort cette nuit !\n"

        for player in self.game_manager.players.values():
            if (player.is_alive and player.role
                    and player.role.role_type == RoleType.MONTREUR_OURS):
                if player.role.check_for_wolves(self.game_manager):
                    message += "\n🐻 **L'ours du montreur d'ours grogne !** Un loup est assis à côté de lui...\n"

        message += f"\n💬 Les villageois peuvent discuter jusqu'à {self._vote_hour}h00."

        await self.room_manager.send_to_village(message)

        if results['deaths'] and self.notification_manager:
            for player_id in results['deaths']:
                player = self.game_manager.get_player(player_id)
                if player:
                    await self.notification_manager.send_death_notification(
                        player.user_id, player.role
                    )

        if results['deaths']:
            await self._update_seating_message()

        self._sorciere_notified = False
        self._wolf_votes_locked = False

        if results.get('winner'):
            await self._announce_victory(results['winner'])
            self.scheduler.stop()
        else:
            await self._check_victory()

        if self.game_manager.phase != GamePhase.ENDED:
            await self._check_mayor_succession()

        if self.game_manager.phase != GamePhase.ENDED:
            await self._check_and_start_chasseur_timeouts()

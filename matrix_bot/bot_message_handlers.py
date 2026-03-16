"""Mixins pour les handlers de messages."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from models.enums import GamePhase, RoleType

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class BotMessageHandlersMixin:
    """Handlers d'invitation et messages de salons."""

    async def _on_invite(self: 'WerewolfBot', room, event):
        """Auto-accepte toutes les invitations reçues par le bot."""
        if event.state_key != self.user_id:
            return
        if event.membership != "invite":
            return

        try:
            await self.client.client.join(room.room_id)
            logger.info(
                "✅ Invitation acceptée : %s (invité par %s)",
                room.room_id,
                event.sender,
            )
        except Exception as e:
            logger.error("❌ Impossible d'accepter l'invitation pour %s: %s", room.room_id, e)

    async def _handle_wolf_message(self: 'WerewolfBot', message: str, sender: str):
        """Gère un message envoyé dans le salon des loups pour la Petite Fille."""
        if self.game_manager.phase != GamePhase.NIGHT:
            return

        little_girl = None
        for player in self.game_manager.players.values():
            if (player.role and player.role.role_type == RoleType.PETITE_FILLE
                    and player.is_alive):
                little_girl = player
                break

        if not little_girl:
            return

        try:
            if self.distort_little_girl_messages:
                formatted_message = self.message_distorter.format_wolf_message_for_little_girl(
                    message,
                    distort=True,
                )
            else:
                formatted_message = self.message_distorter.format_wolf_message_for_little_girl(
                    message,
                    distort=False,
                )

            await self.client.send_dm(little_girl.user_id, formatted_message)
            logger.debug(
                "Message des loups transmis à la Petite Fille (distorsion: %s)",
                self.distort_little_girl_messages,
            )

        except Exception as e:
            logger.error("Erreur lors de la transmission à la Petite Fille: %s", e)

    async def _handle_village_message(self: 'WerewolfBot', message: str, sender: str):
        """Gère un message envoyé dans le salon du village."""
        if self.game_manager.phase not in (GamePhase.DAY, GamePhase.VOTE):
            return

        player = self.game_manager.get_player(sender)
        if not player or not player.is_alive:
            return

        if player.role and player.role.role_type == RoleType.LOUP_BAVARD:
            if player.role.check_message_for_word(message):
                logger.debug("Loup Bavard %s a dit le mot imposé !", player.pseudo)

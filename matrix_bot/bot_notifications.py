"""Mixins pour les notifications du bot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.enums import RoleType

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot


class BotNotificationsMixin:
    """Envoi des notifications de roles."""

    async def _send_role_notifications(self: 'WerewolfBot'):
        """Envoie les informations de role a chaque joueur via DM."""
        for player in self.game_manager.players.values():
            await self.notification_manager.send_role_assignment(
                player.user_id,
                player.role,
            )

        for player in self.game_manager.players.values():
            if (player.role
                    and player.role.role_type == RoleType.MERCENAIRE
                    and getattr(player, 'target', None)):
                await self.notification_manager.send_mercenaire_target(
                    player.user_id,
                    player.target.pseudo,
                )

        for player in self.game_manager.players.values():
            if (player.role
                    and player.role.role_type == RoleType.CHASSEUR_DE_TETES
                    and getattr(player, 'target', None)):
                await self.notification_manager.send_chasseur_de_tetes_target(
                    player.user_id,
                    player.target.pseudo,
                )

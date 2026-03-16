"""Mixins de gestion des salons et mutes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class BotRoomsMixin:
    """Gestion des salons et des permissions."""

    async def _set_room_power(self: 'WerewolfBot', room_id: str, user_id: str, level: int):
        """Fixe le power level d'un joueur dans un salon si possible."""
        if not room_id:
            return
        try:
            await self.client.set_power_level(room_id, user_id, level)
        except Exception as e:
            logger.error("Erreur power level %s pour %s: %s", room_id, user_id, e)

    async def _jail_player(self: 'WerewolfBot', user_id: str):
        """Mute temporairement un joueur dans tous les salons (geolier)."""
        if self.room_manager.village_room:
            await self._set_room_power(self.room_manager.village_room, user_id, -1)

        if self.room_manager.wolves_room:
            await self._set_room_power(self.room_manager.wolves_room, user_id, -1)

        if self.room_manager.couple_room:
            try:
                members = await self.client.get_room_members(self.room_manager.couple_room)
                if user_id in members:
                    await self._set_room_power(self.room_manager.couple_room, user_id, -1)
            except Exception as e:
                logger.error("Erreur mute couple (geolier) pour %s: %s", user_id, e)

    async def _unjail_player(self: 'WerewolfBot', user_id: str):
        """Retire le mute temporaire d'un joueur (geolier)."""
        if self.room_manager.village_room:
            await self._set_room_power(self.room_manager.village_room, user_id, 0)

        if self.room_manager.wolves_room:
            await self._set_room_power(self.room_manager.wolves_room, user_id, 0)

        if self.room_manager.couple_room:
            try:
                members = await self.client.get_room_members(self.room_manager.couple_room)
                if user_id in members:
                    await self._set_room_power(self.room_manager.couple_room, user_id, 0)
            except Exception as e:
                logger.error("Erreur unmute couple (geolier) pour %s: %s", user_id, e)

    async def _create_special_rooms(self: 'WerewolfBot'):
        """Crée les salons spéciaux (loups seulement au départ)."""
        wolf_players = [
            p for p in self.game_manager.players.values()
            if p.role and p.role.can_vote_with_wolves()
        ]

        if wolf_players:
            wolf_ids = [p.user_id for p in wolf_players]
            wolves_room_id = await self.room_manager.create_wolves_room(wolf_ids)

            self._wolves_in_room = set(wolf_ids)

            if wolves_room_id and self.message_handler:
                self.message_handler.wolves_room_id = wolves_room_id

    async def _create_couple_room_if_needed(self: 'WerewolfBot'):
        """Crée le salon du couple si Cupidon a marié deux joueurs."""
        if self.room_manager.couple_room:
            return

        groups = self.game_manager.get_love_groups(alive_only=True)
        if not groups:
            return

        lovers = list(groups[0])
        lover_ids = [p.user_id for p in lovers]
        await self.room_manager.create_couple_room(lover_ids)

        if self.notification_manager:
            await self.notification_manager.send_couple_notification(lovers)

        self._save_room_state()

    def _save_room_state(self: 'WerewolfBot'):
        """Sauvegarde les IDs des salons Matrix en BDD pour récupération crash."""
        rooms = {
            'village': self.room_manager.village_room,
            'wolves': self.room_manager.wolves_room,
            'couple': self.room_manager.couple_room,
            'dead': self.room_manager.dead_room,
        }
        self.game_manager.db.save_room_state(rooms)

    async def _remove_wolf_from_room(self: 'WerewolfBot', user_id: str):
        """Passe un loup mort en lecture seule dans le salon des loups."""
        if self.room_manager.wolves_room:
            try:
                await self.client.set_power_level(
                    self.room_manager.wolves_room, user_id, -1
                )
                self._wolves_in_room.discard(user_id)
                logger.info(
                    "🐺☠️ %s en lecture seule dans le salon des loups (spectateur)",
                    user_id,
                )
            except Exception as e:
                logger.error("Erreur lors du passage en lecture seule du loup: %s", e)

    async def _mute_player(self: 'WerewolfBot', user_id: str):
        """Mute un joueur mort : lecture seule partout, muté dans le couple."""
        if self.room_manager.village_room:
            try:
                await self.client.set_power_level(
                    self.room_manager.village_room, user_id, -1
                )
                logger.info("☠️ %s muté dans le village (power level -1)", user_id)
            except Exception as e:
                logger.error("Erreur mute village pour %s: %s", user_id, e)

        if self.room_manager.wolves_room and user_id in self._wolves_in_room:
            try:
                await self.client.set_power_level(
                    self.room_manager.wolves_room, user_id, -1
                )
                self._wolves_in_room.discard(user_id)
                logger.info("☠️ %s muté dans le salon des loups (spectateur)", user_id)
            except Exception as e:
                logger.error("Erreur mute loups pour %s: %s", user_id, e)

        if self.room_manager.couple_room:
            try:
                members = await self.client.get_room_members(self.room_manager.couple_room)
                if user_id in members:
                    await self.client.set_power_level(
                        self.room_manager.couple_room, user_id, -1
                    )
                    logger.info("☠️ %s muté dans le salon du couple (spectateur)", user_id)
            except Exception as e:
                logger.error("Erreur mute couple pour %s: %s", user_id, e)

        try:
            await self.room_manager.add_to_dead(user_id)
            logger.info("☠️ %s invité au cimetière", user_id)
        except Exception as e:
            logger.error("Erreur invitation cimetière pour %s: %s", user_id, e)

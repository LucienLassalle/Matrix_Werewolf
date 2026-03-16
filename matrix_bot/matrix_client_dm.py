"""Mixins pour la gestion des DMs Matrix."""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp
from nio import RoomVisibility, RoomPreset

logger = logging.getLogger(__name__)


class MatrixClientDMMixin:
    """Helpers pour les messages directs."""

    async def send_dm(self, user_id: str, message: str) -> bool:
        """Envoie un message prive (DM) a un utilisateur via Matrix."""
        if not self.client:
            logger.error("Client non connecté")
            return False

        try:
            dm_room = self._dm_rooms.get(user_id)
            if dm_room:
                logger.info("📩 DM → %s: cache hit (room=%s)", user_id, dm_room)

            if not dm_room:
                dm_room = await self._find_existing_dm(user_id)
                if dm_room:
                    logger.info("📩 DM → %s: salon existant trouvé (room=%s)", user_id, dm_room)

            if not dm_room:
                logger.info("📩 DM → %s: aucun DM existant, création d'un nouveau salon...", user_id)
                dm_room = await self._create_direct_room(user_id)
                if dm_room:
                    logger.info("📩 DM → %s: nouveau salon créé (room=%s)", user_id, dm_room)

            if dm_room:
                self._dm_rooms[user_id] = dm_room
                event_id = await self.send_message(dm_room, message, formatted=True)
                if event_id:
                    logger.info(
                        "📩 DM → %s: message envoyé ✅ (room=%s, len=%s)",
                        user_id, dm_room, len(message),
                    )
                else:
                    logger.error(
                        "📩 DM → %s: send_message a ÉCHOUÉ dans room=%s",
                        user_id, dm_room,
                    )
                    self._dm_rooms.pop(user_id, None)
                return bool(event_id)

            logger.error("📩 DM → %s: IMPOSSIBLE d'obtenir un salon DM", user_id)
            return False

        except Exception as e:
            logger.error("📩 DM → %s: EXCEPTION %s", user_id, e)
            self._dm_rooms.pop(user_id, None)
            return False

    async def _find_existing_dm(self, user_id: str) -> Optional[str]:
        """Cherche un salon DM existant via m.direct (account data)."""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            url = f"{self.homeserver}/_matrix/client/v3/user/{self.user_id}/account_data/m.direct"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        direct_data = await resp.json()
                        dm_rooms_for_user = direct_data.get(user_id, [])

                        if dm_rooms_for_user:
                            logger.info("🔍 m.direct pour %s: %s", user_id, dm_rooms_for_user)
                            response = await self.client.joined_rooms()
                            joined = response.rooms if hasattr(response, 'rooms') else []

                            for room_id in dm_rooms_for_user:
                                if room_id in joined:
                                    logger.info(
                                        "🔍 DM existant trouvé via m.direct: %s (bot est membre)",
                                        room_id,
                                    )
                                    return room_id
                                logger.info(
                                    "🔍 DM %s dans m.direct mais bot n'est plus membre — ignoré",
                                    room_id,
                                )
                        else:
                            logger.info("🔍 Aucun DM dans m.direct pour %s", user_id)
                    elif resp.status == 404:
                        logger.info("🔍 Pas de données m.direct (premier usage)")
                    else:
                        body = await resp.text()
                        logger.warning("🔍 Erreur lecture m.direct: %s - %s", resp.status, body)
        except Exception as e:
            logger.warning("🔍 Impossible de lire m.direct: %s", e)

        logger.info("🔍 Aucun DM existant trouvé pour %s", user_id)
        return None

    async def _create_direct_room(self, user_id: str) -> Optional[str]:
        """Cree un DM Matrix (is_direct, sans nom, hors du space)."""
        try:
            response = await self.client.room_create(
                visibility=RoomVisibility.private,
                preset=RoomPreset.private_chat,
                is_direct=True,
                invite=[user_id],
                initial_state=[
                    {
                        "type": "m.room.history_visibility",
                        "content": {"history_visibility": "invited"},
                    }
                ],
            )

            if hasattr(response, 'room_id'):
                room_id = response.room_id
                logger.info("DM créé avec %s: %s", user_id, room_id)

                await self._set_direct_room(user_id, room_id)

                return room_id
            logger.error("Erreur création DM: %s", response)
            return None

        except Exception as e:
            logger.error("Erreur création DM avec %s: %s", user_id, e)
            return None

    async def _set_direct_room(self, user_id: str, room_id: str):
        """Marque un salon comme conversation directe (m.direct)."""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            url = f"{self.homeserver}/_matrix/client/v3/user/{self.user_id}/account_data/m.direct"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        direct_data = await resp.json()
                    else:
                        direct_data = {}

                if user_id not in direct_data:
                    direct_data[user_id] = []
                if room_id not in direct_data[user_id]:
                    direct_data[user_id].append(room_id)

                async with session.put(url, headers=headers, json=direct_data) as resp:
                    if resp.status == 200:
                        logger.debug("m.direct mis à jour pour %s", user_id)
                    else:
                        body = await resp.text()
                        logger.warning("Erreur mise à jour m.direct: %s - %s", resp.status, body)

        except Exception as e:
            logger.warning("Impossible de mettre à jour m.direct pour %s: %s", user_id, e)

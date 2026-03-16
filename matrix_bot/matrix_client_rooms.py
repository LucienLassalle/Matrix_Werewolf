"""Mixins pour la gestion des salons Matrix."""

from __future__ import annotations

import logging
from typing import Optional, List

from nio import RoomVisibility, RoomPreset

logger = logging.getLogger(__name__)


class MatrixClientRoomsMixin:
    """Helpers de creation et gestion de salons."""

    async def create_room(
        self,
        name: str,
        topic: str,
        is_public: bool = False,
        invite_users: List[str] = None,
        space_id: str = None,
    ) -> Optional[str]:
        """Cree un salon Matrix."""
        if not self.client:
            logger.error("Client non connecté")
            return None

        try:
            vis = RoomVisibility.public if is_public else RoomVisibility.private
            pre = RoomPreset.public_chat if is_public else RoomPreset.private_chat

            room_config = {
                "name": name,
                "topic": topic,
                "visibility": vis,
                "preset": pre,
                "invite": invite_users or [],
            }

            if space_id:
                room_config["initial_state"] = [
                    {
                        "type": "m.space.parent",
                        "state_key": space_id,
                        "content": {
                            "canonical": True,
                            "via": [self.homeserver.replace("https://", "").replace("http://", "")],
                        },
                    }
                ]

            response = await self.client.room_create(**room_config)

            if hasattr(response, 'room_id'):
                logger.info("Salon créé: %s (%s)", response.room_id, name)

                if space_id:
                    await self.add_room_to_space(space_id, response.room_id)

                return response.room_id
            logger.error("Erreur création salon: %s", response)
            return None

        except Exception as e:
            logger.error("Erreur création salon: %s", e)
            return None

    async def add_room_to_space(self, space_id: str, room_id: str):
        """Ajoute un salon a un espace."""
        try:
            await self.client.room_put_state(
                space_id,
                "m.space.child",
                {
                    "via": [self.homeserver.replace("https://", "").replace("http://", "")],
                    "suggested": True,
                },
                state_key=room_id,
            )
            logger.info("Salon %s ajouté à l'espace %s", room_id, space_id)
        except Exception as e:
            logger.error("Erreur ajout au space: %s", e)

    async def remove_room_from_space(self, space_id: str, room_id: str):
        """Retire un salon d'un espace (supprime le lien m.space.child)."""
        try:
            await self.client.room_put_state(
                space_id,
                "m.space.child",
                {},
                state_key=room_id,
            )
            logger.info("Salon %s retiré de l'espace %s", room_id, space_id)
        except Exception as e:
            logger.error("Erreur retrait du space: %s", e)

    async def invite_user(self, room_id: str, user_id: str):
        """Invite un utilisateur dans un salon."""
        if not self.client:
            return

        try:
            await self.client.room_invite(room_id, user_id)
            logger.info("Utilisateur %s invité dans %s", user_id, room_id)
        except Exception as e:
            logger.error("Erreur invitation: %s", e)

    async def kick_user(self, room_id: str, user_id: str, reason: str = ""):
        """Expulse un utilisateur d'un salon."""
        if not self.client:
            return

        try:
            await self.client.room_kick(room_id, user_id, reason)
            logger.info("Utilisateur %s expulsé de %s", user_id, room_id)
        except Exception as e:
            logger.error("Erreur expulsion: %s", e)

    async def delete_room(self, room_id: str):
        """Supprime un salon (le bot quitte le salon)."""
        if not self.client:
            return

        try:
            await self.client.room_leave(room_id)
            logger.info("Salon %s quitté", room_id)
        except Exception as e:
            logger.error("Erreur suppression salon: %s", e)

    async def clear_room_history(self, room_id: str):
        """Nettoie l'historique d'un salon (approximatif)."""
        if not self.client:
            return

        try:
            await self.send_message(
                room_id,
                "═══════════════════════════════\n"
                "🔄 NOUVELLE PARTIE\n"
                "═══════════════════════════════",
            )
        except Exception as e:
            logger.error("Erreur clear historique: %s", e)

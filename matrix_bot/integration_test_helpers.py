"""Helpers pour les tests d'integration Matrix."""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp
from nio import AsyncClient

logger = logging.getLogger(__name__)


class IntegrationTestHelpersMixin:
    """Helpers utilitaires pour les tests d'integration."""

    def _ok(self, label: str):
        self._passed += 1
        logger.info("  ✅ %s", label)

    def _fail(self, label: str, detail: str = ""):
        self._failed += 1
        msg = f"  ❌ {label}" + (f" — {detail}" if detail else "")
        self._errors.append(msg)
        logger.error(msg)

    async def _connect_test_client(self, user_id: str, token: str) -> Optional[AsyncClient]:
        """Connecte un compte de test et retourne le client."""
        try:
            client = AsyncClient(self.homeserver, user_id)
            client.access_token = token
            resp = await client.whoami()
            if resp and hasattr(resp, "user_id"):
                logger.info("  Compte de test connecté : %s", resp.user_id)
                return client
            logger.error("  whoami échoué pour %s", user_id)
            return None
        except Exception as e:
            logger.error("  Connexion échouée pour %s: %s", user_id, e)
            return None

    async def _connect_all(self) -> bool:
        """Connecte les deux comptes de test."""
        self.client1 = await self._connect_test_client(self.user1_id, self.user1_token)
        self.client2 = await self._connect_test_client(self.user2_id, self.user2_token)
        return self.client1 is not None and self.client2 is not None

    async def _disconnect_all(self):
        for c in (self.client1, self.client2):
            if c:
                await c.close()
        self.client1 = self.client2 = None

    async def _send_as(self, client: AsyncClient, room_id: str, body: str) -> bool:
        """Envoie un message depuis un client de test."""
        try:
            resp = await client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": body},
            )
            return hasattr(resp, "event_id")
        except Exception as e:
            logger.debug("  _send_as error: %s", e)
            return False

    async def _join_as(self, client: AsyncClient, room_id: str) -> bool:
        """Rejoint un salon depuis un client de test."""
        try:
            resp = await client.join(room_id)
            return hasattr(resp, "room_id")
        except Exception as e:
            logger.debug("  _join_as error: %s", e)
            return False

    async def _read_room_history(self, token: str, room_id: str, search_text: str, limit: int = 10) -> bool:
        """Lit l'historique d'un salon via l'API REST et cherche search_text."""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            url = (
                f"{self.homeserver}/_matrix/client/v3/rooms/{room_id}"
                f"/messages?dir=b&limit={limit}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for ev in data.get("chunk", []):
                            body = ev.get("content", {}).get("body", "")
                            if search_text in body:
                                return True
            return False
        except Exception as e:
            logger.debug("  _read_room_history error: %s", e)
            return False

    async def _read_room_history_detail(
        self,
        token: str,
        room_id: str,
        search_text: str,
        limit: int = 10,
    ) -> Optional[dict]:
        """Comme _read_room_history mais retourne l'event complet."""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            url = (
                f"{self.homeserver}/_matrix/client/v3/rooms/{room_id}"
                f"/messages?dir=b&limit={limit}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for ev in data.get("chunk", []):
                            body = ev.get("content", {}).get("body", "")
                            if search_text in body:
                                return ev
            return None
        except Exception:
            return None

    async def _sync_find_message(
        self,
        client: AsyncClient,
        room_id: str,
        search_text: str,
        timeout: int = 5000,
    ) -> bool:
        """Sync un client et cherche search_text dans room_id."""
        try:
            sync_resp = await client.sync(timeout=timeout, full_state=False)
            if not sync_resp or not hasattr(sync_resp, "rooms"):
                return False
            join_rooms = sync_resp.rooms.join if hasattr(sync_resp.rooms, "join") else {}
            if room_id not in join_rooms:
                return False
            room_data = join_rooms[room_id]
            timeline = room_data.timeline.events if hasattr(room_data, "timeline") else []
            for event in timeline:
                if search_text in getattr(event, "body", ""):
                    return True
            return False
        except Exception as e:
            logger.debug("  _sync_find_message error: %s", e)
            return False

    async def _cleanup_room(self, room_id: str, space_id: str = None):
        """Supprime un salon de test (retirer du space + kick + leave + forget)."""
        if not room_id:
            return
        try:
            if space_id:
                await self.bot.remove_room_from_space(space_id, room_id)
            members = await self.bot.get_room_members(room_id)
            for mid in members:
                if mid != self.bot.user_id:
                    try:
                        await self.bot.kick_user(room_id, mid, "Test terminé")
                    except Exception:
                        pass
            await self.bot.delete_room(room_id)
            if self.bot.client:
                try:
                    await self.bot.client.room_forget(room_id)
                except Exception:
                    pass
            for c in (self.client1, self.client2):
                if c:
                    try:
                        await c.room_forget(room_id)
                    except Exception:
                        pass
        except Exception:
            pass

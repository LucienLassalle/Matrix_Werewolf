"""Mixins pour la persistance des salons Matrix."""

from __future__ import annotations

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GameDatabaseRoomsMixin:
    """Gestion des salons Matrix (crash-safe)."""

    def save_room_state(self, rooms: Dict[str, Optional[str]]):
        """Sauvegarde les IDs des salons Matrix (persistante en cas de crash)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM room_state")
        for key, room_id in rooms.items():
            if room_id:
                cursor.execute(
                    "INSERT INTO room_state (key, room_id) VALUES (?, ?)",
                    (key, room_id),
                )
        self.conn.commit()
        logger.info(f"Etat des salons sauvegarde ({len(rooms)} entrees)")

    def load_room_state(self) -> Dict[str, str]:
        """Charge les IDs des salons depuis la BDD."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, room_id FROM room_state")
        rows = cursor.fetchall()
        rooms = {row['key']: row['room_id'] for row in rows}
        if rooms:
            logger.info(f"{len(rooms)} salon(s) restaures depuis la BDD")
        return rooms

    def clear_room_state(self):
        """Efface les IDs des salons."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM room_state")
        self.conn.commit()
        logger.info("Etat des salons efface")

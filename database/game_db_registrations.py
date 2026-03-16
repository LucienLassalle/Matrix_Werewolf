"""Mixins pour inscriptions persistantes."""

from __future__ import annotations

from datetime import datetime
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class GameDatabaseRegistrationsMixin:
    """Gestion des inscriptions crash-safe."""

    def save_registration(self, user_id: str, display_name: str):
        """Sauvegarde une inscription joueur (persistante en cas de crash)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO registrations (user_id, display_name, registered_at)
            VALUES (?, ?, ?)
        """,
            (user_id, display_name, datetime.now().isoformat()),
        )
        self.conn.commit()
        logger.info(f"Inscription sauvegardee en BDD: {display_name} ({user_id})")

    def remove_registration(self, user_id: str):
        """Supprime une inscription joueur."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM registrations WHERE user_id = ?", (user_id,))
        self.conn.commit()
        logger.info(f"Inscription supprimee: {user_id}")

    def load_registrations(self) -> Dict[str, str]:
        """Charge toutes les inscriptions depuis la BDD."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, display_name FROM registrations")
        rows = cursor.fetchall()
        registrations = {row['user_id']: row['display_name'] for row in rows}
        if registrations:
            logger.info(
                f"{len(registrations)} inscription(s) restauree(s) depuis la BDD"
            )
        return registrations

    def clear_registrations(self):
        """Efface toutes les inscriptions (apres demarrage de partie ou annulation)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM registrations")
        self.conn.commit()
        logger.info("Inscriptions effacees de la BDD")

    def has_active_game(self) -> bool:
        """Verifie si une partie etait en cours (pour detection de crash)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT phase FROM game_state WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            return False
        return row['phase'] not in ('SETUP', 'ENDED')

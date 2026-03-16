"""Mixins pour les stats de la base de donnees."""

from __future__ import annotations

from typing import Dict, Optional


class GameDatabaseStatsMixin:
    """Stats et leaderboard."""

    def get_leaderboard(self, limit: int = 10) -> list:
        """Recupere le top des joueurs."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT user_id, pseudo, total_games, total_wins, total_deaths,
                   CAST(total_wins AS FLOAT) / total_games * 100 as win_rate
            FROM leaderboard
            WHERE total_games > 0
            ORDER BY total_wins DESC, win_rate DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_role_stats(self) -> list:
        """Recupere les statistiques par role."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT role_type,
                   COUNT(*) as games_played,
                   SUM(won) as wins,
                   CAST(SUM(won) AS FLOAT) / COUNT(*) * 100 as win_rate
            FROM player_stats
            GROUP BY role_type
            ORDER BY win_rate DESC
        """
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_player_stats(self, user_id: str) -> Optional[Dict]:
        """Recupere les statistiques d'un joueur."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT * FROM leaderboard WHERE user_id = ?
        """,
            (user_id,),
        )

        global_stats = cursor.fetchone()
        if not global_stats:
            return None

        cursor.execute(
            """
            SELECT role_type, COUNT(*) as games, SUM(won) as wins
            FROM player_stats
            WHERE user_id = ?
            GROUP BY role_type
            ORDER BY games DESC
        """,
            (user_id,),
        )

        role_stats = [dict(row) for row in cursor.fetchall()]

        return {
            'global': dict(global_stats),
            'roles': role_stats,
        }

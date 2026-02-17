"""Tests du LeaderboardManager.

Couvre :
- Leaderboard vide
- Message de leaderboard formaté
- Stats par rôle vides
- Stats d'un joueur vides
- _format_role_name avec RoleType valide et invalide
"""

import pytest
from unittest.mock import MagicMock
from game.leaderboard import LeaderboardManager, _format_role_name
from models.enums import RoleType


class TestFormatRoleName:
    def test_known_role(self):
        """Un RoleType connu retourne le nom d'affichage."""
        name = _format_role_name("loup_garou")
        assert name  # Non vide
        assert "_" not in name or name[0].isupper()  # Formaté

    def test_unknown_role(self):
        """Un rôle inconnu retourne un fallback title-case."""
        name = _format_role_name("super_heros_inconnu")
        assert name == "Super Heros Inconnu"


class TestLeaderboardManager:
    def _make_manager(self, leaderboard=None, role_stats=None, player_stats=None):
        db = MagicMock()
        db.get_leaderboard.return_value = leaderboard or []
        db.get_role_stats.return_value = role_stats or []
        db.get_player_stats.return_value = player_stats
        return LeaderboardManager(db)

    def test_empty_leaderboard(self):
        mgr = self._make_manager()
        msg = mgr.get_leaderboard_message()
        assert "Aucune partie" in msg

    def test_leaderboard_with_data(self):
        data = [
            {"pseudo": "Alice", "total_games": 10, "total_wins": 7, "win_rate": 70.0},
            {"pseudo": "Bob", "total_games": 8, "total_wins": 4, "win_rate": 50.0},
        ]
        mgr = self._make_manager(leaderboard=data)
        msg = mgr.get_leaderboard_message()
        assert "Alice" in msg
        assert "Bob" in msg
        assert "🥇" in msg
        assert "🥈" in msg

    def test_leaderboard_medals(self):
        data = [
            {"pseudo": f"P{i}", "total_games": 10, "total_wins": 10 - i, "win_rate": (10 - i) * 10.0}
            for i in range(5)
        ]
        mgr = self._make_manager(leaderboard=data)
        msg = mgr.get_leaderboard_message()
        assert "🥇" in msg
        assert "🥈" in msg
        assert "🥉" in msg
        # 4th and 5th don't have medals
        assert "4." in msg

    def test_empty_role_stats(self):
        mgr = self._make_manager()
        msg = mgr.get_role_stats_message()
        assert "Aucune donnée" in msg

    def test_role_stats_with_data(self):
        data = [
            {"role_type": "loup_garou", "games_played": 20, "wins": 12, "win_rate": 60.0},
        ]
        mgr = self._make_manager(role_stats=data)
        msg = mgr.get_role_stats_message()
        assert "12/20" in msg

    def test_empty_player_stats(self):
        mgr = self._make_manager(player_stats=None)
        msg = mgr.get_player_stats_message("u1", "Alice")
        assert "Aucune partie" in msg

    def test_player_stats_with_data(self):
        data = {
            "global": {"total_games": 5, "total_wins": 3, "total_deaths": 2},
            "roles": [
                {"role_type": "sorciere", "games": 3, "wins": 2},
            ],
        }
        mgr = self._make_manager(player_stats=data)
        msg = mgr.get_player_stats_message("u1", "Alice")
        assert "Alice" in msg
        assert "5" in msg  # total_games
        assert "3" in msg  # total_wins

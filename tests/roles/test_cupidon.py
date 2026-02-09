"""Tests complets du rôle Cupidon.

Couvre :
- Cupidon ne peut marier que pendant la première nuit
- Le pouvoir est consommé (même sans action) après la nuit 1
- Le Cupidon mort ne peut plus agir
- Pas de crash si Cupidon n'est pas dans la partie
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def make_game(*specs) -> GameManager:
    """Crée une partie avec les joueurs/rôles donnés."""
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


# ═══════════════════════════════════════════════════════════
#  Mariage limité à la première nuit
# ═══════════════════════════════════════════════════════════

class TestCupidonFirstNightOnly:
    """Cupidon ne peut marier que pendant la nuit 1."""

    def test_power_consumed_after_night_1(self):
        game = make_game(
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        game._auto_resolve_cupidon()
        assert game.players["c1"].role.has_used_power is True

    def test_cannot_marry_after_night_1(self):
        game = make_game(
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["c1"].role.has_used_power = True

        result = game.players["c1"].role.perform_action(
            game, ActionType.MARRY, target1=game.players["a1"], target2=game.players["b1"]
        )
        assert not result["success"]

    def test_can_marry_during_night_1(self):
        game = make_game(
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        assert game.players["c1"].role.has_used_power is False

        result = game.players["c1"].role.perform_action(
            game, ActionType.MARRY, target1=game.players["a1"], target2=game.players["b1"]
        )
        assert result["success"]
        assert game.players["c1"].role.has_used_power is True

    def test_no_cupidon_no_crash(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        game._auto_resolve_cupidon()  # Ne doit pas planter

    def test_dead_cupidon_not_auto_resolved(self):
        """Un Cupidon mort n'est pas auto-résolu (is_alive check)."""
        game = make_game(
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        game.players["c1"].is_alive = False

        game._auto_resolve_cupidon()
        # Cupidon mort → pas de résolution
        assert game.players["c1"].role.has_used_power is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

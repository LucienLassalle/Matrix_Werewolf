"""Tests complets du rôle Garde.

Couvre :
- Le garde protège le maire pendant la nuit
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
#  Protection du maire
# ═══════════════════════════════════════════════════════════

class TestGardeProtectsMayor:
    """Le garde peut protéger le maire contre les loups."""

    def test_guard_saves_mayor_from_wolves(self):
        game = make_game(
            ("Garde", "g1", RoleType.GARDE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        game.players["m1"].is_mayor = True
        game.current_turn = 1

        result = game.players["g1"].role.perform_action(
            game, ActionType.PROTECT, game.players["m1"]
        )
        assert result["success"]

        game.pending_wolf_kill = "m1"
        night_result = game.resolve_night()

        assert game.players["m1"].is_alive
        assert game.players["m1"].is_mayor


class TestGardeDaySelection:
    """Le garde peut préparer sa protection en journée."""

    def test_day_selection_can_be_changed_before_night(self):
        game = make_game(
            ("Garde", "g1", RoleType.GARDE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        garde = game.players["g1"].role
        alice = game.players["a1"]
        bob = game.players["b1"]

        game.phase = GamePhase.DAY
        r1 = garde.perform_action(game, ActionType.PROTECT, alice)
        r2 = garde.perform_action(game, ActionType.PROTECT, bob)
        assert r1["success"]
        assert r2["success"]
        assert not alice.is_protected
        assert not bob.is_protected

        game.phase = GamePhase.NIGHT
        garde.on_night_start(game)

        assert not alice.is_protected
        assert bob.is_protected
        assert garde.last_protected is bob
        assert garde.has_used_power_tonight


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

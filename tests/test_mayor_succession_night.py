"""Succession du maire pendant la nuit."""

from models.enums import ActionType, RoleType
from tests.mayor_cupidon_helpers import make_game


class TestNightMayorSuccession:
    """Le maire tue pendant la nuit declenche _pending_mayor_succession."""

    def test_wolf_kills_mayor_triggers_succession(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        game.vote_manager.add_wolf_vote(game.players["w1"], mayor)
        result = game.end_night()
        assert result["success"]
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor
        assert mayor.is_mayor is False

    def test_sorciere_poison_mayor_triggers_succession(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Sorc", "s1", RoleType.SORCIERE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        sorc = game.players["s1"]
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["a1"])
        sorc.role.perform_action(game, ActionType.POISON, mayor)
        game.action_manager.register_action(sorc, ActionType.POISON, mayor)
        game.end_night()
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor

    def test_loup_blanc_kills_mayor_triggers_succession(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("LBlanc", "wb1", RoleType.LOUP_BLANC),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        loup_blanc = game.players["wb1"]
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["a1"])
        game.vote_manager.add_wolf_vote(loup_blanc, game.players["a1"])
        loup_blanc.role.night_count = 1
        loup_blanc.role.on_night_start(game)
        r = loup_blanc.role.perform_action(game, ActionType.KILL, mayor)
        assert r["success"]
        game.action_manager.register_action(loup_blanc, ActionType.KILL, mayor)
        game.end_night()
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor

    def test_no_succession_if_mayor_survives(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["m1"].is_mayor = True
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["a1"])
        game.end_night()
        assert game.players["m1"].is_alive
        assert game._pending_mayor_succession is None

    def test_mayor_lover_cascade_triggers_succession(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Lover", "l1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        lover = game.players["l1"]
        mayor.lover = lover
        lover.lover = mayor
        game.vote_manager.add_wolf_vote(game.players["w1"], lover)
        game.end_night()
        assert not lover.is_alive
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor


class TestEndNightMayorIntegration:
    """resolve_night() detecte correctement la mort du maire."""

    def test_resolve_night_mayor_killed_by_wolves(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["m1"].is_mayor = True
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["m1"])
        result = game.resolve_night()
        assert "m1" in result["deaths"]
        assert game._pending_mayor_succession is not None
        assert game.players["m1"].is_mayor is False

"""Tests du role Pyromane."""

from models.enums import ActionType, GamePhase, RoleType
from roles import RoleFactory
from game.game_manager import GameManager


def make_game(*specs) -> GameManager:
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestPyromane:
    def test_pyromane_soak_then_ignite(self):
        game = make_game(
            ("Pyromane", "p1", RoleType.PYROMANE),
            ("Cible1", "t1", RoleType.VILLAGEOIS),
            ("Cible2", "t2", RoleType.VILLAGEOIS),
            ("Alice", "v1", RoleType.VILLAGEOIS),
            ("Bob", "v2", RoleType.VILLAGEOIS),
        )
        pyro = game.players["p1"]
        t1 = game.players["t1"]
        t2 = game.players["t2"]

        r1 = pyro.role.perform_action(game, ActionType.PYROMANE_SOAK, t1)
        assert r1["success"]
        game.action_manager.register_action(pyro, ActionType.PYROMANE_SOAK, t1)
        game.action_manager.execute_night_actions(game)

        game.action_manager.reset()
        pyro.role.on_night_start(game)

        r2 = pyro.role.perform_action(game, ActionType.PYROMANE_SOAK, t2)
        assert r2["success"]
        game.action_manager.register_action(pyro, ActionType.PYROMANE_SOAK, t2)

        game.action_manager.execute_night_actions(game)

        game.action_manager.reset()
        pyro.role.on_night_start(game)

        r3 = pyro.role.perform_action(game, ActionType.PYROMANE_IGNITE)
        assert r3["success"]
        game.action_manager.register_action(pyro, ActionType.PYROMANE_IGNITE)

        night_result = game.action_manager.execute_night_actions(game)
        dead_ids = {p.user_id for p in night_result["deaths"]}
        assert t1.user_id in dead_ids
        assert t2.user_id in dead_ids

    def test_pyromane_two_soaks_per_night(self):
        game = make_game(
            ("Pyromane", "p1", RoleType.PYROMANE),
            ("Cible1", "t1", RoleType.VILLAGEOIS),
            ("Cible2", "t2", RoleType.VILLAGEOIS),
            ("Cible3", "t3", RoleType.VILLAGEOIS),
            ("Alice", "v1", RoleType.VILLAGEOIS),
            ("Bob", "v2", RoleType.VILLAGEOIS),
        )
        pyro = game.players["p1"]
        t1 = game.players["t1"]
        t2 = game.players["t2"]
        t3 = game.players["t3"]

        ok = pyro.role.perform_action(game, ActionType.PYROMANE_SOAK, t1)
        assert ok["success"]
        ok2 = pyro.role.perform_action(game, ActionType.PYROMANE_SOAK, t2)
        assert ok2["success"]
        fail = pyro.role.perform_action(game, ActionType.PYROMANE_SOAK, t3)
        assert not fail["success"]

    def test_pyromane_cannot_ignite_after_soaking_same_night(self):
        game = make_game(
            ("Pyromane", "p1", RoleType.PYROMANE),
            ("Cible1", "t1", RoleType.VILLAGEOIS),
            ("Cible2", "t2", RoleType.VILLAGEOIS),
            ("Alice", "v1", RoleType.VILLAGEOIS),
            ("Bob", "v2", RoleType.VILLAGEOIS),
        )
        pyro = game.players["p1"]
        t1 = game.players["t1"]

        ok = pyro.role.perform_action(game, ActionType.PYROMANE_SOAK, t1)
        assert ok["success"]

        fail = pyro.role.perform_action(game, ActionType.PYROMANE_IGNITE)
        assert not fail["success"]

    def test_pyromane_ignition_ignores_guard(self):
        game = make_game(
            ("Pyromane", "p1", RoleType.PYROMANE),
            ("Garde", "g1", RoleType.GARDE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "v1", RoleType.VILLAGEOIS),
            ("Bob", "v2", RoleType.VILLAGEOIS),
        )
        pyro = game.players["p1"]
        guard = game.players["g1"]
        target = game.players["t1"]

        pyro.role.perform_action(game, ActionType.PYROMANE_SOAK, target)
        game.action_manager.register_action(pyro, ActionType.PYROMANE_SOAK, target)
        game.action_manager.execute_night_actions(game)

        game.action_manager.reset()
        pyro.role.on_night_start(game)

        guard.role.perform_action(game, ActionType.PROTECT, target)
        game.action_manager.register_action(guard, ActionType.PROTECT, target)

        ok = pyro.role.perform_action(game, ActionType.PYROMANE_IGNITE)
        assert ok["success"]
        game.action_manager.register_action(pyro, ActionType.PYROMANE_IGNITE)

        night_result = game.action_manager.execute_night_actions(game)
        assert target in night_result["deaths"]

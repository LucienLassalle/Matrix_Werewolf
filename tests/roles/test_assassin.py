"""Tests du role Assassin."""

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


class TestAssassinNightKill:
    def test_assassin_kill_applied_at_night_resolution(self):
        game = make_game(
            ("Assassin", "a1", RoleType.ASSASSIN),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "v1", RoleType.VILLAGEOIS),
            ("Bob", "v2", RoleType.VILLAGEOIS),
            ("Eve", "v3", RoleType.VILLAGEOIS),
        )
        assassin = game.players["a1"]
        target = game.players["t1"]

        result = assassin.role.perform_action(game, ActionType.ASSASSIN_KILL, target)
        assert result["success"]
        game.action_manager.register_action(assassin, ActionType.ASSASSIN_KILL, target)

        night_result = game.action_manager.execute_night_actions(game)
        assert not target.is_alive
        assert target in night_result["deaths"]

    def test_assassin_single_kill_per_night(self):
        game = make_game(
            ("Assassin", "a1", RoleType.ASSASSIN),
            ("Cible1", "t1", RoleType.VILLAGEOIS),
            ("Cible2", "t2", RoleType.VILLAGEOIS),
            ("Alice", "v1", RoleType.VILLAGEOIS),
            ("Bob", "v2", RoleType.VILLAGEOIS),
        )
        assassin = game.players["a1"]
        t1 = game.players["t1"]
        t2 = game.players["t2"]

        ok = assassin.role.perform_action(game, ActionType.ASSASSIN_KILL, t1)
        assert ok["success"]
        fail = assassin.role.perform_action(game, ActionType.ASSASSIN_KILL, t2)
        assert not fail["success"]

    def test_assassin_respects_guard_protection(self):
        game = make_game(
            ("Assassin", "a1", RoleType.ASSASSIN),
            ("Garde", "g1", RoleType.GARDE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "v1", RoleType.VILLAGEOIS),
            ("Bob", "v2", RoleType.VILLAGEOIS),
        )
        assassin = game.players["a1"]
        guard = game.players["g1"]
        target = game.players["t1"]

        guard.role.perform_action(game, ActionType.PROTECT, target)
        game.action_manager.register_action(guard, ActionType.PROTECT, target)

        result = assassin.role.perform_action(game, ActionType.ASSASSIN_KILL, target)
        assert result["success"]
        game.action_manager.register_action(assassin, ActionType.ASSASSIN_KILL, target)

        night_result = game.action_manager.execute_night_actions(game)
        assert target.is_alive
        assert target not in night_result["deaths"]

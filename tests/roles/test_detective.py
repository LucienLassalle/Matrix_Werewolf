"""Tests du role Detective."""

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


class TestDetective:
    def test_detective_same_team(self):
        game = make_game(
            ("Detective", "d1", RoleType.DETECTIVE),
            ("A", "a1", RoleType.VILLAGEOIS),
            ("B", "b1", RoleType.VILLAGEOIS),
            ("C", "c1", RoleType.VILLAGEOIS),
            ("D", "d2", RoleType.VILLAGEOIS),
        )
        det = game.players["d1"]
        a = game.players["a1"]
        b = game.players["b1"]

        result = det.role.perform_action(game, ActionType.DETECTIVE_CHECK, None, target1=a, target2=b)
        assert result["success"]
        assert result["same_team"] is True

    def test_detective_diff_team(self):
        game = make_game(
            ("Detective", "d1", RoleType.DETECTIVE),
            ("A", "a1", RoleType.VILLAGEOIS),
            ("B", "b1", RoleType.LOUP_GAROU),
            ("C", "c1", RoleType.VILLAGEOIS),
            ("D", "d2", RoleType.VILLAGEOIS),
        )
        det = game.players["d1"]
        a = game.players["a1"]
        b = game.players["b1"]

        result = det.role.perform_action(game, ActionType.DETECTIVE_CHECK, None, target1=a, target2=b)
        assert result["success"]
        assert result["same_team"] is False

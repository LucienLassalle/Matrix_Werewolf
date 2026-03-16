"""Tests de contraintes pour Assassin/Pyromane."""

from models.enums import RoleType
from roles import RoleFactory
from game.game_manager import GameManager


def make_game(players: int) -> GameManager:
    game = GameManager()
    for i in range(players):
        game.add_player(f"P{i}", f"p{i}")
    return game


class TestNeutralEvilRatioConstraints:
    def test_assassin_pyromane_requires_8_players(self):
        game = make_game(7)
        result = game.set_roles({
            RoleType.ASSASSIN: 1,
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 2,
        })
        assert not result["success"]

    def test_ratio_neutral_evil_out_of_range_fails(self):
        game = make_game(8)
        result = game.set_roles({
            RoleType.ASSASSIN: 1,
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        assert not result["success"]

    def test_ratio_neutral_evil_in_range_ok(self):
        game = make_game(8)
        result = game.set_roles({
            RoleType.ASSASSIN: 1,
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 2,
        })
        assert result["success"]

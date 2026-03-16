"""Tests pour les conditions de victoire avec neutres."""

from models.enums import RoleType, Team
from roles import RoleFactory
from game.game_manager import GameManager


def make_game(*specs) -> GameManager:
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    return game


class TestNeutralVictoryRules:
    def test_two_neutrals_no_winner(self):
        game = make_game(
            ("Assassin", "a1", RoleType.ASSASSIN),
            ("Pyromane", "p1", RoleType.PYROMANE),
        )
        assert game.check_win_condition() is None

    def test_neutral_and_wolf_wolves_win(self):
        game = make_game(
            ("Pyromane", "p1", RoleType.PYROMANE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        assert game.check_win_condition() == Team.MECHANT

    def test_neutral_and_villager_village_wins(self):
        game = make_game(
            ("Assassin", "a1", RoleType.ASSASSIN),
            ("Village", "v1", RoleType.VILLAGEOIS),
        )
        assert game.check_win_condition() == Team.GENTIL

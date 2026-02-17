"""Tests du rôle Médium.

Couvre :
- Peut parler avec un joueur mort
- Ne peut pas cibler un joueur vivant
- Un seul mort par nuit
- Pouvoir réinitialisé chaque nuit
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


def make_game(*specs) -> GameManager:
    game = GameManager(db_path=":memory:")
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestMedium:
    """Tests du Médium."""

    def test_speak_with_dead(self):
        """Le Médium peut parler avec un joueur mort."""
        game = make_game(
            ("Médium", "m1", RoleType.MEDIUM),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        game.players["a1"].kill()
        result = game.players["m1"].role.perform_action(
            game, ActionType.SPEAK_WITH_DEAD, game.players["a1"]
        )
        assert result["success"]
        assert "Alice" in result["message"]

    def test_cannot_speak_with_alive(self):
        """Le Médium ne peut pas cibler un joueur vivant."""
        game = make_game(
            ("Médium", "m1", RoleType.MEDIUM),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        result = game.players["m1"].role.perform_action(
            game, ActionType.SPEAK_WITH_DEAD, game.players["a1"]
        )
        assert not result["success"]

    def test_one_per_night(self):
        """Le Médium ne peut parler qu'avec un mort par nuit."""
        game = make_game(
            ("Médium", "m1", RoleType.MEDIUM),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        game.players["a1"].kill()
        game.players["b1"].kill()

        r1 = game.players["m1"].role.perform_action(
            game, ActionType.SPEAK_WITH_DEAD, game.players["a1"]
        )
        assert r1["success"]
        assert not game.players["m1"].role.can_perform_action(ActionType.SPEAK_WITH_DEAD)

    def test_power_resets_each_night(self):
        """Le pouvoir se réinitialise au début de chaque nuit."""
        game = make_game(
            ("Médium", "m1", RoleType.MEDIUM),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        game.players["a1"].kill()
        game.players["m1"].role.perform_action(
            game, ActionType.SPEAK_WITH_DEAD, game.players["a1"]
        )
        game.players["m1"].role.on_night_start(game)
        assert not game.players["m1"].role.has_used_power_tonight

    def test_team(self):
        role = RoleFactory.create_role(RoleType.MEDIUM)
        assert role.team == Team.GENTIL

    def test_can_act_at_night(self):
        role = RoleFactory.create_role(RoleType.MEDIUM)
        assert role.can_act_at_night()

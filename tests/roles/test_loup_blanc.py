"""Tests du rôle Loup-Blanc.

Couvre :
- Kill uniquement les nuits paires (night_count % 2 == 0)
- Pas de kill la première nuit
- Peut cibler des loups
- Ne peut pas se cibler lui-même
- Compteur de nuits
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


class TestLoupBlanc:
    """Tests du Loup-Blanc."""

    def test_cannot_kill_first_night(self):
        """Le Loup-Blanc ne peut pas tuer la première nuit (nuit 1 = impaire)."""
        game = make_game(
            ("LoupBlanc", "lb1", RoleType.LOUP_BLANC),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lb = game.players["lb1"]
        lb.role.on_night_start(game)  # night_count = 1
        assert not lb.role.can_kill_tonight
        assert not lb.role.can_perform_action(ActionType.KILL)

    def test_can_kill_second_night(self):
        """Le Loup-Blanc peut tuer la deuxième nuit (nuit 2 = paire)."""
        game = make_game(
            ("LoupBlanc", "lb1", RoleType.LOUP_BLANC),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lb = game.players["lb1"]
        lb.role.on_night_start(game)  # night 1
        lb.role.on_night_start(game)  # night 2
        assert lb.role.can_kill_tonight
        assert lb.role.can_perform_action(ActionType.KILL)

    def test_kill_alternates(self):
        """Nuit 3 → non, Nuit 4 → oui."""
        game = make_game(
            ("LoupBlanc", "lb1", RoleType.LOUP_BLANC),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lb = game.players["lb1"]
        for _ in range(3):
            lb.role.on_night_start(game)
        assert not lb.role.can_kill_tonight  # night 3

        lb.role.on_night_start(game)  # night 4
        assert lb.role.can_kill_tonight

    def test_can_target_wolf(self):
        """Le Loup-Blanc peut cibler un autre loup."""
        game = make_game(
            ("LoupBlanc", "lb1", RoleType.LOUP_BLANC),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        lb = game.players["lb1"]
        lb.role.on_night_start(game)  # night 1
        lb.role.on_night_start(game)  # night 2

        result = lb.role.perform_action(game, ActionType.KILL, target=game.players["w1"])
        assert result["success"]

    def test_cannot_target_self(self):
        """Le Loup-Blanc ne peut pas se cibler lui-même."""
        game = make_game(
            ("LoupBlanc", "lb1", RoleType.LOUP_BLANC),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lb = game.players["lb1"]
        lb.role.on_night_start(game)
        lb.role.on_night_start(game)

        result = lb.role.perform_action(game, ActionType.KILL, target=lb)
        assert not result["success"]

    def test_one_kill_per_night(self):
        """Le Loup-Blanc ne peut tuer qu'une fois par nuit."""
        game = make_game(
            ("LoupBlanc", "lb1", RoleType.LOUP_BLANC),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lb = game.players["lb1"]
        lb.role.on_night_start(game)
        lb.role.on_night_start(game)

        result1 = lb.role.perform_action(game, ActionType.KILL, target=game.players["a1"])
        assert result1["success"]
        assert not lb.role.can_perform_action(ActionType.KILL)

    def test_team(self):
        role = RoleFactory.create_role(RoleType.LOUP_BLANC)
        assert role.team == Team.MECHANT

    def test_can_act_at_night(self):
        role = RoleFactory.create_role(RoleType.LOUP_BLANC)
        assert role.can_act_at_night()

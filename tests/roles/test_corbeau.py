"""Tests du rôle Corbeau.

Couvre :
- Ajout de 2 votes via perform_action
- Une seule utilisation par nuit  
- Reset au début de la nuit
- Cible invalide (morte ou None)
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


class TestCorbeau:
    """Tests du Corbeau."""

    def test_add_votes(self):
        """Le Corbeau ajoute +2 votes sur la cible."""
        game = make_game(
            ("Corbeau", "c1", RoleType.CORBEAU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        corbeau = game.players["c1"]
        alice = game.players["a1"]
        initial = alice.votes_against

        result = corbeau.role.perform_action(game, ActionType.ADD_VOTES, target=alice)
        assert result["success"]
        assert alice.votes_against == initial + 2

    def test_one_use_per_night(self):
        """Le Corbeau ne peut utiliser son pouvoir qu'une fois par nuit."""
        game = make_game(
            ("Corbeau", "c1", RoleType.CORBEAU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        corbeau = game.players["c1"]
        result1 = corbeau.role.perform_action(game, ActionType.ADD_VOTES, target=game.players["a1"])
        assert result1["success"]

        # Deuxième utilisation échoue
        assert not corbeau.role.can_perform_action(ActionType.ADD_VOTES)

    def test_power_reset_on_night_start(self):
        """Le pouvoir se réinitialise au début de chaque nuit."""
        game = make_game(
            ("Corbeau", "c1", RoleType.CORBEAU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        corbeau = game.players["c1"]
        corbeau.role.perform_action(game, ActionType.ADD_VOTES, target=game.players["a1"])
        assert corbeau.role.has_used_power_tonight

        corbeau.role.on_night_start(game)
        assert not corbeau.role.has_used_power_tonight
        assert corbeau.role.can_perform_action(ActionType.ADD_VOTES)

    def test_invalid_target_dead(self):
        """Impossible de cibler un joueur mort."""
        game = make_game(
            ("Corbeau", "c1", RoleType.CORBEAU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        alice = game.players["a1"]
        alice.is_alive = False

        result = game.players["c1"].role.perform_action(game, ActionType.ADD_VOTES, target=alice)
        assert not result["success"]

    def test_invalid_target_none(self):
        """Cible None doit échouer."""
        game = make_game(
            ("Corbeau", "c1", RoleType.CORBEAU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        result = game.players["c1"].role.perform_action(game, ActionType.ADD_VOTES, target=None)
        assert not result["success"]

    def test_team(self):
        role = RoleFactory.create_role(RoleType.CORBEAU)
        assert role.team == Team.GENTIL

    def test_can_act_at_night(self):
        role = RoleFactory.create_role(RoleType.CORBEAU)
        assert role.can_act_at_night()

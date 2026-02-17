"""Tests du rôle Idiot du Village.

Couvre :
- L'Idiot est gracié une fois lors d'un vote
- Après la grâce, il perd son droit de vote
- La seconde fois, il meurt normalement
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
    game.phase = GamePhase.VOTE
    return game


class TestIdiot:
    """Tests de l'Idiot du Village."""

    def test_first_vote_pardoned(self):
        """L'Idiot est gracié la première fois qu'il est voté."""
        game = make_game(
            ("Idiot", "i1", RoleType.IDIOT),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        idiot = game.players["i1"]
        assert not idiot.has_been_pardoned
        result = idiot.role.on_voted_out(game)
        assert result is True  # Sauvé
        assert idiot.has_been_pardoned
        assert idiot.is_alive

    def test_loses_vote_after_pardon(self):
        """Après la grâce, l'Idiot perd son droit de vote."""
        game = make_game(
            ("Idiot", "i1", RoleType.IDIOT),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        idiot = game.players["i1"]
        idiot.role.on_voted_out(game)
        assert not idiot.can_vote

    def test_second_vote_dies(self):
        """La seconde fois voté, l'Idiot meurt."""
        game = make_game(
            ("Idiot", "i1", RoleType.IDIOT),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        idiot = game.players["i1"]
        idiot.role.on_voted_out(game)  # First time → pardoned
        result = idiot.role.on_voted_out(game)  # Second time → dies
        assert result is False

    def test_team(self):
        role = RoleFactory.create_role(RoleType.IDIOT)
        assert role.team == Team.GENTIL

    def test_idiot_in_end_vote_phase(self):
        """Teste le flux complet: l'Idiot voté dans end_vote_phase est gracié."""
        game = make_game(
            ("Idiot", "i1", RoleType.IDIOT),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        # Tous votent pour l'Idiot
        for uid in ["w1", "a1", "b1", "e1"]:
            game.vote_manager.cast_vote(game.players[uid], game.players["i1"])
        
        result = game.end_vote_phase()
        assert result["success"]
        # L'Idiot est gracié, il est toujours vivant
        assert game.players["i1"].is_alive
        assert game.players["i1"].has_been_pardoned
        assert not game.players["i1"].can_vote

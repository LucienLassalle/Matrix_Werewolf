"""Tests du rôle Mentaliste.

Couvre :
- Prédiction positive (vote élimine un loup)  
- Prédiction négative (vote élimine un villageois)
- Prédiction neutre (pas de joueur voté)
"""

import pytest
from models.player import Player
from models.enums import RoleType, Team, GamePhase
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


class TestMentaliste:
    """Tests du Mentaliste."""

    def test_positive_prediction(self):
        """Le vote élimine un loup → 'positif'."""
        game = make_game(
            ("Mental", "m1", RoleType.MENTALISTE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        mental = game.players["m1"]
        loup = game.players["w1"]

        result = mental.role.predict_vote_outcome(game, loup)
        assert result == "positif"

    def test_negative_prediction(self):
        """Le vote élimine un villageois → 'négatif'."""
        game = make_game(
            ("Mental", "m1", RoleType.MENTALISTE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        mental = game.players["m1"]
        alice = game.players["a1"]

        result = mental.role.predict_vote_outcome(game, alice)
        assert result == "négatif"

    def test_neutral_prediction(self):
        """Pas de joueur voté → 'neutre'."""
        game = make_game(
            ("Mental", "m1", RoleType.MENTALISTE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        mental = game.players["m1"]
        result = mental.role.predict_vote_outcome(game, None)
        assert result == "neutre"

    def test_team(self):
        role = RoleFactory.create_role(RoleType.MENTALISTE)
        assert role.team == Team.GENTIL

    def test_mentaliste_on_sorciere(self):
        """La Sorcière est GENTIL → vote négatif."""
        game = make_game(
            ("Mental", "m1", RoleType.MENTALISTE),
            ("Sorc", "s1", RoleType.SORCIERE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mental = game.players["m1"]
        result = mental.role.predict_vote_outcome(game, game.players["s1"])
        assert result == "négatif"

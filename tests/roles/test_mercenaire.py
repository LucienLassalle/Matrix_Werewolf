"""Tests complets du rôle Mercenaire.

Couvre :
- Le contrat ne se valide QUE si la cible est éliminée par le vote du village
- Un kill via Dictateur/Chasseur/nuit ne valide PAS le contrat
- Le Mercenaire mort ne gagne pas même si la cible meurt ensuite
- Cible incorrecte → pas de victoire
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def make_game(*specs) -> GameManager:
    """Crée une partie avec les joueurs/rôles donnés."""
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


# ═══════════════════════════════════════════════════════════
#  Validation du contrat via voted_out
# ═══════════════════════════════════════════════════════════

class TestMercenaireVotedOut:
    """Le contrat Mercenaire se valide uniquement via le vote du village."""

    def test_vote_kill_validates_contract(self):
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        game.kill_player(game.players["t1"], voted_out=True)
        assert merc.role.has_won is True

    def test_dictateur_kill_does_not_validate(self):
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        game.kill_player(game.players["t1"], voted_out=False)
        assert merc.role.has_won is False

    def test_night_kill_does_not_validate(self):
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        game.kill_player(game.players["t1"])
        assert merc.role.has_won is False

    def test_chasseur_kill_does_not_validate(self):
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        game.kill_player(game.players["t1"], voted_out=False)
        assert merc.role.has_won is False

    def test_end_vote_phase_integration(self):
        """end_vote_phase passe bien voted_out=True à kill_player."""
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True
        game.phase = GamePhase.VOTE

        game.vote_manager.cast_vote(game.players["merc1"], game.players["t1"])
        game.vote_manager.cast_vote(game.players["a1"], game.players["t1"])
        game.vote_manager.cast_vote(game.players["b1"], game.players["t1"])

        result = game.end_vote_phase()
        assert result["success"]
        assert merc.role.has_won is True


# ═══════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════

class TestMercenaireIntegration:
    """Cas limites : mauvaise cible et Mercenaire mort."""

    def test_wrong_target_no_win(self):
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.LOUP_GAROU),
            ("Autre", "x1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        game.kill_player(game.players["x1"], voted_out=True)
        assert merc.role.has_won is False

    def test_dead_mercenaire_no_win(self):
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        game.kill_player(game.players["merc1"])
        assert not merc.is_alive

        game.kill_player(game.players["t1"], voted_out=True)
        assert merc.role.has_won is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

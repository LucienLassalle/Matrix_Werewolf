"""Tests complets du rôle Mercenaire.

Couvre :
- Le contrat ne se valide QUE si la cible est éliminée par le vote du village
- Un kill via Dictateur/Chasseur/nuit ne valide PAS le contrat
- Le Mercenaire mort ne gagne pas même si la cible meurt ensuite
- Cible incorrecte → pas de victoire
- Mort d'amoureux par cascade ne valide PAS le contrat (voted_out leak fix)
- Le Mercenaire gagne/perd avec le village après contrat complété (pas de victoire additive)
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


# ═══════════════════════════════════════════════════════════
#  Régression : voted_out ne doit PAS fuiter aux amoureux
# ═══════════════════════════════════════════════════════════

class TestMercenaireLoverCascade:
    """La mort par cascade d'amoureux ne valide PAS le contrat."""

    def test_lover_cascade_does_not_validate_contract(self):
        """Si la cible du Mercenaire est l'amoureux du joueur voté,
        la cible meurt par cascade, PAS par vote → contrat invalide."""
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Votee", "v1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        # Créer le couple : Votee + Cible (amoureux)
        game.players["v1"].lover = game.players["t1"]
        game.players["t1"].lover = game.players["v1"]

        # Voter pour Votee → il meurt, Cible meurt par cascade d'amoureux
        game.kill_player(game.players["v1"], voted_out=True)

        assert not game.players["t1"].is_alive, "La cible doit être morte (cascade)"
        assert merc.role.has_won is False, (
            "voted_out ne doit pas fuiter à l'amoureux mort par cascade"
        )

    def test_voted_target_with_lover_validates_contract(self):
        """Si la cible elle-même est votée, le contrat est validé normalement,
        même si l'amoureux meurt en cascade."""
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Amoureux", "l1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        # Couple : Cible + Amoureux
        game.players["t1"].lover = game.players["l1"]
        game.players["l1"].lover = game.players["t1"]

        # Voter pour la Cible directement
        game.kill_player(game.players["t1"], voted_out=True)

        assert merc.role.has_won is True, (
            "Le contrat doit être validé quand la cible est directement votée"
        )


# ═══════════════════════════════════════════════════════════
#  Régression : pas de victoire additive
# ═══════════════════════════════════════════════════════════

class TestMercenaireTeamBasedWin:
    """Le Mercenaire gagne/perd avec son équipe (GENTIL après contrat)."""

    def test_mercenaire_wins_with_village(self):
        """Mercenaire complète son contrat → GENTIL → village gagne → Mercenaire gagne."""
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

        # Compléter le contrat
        game.kill_player(game.players["t1"], voted_out=True)
        assert merc.role.has_won is True
        assert merc.role.team == Team.GENTIL

        # Village gagne (plus de loups)
        winner = game.check_win_condition()
        assert winner == Team.GENTIL

        # Le Mercenaire (GENTIL) est dans l'équipe gagnante
        assert merc.get_team() == winner

    def test_mercenaire_loses_when_wolves_win(self):
        """Mercenaire complète son contrat → GENTIL → loups gagnent → Mercenaire perd."""
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Loup1", "w1", RoleType.LOUP_GAROU),
            ("Loup2", "w2", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        # Compléter le contrat
        game.kill_player(game.players["t1"], voted_out=True)
        assert merc.role.has_won is True
        assert merc.role.team == Team.GENTIL

        # Tuer le reste des villageois + le Mercenaire
        game.kill_player(game.players["a1"])
        game.kill_player(game.players["merc1"])

        # Loups gagnent
        winner = game.check_win_condition()
        assert winner == Team.MECHANT

        # Le Mercenaire ne fait PAS partie de l'équipe gagnante
        assert merc.get_team() != winner

    def test_neutre_mercenaire_loses_when_village_wins(self):
        """Mercenaire ne complète PAS son contrat → reste NEUTRE → village gagne → il perd."""
        game = make_game(
            ("Mercenaire", "merc1", RoleType.MERCENAIRE),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        merc = game.players["merc1"]
        merc.target = game.players["t1"]
        merc.role.target_assigned = True

        # Tuer le loup sans passer par le vote de la cible
        game.kill_player(game.players["w1"])

        # Village gagne
        winner = game.check_win_condition()
        assert winner == Team.GENTIL

        # Le Mercenaire est NEUTRE → pas dans l'équipe gagnante
        assert merc.role.has_won is False
        assert merc.get_team() == Team.NEUTRE
        assert merc.get_team() != winner


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

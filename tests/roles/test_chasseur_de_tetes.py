"""Tests complets du rôle Chasseur de Têtes (Headhunter).

Couvre :
- Attribution d'une cible aléatoire au début de la partie (non-loup)
- Victoire solo si la cible est éliminée par le vote du village
- Le CDT mort ne gagne pas même si la cible est votée ensuite
- Cible morte autrement → rejoint l'alliance du mal (Team.MECHANT)
- Le CDT ne vote jamais avec les loups (même après alliance du mal)
- Pas d'action de nuit (can_act_at_night False)
- Sérialisation / restauration de l'état
- Condition de victoire (check_win_condition)
- Cascade d'amoureux : voted_out ne fuite pas
"""

import pytest
from unittest.mock import patch
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from roles.chasseur_de_tetes import ChasseurDeTetes
from game.game_manager import GameManager


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def make_game(*specs) -> GameManager:
    """Crée une partie avec les joueurs/rôles donnés (phase NIGHT)."""
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


# ═══════════════════════════════════════════════════════════
#  Propriétés de base du rôle
# ═══════════════════════════════════════════════════════════

class TestChasseurDeTetesBasics:
    """Propriétés fondamentales du rôle."""

    def test_role_type(self):
        role = ChasseurDeTetes()
        assert role.role_type == RoleType.CHASSEUR_DE_TETES

    def test_initial_team_neutre(self):
        role = ChasseurDeTetes()
        assert role.team == Team.NEUTRE

    def test_can_act_at_night_false(self):
        role = ChasseurDeTetes()
        assert role.can_act_at_night() is False

    def test_can_vote_with_wolves_false(self):
        role = ChasseurDeTetes()
        assert role.can_vote_with_wolves() is False

    def test_description_not_empty(self):
        role = ChasseurDeTetes()
        assert len(role.get_description()) > 0

    def test_initial_flags(self):
        role = ChasseurDeTetes()
        assert role.target_assigned is False
        assert role.target_dead_other is False
        assert role.has_won is False


# ═══════════════════════════════════════════════════════════
#  Attribution de la cible
# ═══════════════════════════════════════════════════════════

class TestTargetAssignment:
    """La cible doit être un non-loup, assignée à on_game_start."""

    def test_target_assigned_on_game_start(self):
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Dan", "d1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.role.on_game_start(game)

        assert cdt.role.target_assigned is True
        assert cdt.target is not None

    def test_target_is_not_self(self):
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Dan", "d1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.role.on_game_start(game)

        assert cdt.target != cdt

    def test_target_is_not_wolf(self):
        """Cible préférentielle = non-MECHANT."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Dan", "d1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        # Appeler plusieurs fois pour couvrir le random
        for _ in range(20):
            cdt.role.target_assigned = False
            cdt.target = None
            cdt.role.on_game_start(game)
            assert cdt.target.get_team() != Team.MECHANT

    def test_fallback_if_all_others_are_wolves(self):
        """Si tous les autres joueurs sont loups, on prend quand même une cible."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Wolf1", "w1", RoleType.LOUP_GAROU),
            ("Wolf2", "w2", RoleType.LOUP_GAROU),
            ("Wolf3", "w3", RoleType.LOUP_GAROU),
            ("Wolf4", "w4", RoleType.LOUP_GAROU),
        )
        cdt = game.players["cdt1"]
        cdt.role.on_game_start(game)

        assert cdt.role.target_assigned is True
        assert cdt.target is not None
        assert cdt.target != cdt

    def test_no_double_assignment(self):
        """on_game_start ne réassigne pas si déjà target_assigned."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Dan", "d1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.role.on_game_start(game)
        first_target = cdt.target

        cdt.role.on_game_start(game)
        assert cdt.target is first_target


# ═══════════════════════════════════════════════════════════
#  Victoire solo (cible éliminée par vote)
# ═══════════════════════════════════════════════════════════

class TestSoloVictory:
    """Le CDT gagne seul si la cible meurt par vote du village."""

    def test_vote_kill_validates_win(self):
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        game.kill_player(game.players["t1"], voted_out=True)
        assert cdt.role.has_won is True

    def test_win_condition_returns_neutre(self):
        """check_win_condition() renvoie Team.NEUTRE quand CDT a gagné."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        game.kill_player(game.players["t1"], voted_out=True)
        assert game.check_win_condition() == Team.NEUTRE

    def test_end_vote_phase_integration(self):
        """end_vote_phase passe bien voted_out=True à kill_player."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True
        game.phase = GamePhase.VOTE

        game.vote_manager.cast_vote(game.players["cdt1"], game.players["t1"])
        game.vote_manager.cast_vote(game.players["a1"], game.players["t1"])
        game.vote_manager.cast_vote(game.players["b1"], game.players["t1"])

        result = game.end_vote_phase()
        assert result["success"]
        assert cdt.role.has_won is True


# ═══════════════════════════════════════════════════════════
#  Cible morte autrement → alliance du mal
# ═══════════════════════════════════════════════════════════

class TestAllianceDuMal:
    """Si la cible meurt hors vote, CDT rejoint l'alliance du mal."""

    def test_night_kill_switches_to_mechant(self):
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        game.kill_player(game.players["t1"])  # voted_out=False par défaut
        assert cdt.role.target_dead_other is True
        assert cdt.role.team == Team.MECHANT
        assert cdt.role.has_won is False

    def test_day_kill_non_vote_switches_to_mechant(self):
        """Kill pendant le jour mais pas par vote (ex: dictateur, chasseur)."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        game.kill_player(game.players["t1"], killed_during_day=True, voted_out=False)
        assert cdt.role.target_dead_other is True
        assert cdt.role.team == Team.MECHANT

    def test_still_cannot_vote_with_wolves_after_switch(self):
        """Même en MECHANT, le CDT ne vote pas avec les loups."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        game.kill_player(game.players["t1"])
        assert cdt.role.team == Team.MECHANT
        assert cdt.role.can_vote_with_wolves() is False

    def test_wolves_win_includes_cdt_mechant(self):
        """Quand les loups gagnent et CDT est MECHANT, victoire commune."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Wolf", "w1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        # Cible meurt par loups → CDT devient MECHANT
        game.kill_player(game.players["t1"])
        assert cdt.role.team == Team.MECHANT

        # Tous les gentils morts → les loups (+ CDT MECHANT) gagnent
        game.kill_player(game.players["b1"])
        game.kill_player(game.players["e1"])

        # CDT est MECHANT, Wolf est MECHANT → pas de GENTIL vivant
        winner = game.check_win_condition()
        assert winner == Team.MECHANT


# ═══════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════

class TestEdgeCases:
    """Cas limites : CDT mort, mauvaise cible, pas de cible."""

    def test_dead_cdt_no_win(self):
        """Si le CDT est mort, voter la cible ne valide pas la victoire."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        # CDT meurt en premier
        game.kill_player(game.players["cdt1"])
        assert not cdt.is_alive

        # Ensuite sa cible est votée
        game.kill_player(game.players["t1"], voted_out=True)
        assert cdt.role.has_won is False

    def test_wrong_player_voted_no_win(self):
        """Voter un autre joueur que la cible ne valide pas la victoire."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Autre", "x1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        game.kill_player(game.players["x1"], voted_out=True)
        assert cdt.role.has_won is False

    def test_no_target_no_crash(self):
        """Si aucune cible n'a été assignée, on_player_death ne crash pas."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Dan", "d1", RoleType.VILLAGEOIS),
        )
        # Ne pas appeler on_game_start → pas de cible
        game.kill_player(game.players["a1"], voted_out=True)
        assert game.players["cdt1"].role.has_won is False


# ═══════════════════════════════════════════════════════════
#  Cascade d'amoureux
# ═══════════════════════════════════════════════════════════

class TestLoverCascade:
    """voted_out ne doit pas fuiter à l'amoureux mort par cascade."""

    def test_lover_cascade_does_not_validate_win(self):
        """Si la cible est amoureux du joueur voté, cascade ≠ vote."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Votee", "v1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        # Couple : Votee + Cible
        game.players["v1"].lover = game.players["t1"]
        game.players["t1"].lover = game.players["v1"]

        # On vote pour Votee → il meurt, Cible meurt en cascade
        game.kill_player(game.players["v1"], voted_out=True)

        assert not game.players["t1"].is_alive
        # voted_out ne fuite pas → CDT rejoint l'alliance du mal
        assert cdt.role.has_won is False
        assert cdt.role.target_dead_other is True

    def test_voted_target_with_lover_validates_win(self):
        """Si la cible elle-même est votée, la victoire est validée,
        même si l'amoureux meurt en cascade."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Amoureux", "l1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        # Couple : Cible + Amoureux
        game.players["t1"].lover = game.players["l1"]
        game.players["l1"].lover = game.players["t1"]

        game.kill_player(game.players["t1"], voted_out=True)

        assert cdt.role.has_won is True


# ═══════════════════════════════════════════════════════════
#  Sérialisation / Restauration
# ═══════════════════════════════════════════════════════════

class TestSerialization:
    """get_state / restore_state."""

    def test_state_roundtrip(self):
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Dan", "d1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.role.on_game_start(game)
        original_target_uid = cdt.target.user_id

        state = cdt.role.get_state()

        # Créer un nouveau rôle et restaurer
        new_role = ChasseurDeTetes()
        new_role.assign_to_player(cdt)
        new_role.restore_state(state, game.players)

        assert new_role.target_assigned is True
        assert new_role.target_dead_other is False
        assert new_role.has_won is False
        assert cdt.target.user_id == original_target_uid

    def test_state_roundtrip_after_alliance(self):
        """Restauration après passage en alliance du mal."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        game.kill_player(game.players["t1"])
        state = cdt.role.get_state()

        new_role = ChasseurDeTetes()
        new_role.assign_to_player(cdt)
        new_role.restore_state(state, game.players)

        assert new_role.target_dead_other is True
        assert new_role.team == Team.MECHANT

    def test_state_roundtrip_after_win(self):
        """Restauration après victoire."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        game.kill_player(game.players["t1"], voted_out=True)
        state = cdt.role.get_state()

        new_role = ChasseurDeTetes()
        new_role.assign_to_player(cdt)
        new_role.restore_state(state, game.players)

        assert new_role.has_won is True
        assert new_role.team == Team.NEUTRE


# ═══════════════════════════════════════════════════════════
#  Interaction avec check_win_condition
# ═══════════════════════════════════════════════════════════

class TestVictoryConditionIntegration:
    """Le CDT solo doit être prioritaire sur village/loups."""

    def test_cdt_win_priority_over_village(self):
        """Si CDT gagne ET plus de loups vivants, CDT l'emporte (pas village)."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        # Voter pour le dernier loup → CDT gagne + village n'a plus de loups
        game.kill_player(game.players["t1"], voted_out=True)

        winner = game.check_win_condition()
        # CDT est vérifié en premier (priorité 0)
        assert winner == Team.NEUTRE

    def test_no_win_when_cdt_alive_but_no_has_won(self):
        """Un CDT vivant sans victoire ne bloque pas la partie."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Wolf", "w1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["a1"]
        cdt.role.target_assigned = True

        # Tuer le loup sans vote → village gagne normalement
        game.kill_player(game.players["w1"])
        winner = game.check_win_condition()
        assert winner == Team.GENTIL

    def test_cdt_mechant_counted_in_wolf_victory(self):
        """Quand CDT est MECHANT, il compte comme MECHANT pour la victoire loups."""
        game = make_game(
            ("CDT", "cdt1", RoleType.CHASSEUR_DE_TETES),
            ("Cible", "t1", RoleType.VILLAGEOIS),
            ("Wolf", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        cdt = game.players["cdt1"]
        cdt.target = game.players["t1"]
        cdt.role.target_assigned = True

        # Cible tuée par loups → CDT MECHANT
        game.kill_player(game.players["t1"])
        # Tous les gentils morts
        game.kill_player(game.players["a1"])
        game.kill_player(game.players["b1"])

        winner = game.check_win_condition()
        assert winner == Team.MECHANT


# ═══════════════════════════════════════════════════════════
#  Factory
# ═══════════════════════════════════════════════════════════

class TestFactory:
    """Le rôle est bien créé par la factory."""

    def test_factory_creates_chasseur_de_tetes(self):
        role = RoleFactory.create_role(RoleType.CHASSEUR_DE_TETES)
        assert isinstance(role, ChasseurDeTetes)
        assert role.role_type == RoleType.CHASSEUR_DE_TETES

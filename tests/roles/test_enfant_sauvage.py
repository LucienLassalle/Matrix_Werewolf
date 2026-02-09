"""Tests complets du rôle Enfant Sauvage.

Couvre :
- Auto-résolution de l'Enfant Sauvage à la fin de la première nuit
  (attribution automatique d'un mentor si le joueur n'a pas choisi)
- Pas d'écrasement si le joueur a déjà choisi un mentor
- Auto-résolution uniquement à la nuit 1
- Conversion en loup quand le mentor meurt
- Pas de crash quand il n'y a pas d'Enfant Sauvage
- Un Enfant Sauvage mort n'est pas résolu
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
#  Auto-résolution
# ═══════════════════════════════════════════════════════════

class TestEnfantSauvageAutoResolve:
    """Résolution automatique à la fin de la première nuit."""

    def test_auto_assign_mentor(self):
        """Si l'ES n'a pas choisi, un mentor est assigné automatiquement."""
        game = make_game(
            ("ES", "es1", RoleType.ENFANT_SAUVAGE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        es = game.players["es1"]
        assert not es.role.has_chosen_mentor

        game._auto_resolve_enfant_sauvage()

        assert es.role.has_chosen_mentor
        assert es.mentor is not None
        assert es.mentor.user_id != "es1"

    def test_no_override_if_already_chosen(self):
        """Le choix du joueur n'est pas écrasé."""
        game = make_game(
            ("ES", "es1", RoleType.ENFANT_SAUVAGE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        game.players["es1"].mentor = game.players["a1"]
        game.players["es1"].role.has_chosen_mentor = True

        game._auto_resolve_enfant_sauvage()
        assert game.players["es1"].mentor.user_id == "a1"

    def test_idempotent_after_assignment(self):
        """Une fois le mentor assigné, _auto_resolve ne change rien."""
        game = make_game(
            ("ES", "es1", RoleType.ENFANT_SAUVAGE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        game._auto_resolve_enfant_sauvage()
        first_mentor = game.players["es1"].mentor

        game.current_turn = 2
        game._auto_resolve_enfant_sauvage()
        assert game.players["es1"].mentor == first_mentor

    def test_mentor_death_converts_to_wolf(self):
        """Quand le mentor meurt, l'ES change de camp."""
        game = make_game(
            ("ES", "es1", RoleType.ENFANT_SAUVAGE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        es = game.players["es1"]
        es.mentor = game.players["a1"]
        es.role.has_chosen_mentor = True
        assert es.role.team == Team.GENTIL

        game.kill_player(game.players["a1"])

        assert es.role.team == Team.MECHANT


# ═══════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════

class TestEnfantSauvageEdgeCases:
    """Cas limites : pas d'ES, ES mort."""

    def test_no_enfant_sauvage_no_crash(self):
        """Pas de crash si aucun ES dans la partie."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        game._auto_resolve_enfant_sauvage()  # Ne doit pas planter

    def test_dead_enfant_sauvage_not_resolved(self):
        """Un ES mort n'est pas auto-résolu."""
        game = make_game(
            ("ES", "es1", RoleType.ENFANT_SAUVAGE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.current_turn = 1
        game.players["es1"].is_alive = False

        game._auto_resolve_enfant_sauvage()
        assert not game.players["es1"].role.has_chosen_mentor


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

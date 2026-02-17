"""Tests du rôle Voyante.

Couvre :
- Voyante peut voir le rôle d'un joueur chaque nuit
- Ne peut pas se voir elle-même
- Pouvoir réinitialisé chaque nuit
- Ne peut voir qu'un joueur par nuit
- Cible doit être vivante
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


class TestVoyante:
    """Tests de la Voyante."""

    def test_see_role(self):
        """La Voyante peut voir le rôle d'un joueur."""
        game = make_game(
            ("Voyante", "v1", RoleType.VOYANTE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        voyante = game.players["v1"]
        target = game.players["w1"]
        result = voyante.role.perform_action(game, ActionType.SEE_ROLE, target)
        assert result["success"]
        assert "Loup-Garou" in result["message"]

    def test_cannot_see_self(self):
        """La Voyante ne peut pas se voir elle-même."""
        game = make_game(
            ("Voyante", "v1", RoleType.VOYANTE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        voyante = game.players["v1"]
        result = voyante.role.perform_action(game, ActionType.SEE_ROLE, voyante)
        assert not result["success"]

    def test_one_per_night(self):
        """La Voyante ne peut voir qu'un joueur par nuit."""
        game = make_game(
            ("Voyante", "v1", RoleType.VOYANTE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        voyante = game.players["v1"]
        r1 = voyante.role.perform_action(game, ActionType.SEE_ROLE, game.players["w1"])
        assert r1["success"]
        # Après une utilisation, can_perform_action retourne False
        assert not voyante.role.can_perform_action(ActionType.SEE_ROLE)

    def test_power_resets_each_night(self):
        """Le pouvoir se réinitialise au début de chaque nuit."""
        game = make_game(
            ("Voyante", "v1", RoleType.VOYANTE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        voyante = game.players["v1"]
        voyante.role.perform_action(game, ActionType.SEE_ROLE, game.players["w1"])
        assert voyante.role.has_used_power_tonight
        voyante.role.on_night_start(game)
        assert not voyante.role.has_used_power_tonight
        r = voyante.role.perform_action(game, ActionType.SEE_ROLE, game.players["a1"])
        assert r["success"]

    def test_cannot_see_dead_player(self):
        """La Voyante ne peut pas voir un joueur mort."""
        game = make_game(
            ("Voyante", "v1", RoleType.VOYANTE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        game.players["a1"].kill()
        voyante = game.players["v1"]
        result = voyante.role.perform_action(game, ActionType.SEE_ROLE, game.players["a1"])
        assert not result["success"]

    def test_team(self):
        """La Voyante est dans l'équipe GENTIL."""
        role = RoleFactory.create_role(RoleType.VOYANTE)
        assert role.team == Team.GENTIL

    def test_can_act_at_night(self):
        """La Voyante agit la nuit."""
        role = RoleFactory.create_role(RoleType.VOYANTE)
        assert role.can_act_at_night()

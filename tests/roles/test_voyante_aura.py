"""Tests du rôle Voyante d'Aura.

Couvre :
- Voir l'aura (équipe) d'un joueur
- Ne peut pas se voir elle-même
- Pouvoir réinitialisé chaque nuit
- Détecte correctement GENTIL, MECHANT, NEUTRE
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


class TestVoyanteAura:
    """Tests de la Voyante d'Aura."""

    def test_see_aura_gentil(self):
        game = make_game(
            ("Aura", "va1", RoleType.VOYANTE_AURA),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        result = game.players["va1"].role.perform_action(
            game, ActionType.SEE_AURA, game.players["a1"]
        )
        assert result["success"]
        assert "Gentil" in result["aura"]

    def test_see_aura_mechant(self):
        game = make_game(
            ("Aura", "va1", RoleType.VOYANTE_AURA),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        result = game.players["va1"].role.perform_action(
            game, ActionType.SEE_AURA, game.players["w1"]
        )
        assert result["success"]
        assert "Méchant" in result["aura"]

    def test_see_aura_neutre(self):
        game = make_game(
            ("Aura", "va1", RoleType.VOYANTE_AURA),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Mercenaire", "m1", RoleType.MERCENAIRE),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        result = game.players["va1"].role.perform_action(
            game, ActionType.SEE_AURA, game.players["m1"]
        )
        assert result["success"]
        assert "Neutre" in result["aura"]

    def test_cannot_see_self(self):
        game = make_game(
            ("Aura", "va1", RoleType.VOYANTE_AURA),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        result = game.players["va1"].role.perform_action(
            game, ActionType.SEE_AURA, game.players["va1"]
        )
        assert not result["success"]

    def test_one_per_night(self):
        game = make_game(
            ("Aura", "va1", RoleType.VOYANTE_AURA),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        r1 = game.players["va1"].role.perform_action(
            game, ActionType.SEE_AURA, game.players["w1"]
        )
        assert r1["success"]
        assert not game.players["va1"].role.can_perform_action(ActionType.SEE_AURA)

    def test_power_resets_each_night(self):
        game = make_game(
            ("Aura", "va1", RoleType.VOYANTE_AURA),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.SORCIERE),
            ("Eve", "e1", RoleType.CHASSEUR),
        )
        va = game.players["va1"]
        va.role.perform_action(game, ActionType.SEE_AURA, game.players["w1"])
        va.role.on_night_start(game)
        assert not va.role.has_used_power_tonight

    def test_team(self):
        role = RoleFactory.create_role(RoleType.VOYANTE_AURA)
        assert role.team == Team.GENTIL

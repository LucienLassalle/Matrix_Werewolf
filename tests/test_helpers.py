"""Tests des utilitaires helpers.

Couvre :
- format_player_list (avec/sans rôles, mayor, lover)
- get_team_stats
- validate_role_configuration (valid, errors, warnings)
- generate_game_id
"""

import pytest
from models.player import Player
from models.enums import RoleType, Team
from roles import RoleFactory
from utils.helpers import (
    format_player_list,
    get_team_stats,
    validate_role_configuration,
    generate_game_id,
)


def _make_player(pseudo, uid, role_type, alive=True, mayor=False, lover=None):
    p = Player(pseudo, uid)
    role = RoleFactory.create_role(role_type)
    role.assign_to_player(p)
    p.is_alive = alive
    p.is_mayor = mayor
    p.lover = lover
    return p


class TestFormatPlayerList:
    def test_basic(self):
        players = [_make_player("Alice", "a1", RoleType.VILLAGEOIS)]
        txt = format_player_list(players)
        assert "Alice" in txt
        assert "✓" in txt

    def test_dead_player(self):
        players = [_make_player("Bob", "b1", RoleType.VILLAGEOIS, alive=False)]
        txt = format_player_list(players)
        assert "✗" in txt

    def test_show_roles(self):
        players = [_make_player("Alice", "a1", RoleType.SORCIERE)]
        txt = format_player_list(players, show_roles=True)
        assert "sorci" in txt.lower()  # Fonctionne avec Sorcière (accent) ou Sorciere

    def test_mayor_crown(self):
        players = [_make_player("Alice", "a1", RoleType.VILLAGEOIS, mayor=True)]
        txt = format_player_list(players)
        assert "👑" in txt

    def test_lover_heart(self):
        alice = _make_player("Alice", "a1", RoleType.VILLAGEOIS)
        bob = _make_player("Bob", "b1", RoleType.VILLAGEOIS)
        alice.lover = bob
        txt = format_player_list([alice])
        assert "💕" in txt


class TestGetTeamStats:
    def test_counts(self):
        players = [
            _make_player("Alice", "a1", RoleType.VILLAGEOIS),
            _make_player("Bob", "b1", RoleType.LOUP_GAROU),
            _make_player("Eve", "e1", RoleType.VILLAGEOIS, alive=False),
        ]
        stats = get_team_stats(players)
        assert stats[Team.GENTIL]["alive"] == 1
        assert stats[Team.GENTIL]["dead"] == 1
        assert stats[Team.MECHANT]["alive"] == 1

    def test_empty(self):
        stats = get_team_stats([])
        assert stats[Team.GENTIL]["alive"] == 0


class TestValidateRoleConfiguration:
    def test_valid_config(self):
        config = {
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        }
        result = validate_role_configuration(config, 8)
        assert result["valid"]
        assert len(result["errors"]) == 0

    def test_too_many_roles(self):
        config = {
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 10,
        }
        result = validate_role_configuration(config, 5)
        assert not result["valid"]
        assert any("Trop de rôles" in e for e in result["errors"])

    def test_no_wolves(self):
        config = {
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        }
        result = validate_role_configuration(config, 6)
        assert not result["valid"]
        assert any("loup" in e.lower() for e in result["errors"])

    def test_missing_mandatory(self):
        config = {
            RoleType.LOUP_GAROU: 2,
            RoleType.VILLAGEOIS: 4,
        }
        result = validate_role_configuration(config, 6)
        assert not result["valid"]
        # Sorcière, Voyante, Chasseur manquantes
        assert len([e for e in result["errors"] if "obligatoire" in e]) == 3

    def test_too_few_players(self):
        config = {
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
        }
        result = validate_role_configuration(config, 3)
        assert not result["valid"]
        assert any("4 joueurs" in e for e in result["errors"])

    def test_warning_many_wolves(self):
        config = {
            RoleType.LOUP_GAROU: 4,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 1,
        }
        result = validate_role_configuration(config, 8)
        assert len(result["warnings"]) > 0

    def test_string_keys_accepted(self):
        """Les clés str sont normalisées en RoleType."""
        config = {
            "LOUP_GAROU": 2,
            "SORCIERE": 1,
            "VOYANTE": 1,
            "CHASSEUR": 1,
            "VILLAGEOIS": 2,
        }
        result = validate_role_configuration(config, 7)
        assert result["valid"]

    def test_redundant_voyantes_warning(self):
        config = {
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.VOYANTE_AURA: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 2,
        }
        result = validate_role_configuration(config, 8)
        assert any("redondant" in w.lower() for w in result["warnings"])


class TestGenerateGameId:
    def test_format(self):
        gid = generate_game_id()
        assert gid.startswith("GAME-")
        parts = gid.split("-")
        assert len(parts) == 3

    def test_unique(self):
        ids = {generate_game_id() for _ in range(10)}
        assert len(ids) == 10

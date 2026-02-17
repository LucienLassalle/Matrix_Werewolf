"""Tests du rôle Montreur d'Ours.

Couvre :
- L'ours grogne si un loup est voisin
- L'ours ne grogne pas si pas de loup voisin
- Fonctionne avec les joueurs morts sautés
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
    game.phase = GamePhase.DAY
    return game


class TestMontreurOurs:
    """Tests du Montreur d'Ours."""

    def test_growl_with_wolf_neighbor(self):
        """L'ours grogne si un loup est voisin direct."""
        # Ordre du cercle : Alice - Montreur - Loup
        game = make_game(
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Montreur", "mo1", RoleType.MONTREUR_OURS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        montreur = game.players["mo1"]
        result = montreur.role.check_for_wolves(game)
        assert result is True

    def test_no_growl_without_wolf_neighbor(self):
        """L'ours ne grogne pas si aucun loup n'est voisin."""
        # Ordre : Alice - Montreur - Bob (pas de loup voisin)
        game = make_game(
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Montreur", "mo1", RoleType.MONTREUR_OURS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        montreur = game.players["mo1"]
        result = montreur.role.check_for_wolves(game)
        assert result is False

    def test_dead_player_skipped(self):
        """Les joueurs morts sont sautés pour trouver les voisins vivants."""
        # Ordre : Alice - [Bob mort] - Montreur - [Eve morte] - Loup
        game = make_game(
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Montreur", "mo1", RoleType.MONTREUR_OURS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        game.players["b1"].is_alive = False
        game.players["e1"].is_alive = False

        montreur = game.players["mo1"]
        result = montreur.role.check_for_wolves(game)
        # Voisin gauche vivant = Alice, voisin droit vivant = Loup
        assert result is True

    def test_no_growl_dead_montreur(self):
        """Un Montreur mort ne déclenche pas de grognement."""
        game = make_game(
            ("Montreur", "mo1", RoleType.MONTREUR_OURS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        game.players["mo1"].is_alive = False
        result = game.players["mo1"].role.check_for_wolves(game)
        assert result is False

    def test_team(self):
        role = RoleFactory.create_role(RoleType.MONTREUR_OURS)
        assert role.team == Team.GENTIL

    def test_wolf_on_left(self):
        """L'ours grogne si le loup est à gauche."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Montreur", "mo1", RoleType.MONTREUR_OURS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        montreur = game.players["mo1"]
        assert montreur.role.check_for_wolves(game) is True

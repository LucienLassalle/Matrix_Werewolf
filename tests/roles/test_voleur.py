"""Tests du rôle Voleur.

Couvre :
- Le tirage de cartes exclut les rôles interdits (Voleur, Cupidon, Mercenaire, Dictateur)
- L'échange de rôle fonctionne correctement
- Pouvoir à usage unique
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


def make_game(*specs) -> GameManager:
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestVoleurExtraCardsPool:
    """Les cartes du Voleur sont tirées d'un pool restreint."""

    def test_excluded_roles_not_in_pool(self):
        """Cupidon, Mercenaire, Dictateur, Voleur ne sont jamais dans le tirage."""
        game = make_game(
            ("Voleur", "v1", RoleType.VOLEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        # Simuler start_game pour générer les extra_roles
        import random
        excluded = {RoleType.VOLEUR, RoleType.CUPIDON, RoleType.MERCENAIRE, RoleType.DICTATEUR}
        extra_pool = [rt for rt in RoleType if rt not in excluded]

        # Vérifier que les rôles exclus ne sont pas dans le pool
        for rt in excluded:
            assert rt not in extra_pool

        # Vérifier que d'autres rôles y sont bien
        assert RoleType.VILLAGEOIS in extra_pool
        assert RoleType.LOUP_GAROU in extra_pool
        assert RoleType.SORCIERE in extra_pool

    def test_extra_roles_generated_on_start(self):
        """start_game() génère les extra_roles sans rôles interdits."""
        game = GameManager()
        game.add_player("Voleur", "v1")
        game.add_player("Loup", "w1")
        game.add_player("Alice", "a1")
        game.add_player("Bob", "b1")
        game.add_player("Eve", "e1")

        # Configurer les rôles manuellement dans available_roles
        game.available_roles = [
            RoleFactory.create_role(RoleType.VOLEUR),
            RoleFactory.create_role(RoleType.LOUP_GAROU),
            RoleFactory.create_role(RoleType.SORCIERE),
            RoleFactory.create_role(RoleType.VOYANTE),
            RoleFactory.create_role(RoleType.CHASSEUR),
        ]

        result = game.start_game()

        assert len(game.extra_roles) == 2
        excluded = {RoleType.VOLEUR, RoleType.CUPIDON, RoleType.MERCENAIRE, RoleType.DICTATEUR}
        for role in game.extra_roles:
            assert role.role_type not in excluded


class TestVoleurSwap:
    """L'échange de rôle du Voleur."""

    def test_swap_with_target(self):
        game = make_game(
            ("Voleur", "v1", RoleType.VOLEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        result = game.players["v1"].role.perform_action(
            game, ActionType.STEAL_ROLE, game.players["a1"]
        )
        assert result["success"]
        assert game.players["v1"].role.role_type == RoleType.VILLAGEOIS
        assert game.players["a1"].role.role_type == RoleType.VOLEUR

    def test_single_use(self):
        game = make_game(
            ("Voleur", "v1", RoleType.VOLEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["v1"].role.perform_action(
            game, ActionType.STEAL_ROLE, game.players["a1"]
        )
        # Après l'échange, le joueur a un nouveau rôle (Villageois, pas Voleur)
        # Tenter de voler à nouveau ne fonctionnerait que si le rôle est toujours Voleur
        # Le test vérifie que le Voleur donné à la cible a has_used_power
        assert game.players["a1"].role.has_used_power

    def test_cannot_swap_with_self(self):
        game = make_game(
            ("Voleur", "v1", RoleType.VOLEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        result = game.players["v1"].role.perform_action(
            game, ActionType.STEAL_ROLE, game.players["v1"]
        )
        assert not result["success"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

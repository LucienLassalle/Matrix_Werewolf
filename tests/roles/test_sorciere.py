"""Tests du rôle Sorcière.

Couvre :
- La Sorcière ne peut pas s'empoisonner elle-même
- Utilisation unique de chaque potion
- Les deux potions peuvent être utilisées la même nuit
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


class TestSorciereSelfPoison:
    """La Sorcière ne peut pas s'empoisonner elle-même."""

    def test_self_poison_rejected(self):
        game = make_game(
            ("Sorcière", "s1", RoleType.SORCIERE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        result = sorc.role.perform_action(game, ActionType.POISON, sorc)
        assert not result["success"]
        assert sorc.role.has_death_potion  # Potion non consommée

    def test_poison_other_player_works(self):
        game = make_game(
            ("Sorcière", "s1", RoleType.SORCIERE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        result = game.players["s1"].role.perform_action(
            game, ActionType.POISON, game.players["a1"]
        )
        assert result["success"]
        assert not game.players["s1"].role.has_death_potion


class TestSorcierePotions:
    """Tests des potions de la Sorcière."""

    def test_both_potions_same_night(self):
        game = make_game(
            ("Sorcière", "s1", RoleType.SORCIERE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]

        # Heal
        r1 = sorc.role.perform_action(game, ActionType.HEAL, game.players["a1"])
        assert r1["success"]

        # Poison
        r2 = sorc.role.perform_action(game, ActionType.POISON, game.players["b1"])
        assert r2["success"]

    def test_cannot_heal_twice(self):
        game = make_game(
            ("Sorcière", "s1", RoleType.SORCIERE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        sorc.role.perform_action(game, ActionType.HEAL, game.players["a1"])
        r2 = sorc.role.perform_action(game, ActionType.HEAL, game.players["b1"])
        assert not r2["success"]

    def test_cannot_poison_twice(self):
        game = make_game(
            ("Sorcière", "s1", RoleType.SORCIERE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        sorc.role.perform_action(game, ActionType.POISON, game.players["a1"])
        r2 = sorc.role.perform_action(game, ActionType.POISON, game.players["b1"])
        assert not r2["success"]

    def test_flags_reset_on_night_start(self):
        """Les flags tonight sont réinitialisés au début de la nuit."""
        game = make_game(
            ("Sorcière", "s1", RoleType.SORCIERE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        sorc.role.has_healed_tonight = True
        sorc.role.has_poisoned_tonight = True

        sorc.role.on_night_start(game)
        assert not sorc.role.has_healed_tonight
        assert not sorc.role.has_poisoned_tonight

    def test_no_life_potion_left(self):
        """Impossible de soigner sans potion de vie."""
        game = make_game(
            ("Sorcière", "s1", RoleType.SORCIERE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        sorc.role.has_life_potion = False

        r = sorc.role.perform_action(game, ActionType.HEAL, game.players["a1"])
        assert not r["success"]

    def test_no_death_potion_left(self):
        """Impossible d'empoisonner sans potion de mort."""
        game = make_game(
            ("Sorcière", "s1", RoleType.SORCIERE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        sorc.role.has_death_potion = False

        r = sorc.role.perform_action(game, ActionType.POISON, game.players["a1"])
        assert not r["success"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

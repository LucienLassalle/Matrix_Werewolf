"""Tests du ActionManager : résolution des actions de nuit.

Couvre :
- Protection du Garde contre les loups
- Sorcière : guérison, poison, combinaison heal+poison
- Loup Blanc : meurtre d'un loup-garou
- Résultat wolf_target dans les résultats
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager
from game.action_manager import ActionManager


def make_game(*specs) -> GameManager:
    """Crée une partie avec les joueurs/rôles donnés en phase NIGHT."""
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestActionManagerResolution:
    """Vérifie l'ordre de résolution de la nuit."""

    def test_garde_protects_wolf_target(self):
        """Le Garde empêche la mort par les loups."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Garde", "g1", RoleType.GARDE),
        )
        target = game.players["v1"]
        garde = game.players["g1"]

        garde.role.perform_action(game, ActionType.PROTECT, target)
        game.action_manager.register_action(garde, ActionType.PROTECT, target)

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.action_manager.execute_night_actions(game)

        assert target.is_alive
        assert len(results["deaths"]) == 0

    def test_sorciere_heal_saves_wolf_target(self):
        """La Sorcière peut sauver la cible des loups."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]
        sorc = game.players["s1"]

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        sorc.role.perform_action(game, ActionType.HEAL, target)
        game.action_manager.register_action(sorc, ActionType.HEAL, target)

        results = game.action_manager.execute_night_actions(game)

        assert target.is_alive
        assert target in results["saved"]

    def test_sorciere_heal_wasted_if_garde_protects(self):
        """Si le Garde protège et la Sorcière soigne, la potion est consommée."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Garde", "g1", RoleType.GARDE),
        )
        target = game.players["v1"]
        sorc = game.players["s1"]
        garde = game.players["g1"]

        garde.role.perform_action(game, ActionType.PROTECT, target)
        game.action_manager.register_action(garde, ActionType.PROTECT, target)

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        sorc.role.perform_action(game, ActionType.HEAL, target)
        game.action_manager.register_action(sorc, ActionType.HEAL, target)

        results = game.action_manager.execute_night_actions(game)

        assert target.is_alive
        assert not sorc.role.has_life_potion  # Potion consommée quand même

    def test_sorciere_poison_kills(self):
        """La potion de mort de la Sorcière tue la cible."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Villageois2", "v2", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        cible_poison = game.players["v2"]

        sorc.role.perform_action(game, ActionType.POISON, cible_poison)
        game.action_manager.register_action(sorc, ActionType.POISON, cible_poison)

        results = game.action_manager.execute_night_actions(game)

        assert not cible_poison.is_alive
        assert cible_poison in results["deaths"]

    def test_sorciere_heal_and_poison_same_night(self):
        """La Sorcière peut sauver ET empoisonner la même nuit."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Victime", "v1", RoleType.VILLAGEOIS),
            ("CiblePoison", "v2", RoleType.VILLAGEOIS),
        )
        target_wolf = game.players["v1"]
        target_poison = game.players["v2"]
        sorc = game.players["s1"]

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target_wolf)
        game.vote_manager.add_wolf_vote(game.players["w1"], target_wolf)

        sorc.role.perform_action(game, ActionType.HEAL, target_wolf)
        game.action_manager.register_action(sorc, ActionType.HEAL, target_wolf)

        sorc.role.perform_action(game, ActionType.POISON, target_poison)
        game.action_manager.register_action(sorc, ActionType.POISON, target_poison)

        results = game.action_manager.execute_night_actions(game)

        assert target_wolf.is_alive  # Sauvé
        assert not target_poison.is_alive  # Empoisonné
        assert target_wolf in results["saved"]
        assert target_poison in results["deaths"]

    def test_loup_blanc_kill(self):
        """Le Loup Blanc tue un loup-garou (nuit paire)."""
        game = make_game(
            ("LoupBlanc", "lb1", RoleType.LOUP_BLANC),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        lb = game.players["lb1"]
        target = game.players["w1"]

        lb.role.on_night_start(game)  # Nuit 1 : non
        lb.role.on_night_start(game)  # Nuit 2 : oui
        lb.role.perform_action(game, ActionType.KILL, target)
        game.action_manager.register_action(lb, ActionType.KILL, target)

        results = game.action_manager.execute_night_actions(game)

        assert not target.is_alive
        assert target in results["deaths"]

    def test_wolf_target_in_results(self):
        """Le résultat contient la cible des loups."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.action_manager.execute_night_actions(game)

        assert results["wolf_target"] == target


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

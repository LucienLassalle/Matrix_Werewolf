"""Scenarios critiques autour du Garde et de la Sorciere."""

from models.enums import ActionType, RoleType
from tests.critical_scenarios_helpers import setup_game


class TestGardeProtection:
    """La protection du Garde empeche le meurtre des loups."""

    def test_garde_saves_wolf_target(self):
        """Le Garde protege la cible des loups -> personne ne meurt."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.GARDE: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        garde = next(p for p in players if p.role.role_type == RoleType.GARDE)
        target = next(p for p in players if p.role.role_type != RoleType.LOUP_GAROU and p != garde)

        result = garde.role.perform_action(game, ActionType.PROTECT, target)
        assert result["success"]
        game.action_manager.register_action(garde, ActionType.PROTECT, target)

        game.vote_manager.cast_vote(wolf, target, is_wolf_vote=True)

        results = game.action_manager.execute_night_actions(game)

        assert len(results["deaths"]) == 0
        assert target.is_alive

    def test_garde_does_not_block_sorciere_poison(self):
        """Le Garde ne protege pas contre le poison de la Sorciere."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.GARDE: 1,
            RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 2
        })

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        garde = next(p for p in players if p.role.role_type == RoleType.GARDE)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        victim = next(p for p in players if p.role.role_type != RoleType.LOUP_GAROU and p != sorciere)

        garde.role.perform_action(game, ActionType.PROTECT, victim)
        game.action_manager.register_action(garde, ActionType.PROTECT, victim)

        sorciere.role.perform_action(game, ActionType.POISON, victim)
        game.action_manager.register_action(sorciere, ActionType.POISON, victim)

        other = next(
            p for p in players
            if p != victim and p.role.role_type != RoleType.LOUP_GAROU
        )
        game.vote_manager.cast_vote(wolf, other, is_wolf_vote=True)

        game.action_manager.execute_night_actions(game)

        assert not victim.is_alive


class TestSorciereHeal:
    """La Sorciere peut sauver la cible des loups."""

    def test_sorciere_heals_wolf_target(self):
        """La Sorciere utilise la potion de vie -> la victime survit."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        victim = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)

        game.vote_manager.cast_vote(wolf, victim, is_wolf_vote=True)

        sorciere.role.perform_action(game, ActionType.HEAL, victim)
        game.action_manager.register_action(sorciere, ActionType.HEAL, victim)

        results = game.action_manager.execute_night_actions(game)

        assert victim.is_alive
        assert len(results["deaths"]) == 0
        assert victim in [p for p in results.get("saved", [])]

    def test_sorciere_heal_and_poison_same_night(self):
        """La Sorciere peut utiliser les deux potions la meme nuit."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        villagers = [p for p in players if p.role.role_type != RoleType.LOUP_GAROU and p != sorciere]
        v1, v2 = villagers[0], villagers[1]

        game.vote_manager.cast_vote(wolf, v1, is_wolf_vote=True)

        sorciere.role.perform_action(game, ActionType.HEAL, v1)
        game.action_manager.register_action(sorciere, ActionType.HEAL, v1)
        sorciere.role.perform_action(game, ActionType.POISON, v2)
        game.action_manager.register_action(sorciere, ActionType.POISON, v2)

        results = game.action_manager.execute_night_actions(game)

        assert v1.is_alive
        assert not v2.is_alive

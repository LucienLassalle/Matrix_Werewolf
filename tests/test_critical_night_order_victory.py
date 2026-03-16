"""Ordre de resolution de nuit et victoires limites."""

from models.enums import ActionType, RoleType, Team
from tests.critical_scenarios_helpers import setup_game


class TestNightResolutionOrder:
    """L'ordre de resolution de la nuit est correct."""

    def test_garde_before_wolves(self):
        """Le Garde agit avant les loups."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.GARDE: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        garde = next(p for p in players if p.role.role_type == RoleType.GARDE)
        target = next(p for p in players if p.role.role_type != RoleType.LOUP_GAROU and p != garde)

        game.action_manager.register_action(garde, ActionType.PROTECT, target)
        target.is_protected = True
        game.vote_manager.cast_vote(wolf, target, is_wolf_vote=True)

        results = game.action_manager.execute_night_actions(game)

        assert target.is_alive
        assert len(results["deaths"]) == 0

    def test_sorciere_after_wolves(self):
        """La Sorciere peut sauver car elle agit apres le vote des loups."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        victim = next(p for p in players if p.role.role_type != RoleType.LOUP_GAROU and p != sorciere)

        game.vote_manager.cast_vote(wolf, victim, is_wolf_vote=True)

        sorciere.role.perform_action(game, ActionType.HEAL, victim)
        game.action_manager.register_action(sorciere, ActionType.HEAL, victim)

        game.action_manager.execute_night_actions(game)

        assert victim.is_alive

    def test_loup_blanc_after_sorciere(self):
        """Le Loup Blanc agit apres la Sorciere."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.LOUP_BLANC: 1,
            RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 2
        })

        players = list(game.players.values())
        lb = next(p for p in players if p.role.role_type == RoleType.LOUP_BLANC)
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        victim = next(
            p for p in players
            if p.role.role_type not in {RoleType.LOUP_GAROU, RoleType.LOUP_BLANC, RoleType.SORCIERE}
        )

        lb.role.can_kill_tonight = True
        lb.role.perform_action(game, ActionType.KILL, wolf)
        game.action_manager.register_action(lb, ActionType.KILL, wolf)

        game.vote_manager.cast_vote(lb, victim, is_wolf_vote=True)
        game.vote_manager.cast_vote(wolf, victim, is_wolf_vote=True)

        results = game.action_manager.execute_night_actions(game)

        dead_ids = {d.user_id for d in results["deaths"]}
        assert wolf.user_id in dead_ids
        assert victim.user_id in dead_ids


class TestVictoryConditions:
    """Conditions de victoire dans des cas limites."""

    def test_all_wolves_dead_village_wins(self):
        """Plus aucun loup vivant -> le village gagne."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})

        wolf = next(p for p in game.players.values() if p.role.role_type == RoleType.LOUP_GAROU)
        wolf.kill()

        assert game.check_win_condition() == Team.GENTIL

    def test_only_wolves_alive_wolves_win(self):
        """Il ne reste que des loups -> les loups gagnent."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 2, RoleType.VILLAGEOIS: 3})

        for p in game.players.values():
            if p.get_team() == Team.GENTIL:
                p.kill()

        assert game.check_win_condition() == Team.MECHANT

    def test_loup_blanc_solo_neutral_win(self):
        """Le Loup Blanc est le seul survivant -> victoire neutre."""
        game = setup_game(5, {RoleType.LOUP_BLANC: 1, RoleType.VILLAGEOIS: 4})

        lb = next(p for p in game.players.values() if p.role.role_type == RoleType.LOUP_BLANC)
        for p in game.players.values():
            if p != lb:
                p.is_alive = False

        assert game.check_win_condition() == Team.NEUTRE

    def test_everyone_dead_neutral(self):
        """Tout le monde est mort -> neutre."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})

        for p in game.players.values():
            p.is_alive = False

        assert game.check_win_condition() == Team.NEUTRE

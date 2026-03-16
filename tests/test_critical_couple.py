"""Scenarios critiques autour du couple."""

from models.enums import GamePhase, RoleType, Team
from tests.critical_scenarios_helpers import setup_game


class TestCoupleDeathCascade:
    """Si un amoureux meurt, l'autre meurt aussi."""

    def test_wolf_kills_lover_both_die_at_night(self):
        """Les loups tuent un amoureux -> les deux meurent la nuit."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        v1, v2 = [p for p in players if p.role.role_type != RoleType.LOUP_GAROU][:2]

        v1.lover = v2
        v2.lover = v1

        game.vote_manager.cast_vote(wolf, v1, is_wolf_vote=True)
        results = game.action_manager.execute_night_actions(game)

        dead_ids = {d.user_id for d in results["deaths"]}
        assert v1.user_id in dead_ids
        assert v2.user_id in dead_ids

    def test_vote_kills_lover_both_die_at_day(self):
        """Le village elimine un amoureux -> les deux meurent le jour."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})

        players = list(game.players.values())
        v1, v2 = [p for p in players if p.role.role_type != RoleType.LOUP_GAROU][:2]

        v1.lover = v2
        v2.lover = v1

        game.phase = GamePhase.VOTE
        game.vote_manager.reset_votes()

        for p in players:
            if p.is_alive and p != v1:
                game.vote_manager.cast_vote(p, v1)

        result = game.end_vote_phase()

        assert result.get("eliminated") == v1
        assert not v1.is_alive
        assert not v2.is_alive

        all_deaths = result.get("all_deaths", [])
        dead_ids = {d.user_id for d in all_deaths}
        assert v1.user_id in dead_ids
        assert v2.user_id in dead_ids


class TestCoupleVictory:
    """Conditions de victoire liees au couple."""

    def test_couple_wolf_village_win_together(self):
        """Couple loup+villageois -> gagner en tant que couple."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        v1 = next(p for p in players if p.role.role_type != RoleType.LOUP_GAROU)

        wolf.lover = v1
        v1.lover = wolf

        for p in players:
            if p != wolf and p != v1:
                p.kill()

        assert game.check_win_condition() == Team.COUPLE

    def test_couple_last_two_alive_couple_wins(self):
        """Les 2 derniers vivants sont amoureux (equipes differentes)."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        villager = next(p for p in players if p.role.role_type != RoleType.LOUP_GAROU)
        wolf.lover = villager
        villager.lover = wolf

        for p in players:
            if p not in (wolf, villager):
                p.is_alive = False

        assert game.check_win_condition() == Team.COUPLE

    def test_couple_same_team_wins_as_team(self):
        """Couple meme equipe -> victoire de l'equipe, pas COUPLE."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})

        players = list(game.players.values())
        villagers = [p for p in players if p.role.role_type != RoleType.LOUP_GAROU]
        p1, p2 = villagers[0], villagers[1]
        p1.lover = p2
        p2.lover = p1

        for p in players:
            if p not in (p1, p2):
                p.is_alive = False

        assert game.check_win_condition() == Team.GENTIL

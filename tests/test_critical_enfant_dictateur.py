"""Scenarios critiques autour de l'Enfant Sauvage et du Dictateur."""

from models.enums import ActionType, GamePhase, RoleType, Team
from tests.critical_scenarios_helpers import setup_game


class TestEnfantSauvageConversion:
    """L'Enfant Sauvage devient loup quand son mentor meurt."""

    def test_mentor_killed_by_wolves_enfant_becomes_wolf(self):
        """Le mentor est tue par les loups -> l'Enfant Sauvage devient loup."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.ENFANT_SAUVAGE: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        enfant = next(p for p in players if p.role.role_type == RoleType.ENFANT_SAUVAGE)
        mentor = next(
            p for p in players
            if p.role.role_type not in (RoleType.LOUP_GAROU, RoleType.ENFANT_SAUVAGE)
        )

        enfant.role.perform_action(game, ActionType.CHOOSE_MENTOR, mentor)
        assert enfant.mentor == mentor
        assert enfant.get_team() == Team.GENTIL

        game.vote_manager.cast_vote(wolf, mentor, is_wolf_vote=True)
        game.end_night()

        assert enfant.role.role_type == RoleType.LOUP_GAROU
        assert enfant.get_team() == Team.MECHANT
        assert enfant.is_alive

    def test_mentor_killed_by_vote_enfant_becomes_wolf(self):
        """Le mentor est elimine par vote -> l'Enfant Sauvage devient loup."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.ENFANT_SAUVAGE: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        enfant = next(p for p in players if p.role.role_type == RoleType.ENFANT_SAUVAGE)
        mentor = next(
            p for p in players
            if p.role.role_type not in (RoleType.LOUP_GAROU, RoleType.ENFANT_SAUVAGE)
        )

        enfant.role.perform_action(game, ActionType.CHOOSE_MENTOR, mentor)

        game.end_night()
        game.start_vote_phase()

        for p in game.get_living_players():
            if p != mentor:
                game.vote_manager.cast_vote(p, mentor)

        game.end_vote_phase()

        assert not mentor.is_alive
        assert enfant.role.role_type == RoleType.LOUP_GAROU
        assert enfant.get_team() == Team.MECHANT


class TestDictateur:
    """Le Dictateur tue: loup -> maire; innocent -> les deux meurent."""

    def test_dictateur_kills_wolf_becomes_mayor(self):
        """Le Dictateur tue un loup -> il devient maire."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.DICTATEUR: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        dictateur = next(p for p in players if p.role.role_type == RoleType.DICTATEUR)

        game.phase = GamePhase.DAY
        result = dictateur.role.perform_action(game, ActionType.DICTATOR_KILL, wolf)

        assert result["success"]
        assert not wolf.is_alive
        assert dictateur.is_alive
        assert dictateur.is_mayor

    def test_dictateur_kills_innocent_both_die(self):
        """Le Dictateur tue un villageois -> les deux meurent."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.DICTATEUR: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        dictateur = next(p for p in players if p.role.role_type == RoleType.DICTATEUR)
        victim = next(
            p for p in players
            if p.role.role_type not in (RoleType.LOUP_GAROU, RoleType.DICTATEUR)
        )

        game.phase = GamePhase.DAY
        result = dictateur.role.perform_action(game, ActionType.DICTATOR_KILL, victim)

        assert result["success"]
        assert not victim.is_alive
        assert not dictateur.is_alive

        deaths = result.get("deaths", [])
        dead_ids = {d.user_id for d in deaths}
        assert victim.user_id in dead_ids
        assert dictateur.user_id in dead_ids

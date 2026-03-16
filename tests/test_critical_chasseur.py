"""Scenarios critiques autour du Chasseur."""

from models.enums import ActionType, RoleType, Team
from tests.critical_scenarios_helpers import setup_game


class TestChasseurKillsLastWolf:
    """Le Chasseur tire et tue le dernier loup -> le village gagne."""

    def test_chasseur_kills_last_wolf_triggers_victory(self):
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.CHASSEUR: 1, RoleType.VILLAGEOIS: 3})

        chasseur = wolf = None
        for p in game.players.values():
            if p.role.role_type == RoleType.CHASSEUR:
                chasseur = p
            elif p.role.role_type == RoleType.LOUP_GAROU:
                wolf = p

        assert chasseur and wolf

        # Tuer le chasseur (le loup le mange)
        chasseur.kill()
        chasseur.role.killed_during_day = False
        chasseur.role.can_shoot_now = True

        result = chasseur.role.perform_action(game, ActionType.KILL, wolf)
        assert result["success"], f"Chasseur n'a pas pu tirer : {result.get('message')}"

        assert not wolf.is_alive
        assert game.check_win_condition() == Team.GENTIL

    def test_chasseur_kills_wolf_lover_cascade(self):
        """Le Chasseur tue un loup en couple -> l'amoureux meurt aussi."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.CHASSEUR: 1, RoleType.VILLAGEOIS: 3})

        chasseur = wolf = villager = None
        for p in game.players.values():
            if p.role.role_type == RoleType.CHASSEUR:
                chasseur = p
            elif p.role.role_type == RoleType.LOUP_GAROU:
                wolf = p
            elif villager is None:
                villager = p

        wolf.lover = villager
        villager.lover = wolf

        chasseur.kill()
        chasseur.role.can_shoot_now = True
        result = chasseur.role.perform_action(game, ActionType.KILL, wolf)
        assert result["success"]

        assert not wolf.is_alive
        assert not villager.is_alive

        deaths = result.get("deaths", [])
        dead_ids = {d.user_id for d in deaths}
        assert wolf.user_id in dead_ids
        assert villager.user_id in dead_ids

    def test_chasseur_kills_last_wolf_with_lover(self):
        """Le Chasseur tue le dernier loup en couple -> cascade, village gagne."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.CHASSEUR: 1, RoleType.VILLAGEOIS: 3
        })

        players = list(game.players.values())
        chasseur = next(p for p in players if p.role.role_type == RoleType.CHASSEUR)
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        v1 = next(p for p in players if p.role.role_type != RoleType.LOUP_GAROU and p != chasseur)

        wolf.lover = v1
        v1.lover = wolf

        chasseur.kill()
        chasseur.role.can_shoot_now = True
        result = chasseur.role.perform_action(game, ActionType.KILL, wolf)

        assert not wolf.is_alive
        assert not v1.is_alive
        assert game.check_win_condition() == Team.GENTIL

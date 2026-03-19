"""Tests de succession quand le Dictateur devient maire."""

from models.enums import ActionType, GamePhase, RoleType
from tests.mayor_cupidon_helpers import make_game


class TestDictateurMayorSuccession:
    """Tests de la succession quand le Dictateur (devenu maire) meurt."""

    def test_dictateur_becomes_mayor_then_dies(self):
        """Le Dictateur devient maire, puis meurt -> succession se declenche."""
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois1", "v1", RoleType.VILLAGEOIS),
            ("Villageois2", "v2", RoleType.VILLAGEOIS),
            ("Villageois3", "v3", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.NIGHT

        dictateur = game.players["d1"]
        loup = game.players["w1"]

        arm = dictateur.role.perform_action(game, ActionType.DICTATOR_KILL, None)
        assert arm["success"]

        game.phase = GamePhase.DAY
        result = dictateur.role.perform_action(game, ActionType.DICTATOR_KILL, loup)
        assert result["success"]
        assert dictateur.is_mayor

        game.kill_player(dictateur, killed_during_day=True)

        assert not dictateur.is_alive
        assert game._pending_mayor_succession == dictateur

    def test_mayor_succession_after_vote_death(self):
        """Le maire meurt par vote du village -> succession."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Villageois1", "v1", RoleType.VILLAGEOIS),
            ("Villageois2", "v2", RoleType.VILLAGEOIS),
            ("Loup1", "w1", RoleType.LOUP_GAROU),
            ("Loup2", "w2", RoleType.LOUP_GAROU),
        )
        game.phase = GamePhase.VOTE
        mayor = game.players["m1"]
        mayor.is_mayor = True

        game.vote_manager.register_player(game.players["v1"])
        game.vote_manager.register_player(game.players["v2"])
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(game.players["w2"])
        game.vote_manager.register_player(mayor)

        game.vote_manager.cast_vote(game.players["v1"], mayor)
        game.vote_manager.cast_vote(game.players["w1"], mayor)
        game.vote_manager.cast_vote(game.players["w2"], mayor)

        result = game.end_vote_phase()

        assert result.get("eliminated") == mayor
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor

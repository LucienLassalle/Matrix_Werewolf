"""Tests de succession du maire."""

from models.enums import RoleType
from tests.mayor_cupidon_helpers import make_game


class TestMayorSuccession:
    """Tests de la succession du maire quand il meurt."""

    def test_mayor_death_triggers_succession(self):
        """Quand le maire meurt, _pending_mayor_succession est set."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True

        game.kill_player(mayor, killed_during_day=False)

        assert not mayor.is_alive
        assert not mayor.is_mayor
        assert game._pending_mayor_succession == mayor

    def test_non_mayor_death_no_succession(self):
        """Quand un non-maire meurt, pas de succession."""
        game = make_game(
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        villager = game.players["v1"]

        game.kill_player(villager, killed_during_day=False)

        assert game._pending_mayor_succession is None

    def test_designate_mayor_success(self):
        """Le maire mort peut designer un successeur vivant."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Successeur", "s1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        successor = game.players["s1"]

        game.kill_player(mayor, killed_during_day=True)
        assert game._pending_mayor_succession == mayor

        result = game.designate_mayor(successor)

        assert result["success"]
        assert successor.is_mayor
        assert game._pending_mayor_succession is None
        assert result["new_mayor"] == successor

    def test_designate_dead_player_fails(self):
        """On ne peut pas designer un joueur mort comme successeur."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Mort", "d1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        dead_target = game.players["d1"]
        dead_target.is_alive = False

        game.kill_player(mayor, killed_during_day=True)
        result = game.designate_mayor(dead_target)

        assert not result["success"]
        assert "vivant" in result["message"]

    def test_designate_without_pending_fails(self):
        """designate_mayor echoue s'il n'y a pas de succession en cours."""
        game = make_game(
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        target = game.players["v1"]

        result = game.designate_mayor(target)

        assert not result["success"]
        assert "Aucune succession" in result["message"]

    def test_auto_designate_mayor(self):
        """Le maire est auto-designe aleatoirement si timeout."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Vivant1", "v1", RoleType.VILLAGEOIS),
            ("Vivant2", "v2", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True

        game.kill_player(mayor, killed_during_day=True)
        assert game._pending_mayor_succession is not None

        new_mayor = game.auto_designate_mayor()

        assert new_mayor is not None
        assert new_mayor.is_alive
        assert new_mayor.is_mayor
        assert game._pending_mayor_succession is None

    def test_auto_designate_no_living_players(self):
        """auto_designate_mayor avec aucun vivant retourne None."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        wolf = game.players["w1"]
        wolf.is_alive = False

        game.kill_player(mayor, killed_during_day=True)
        new_mayor = game.auto_designate_mayor()

        assert new_mayor is None

    def test_mayor_lover_cascade(self):
        """Quand le maire meurt via cascade amoureux, la succession se declenche."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Amoureux", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Vivant", "v1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        amoureux = game.players["a1"]

        mayor.lover = amoureux
        amoureux.lover = mayor

        game.kill_player(amoureux, killed_during_day=False)

        assert not mayor.is_alive
        assert not amoureux.is_alive
        assert game._pending_mayor_succession == mayor

    def test_lover_is_mayor_dies_by_cascade(self):
        """Quand l'amoureux qui est maire meurt, la succession se declenche."""
        game = make_game(
            ("Joueur", "j1", RoleType.VILLAGEOIS),
            ("MaireAmoureux", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Vivant", "v1", RoleType.VILLAGEOIS),
        )
        joueur = game.players["j1"]
        maire_amoureux = game.players["m1"]
        maire_amoureux.is_mayor = True

        joueur.lover = maire_amoureux
        maire_amoureux.lover = joueur

        game.kill_player(joueur, killed_during_day=True)

        assert not joueur.is_alive
        assert not maire_amoureux.is_alive
        assert game._pending_mayor_succession == maire_amoureux

    def test_get_mayor(self):
        """get_mayor retourne le maire vivant."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True

        assert game.get_mayor() == mayor

        mayor.is_alive = False
        assert game.get_mayor() is None

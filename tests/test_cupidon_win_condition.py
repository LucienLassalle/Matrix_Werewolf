"""Tests de la condition de victoire Cupidon + couple."""

from models.enums import RoleType, Team
from tests.mayor_cupidon_helpers import make_game


class TestCupidonWinsWithCouple:
    """Tests de la condition de victoire Couple + Cupidon."""

    def test_couple_wins_2_alive_standard(self):
        """Victoire classique du couple : 2 derniers vivants amoureux."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["d1"].is_alive = False

        assert game.check_win_condition() == Team.COUPLE

    def test_couple_cupidon_wins_3_alive_enabled(self):
        """Avec option activee, Couple + Cupidon gagnent a 3 vivants."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = True

        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["d1"].is_alive = False

        assert game.check_win_condition() == Team.COUPLE

    def test_couple_cupidon_no_win_3_alive_disabled(self):
        """Avec option desactivee, Couple + Cupidon ne gagnent pas a 3 vivants."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = False

        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["d1"].is_alive = False

        assert game.check_win_condition() is None

    def test_cupidon_in_couple_always_wins(self):
        """Si Cupidon est un amoureux, il gagne avec le couple (flag ignore)."""
        game = make_game(
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Amoureux", "a1", RoleType.LOUP_GAROU),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = False

        cupidon = game.players["c1"]
        amoureux = game.players["a1"]
        cupidon.lover = amoureux
        amoureux.lover = cupidon
        game.players["d1"].is_alive = False

        assert game.check_win_condition() == Team.COUPLE

    def test_3_alive_not_cupidon_no_win(self):
        """3 vivants = 2 amoureux + 1 non-Cupidon -> pas de victoire couple."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = True

        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["d1"].is_alive = False

        assert game.check_win_condition() is None

    def test_cupidon_dead_couple_wins_alone(self):
        """Si Cupidon est mort, le couple gagne seul (2 derniers vivants)."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Cupidon", "c1", RoleType.CUPIDON),
        )
        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["c1"].is_alive = False

        assert game.check_win_condition() == Team.COUPLE

    def test_4_alive_no_couple_win(self):
        """Avec 4 vivants (2 amoureux + Cupidon + 1), pas de victoire couple."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Vivant", "v1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = True

        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1

        assert game.check_win_condition() is None

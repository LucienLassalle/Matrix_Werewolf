"""Tests des conditions de victoire (village, loups, couple, Loup Blanc, Mercenaire)."""

import pytest
from game.game_manager import GameManager
from models.enums import GamePhase, Team, RoleType
from models.player import Player
from roles.villageois import Villageois
from roles.loup_garou import LoupGarou
from roles.loup_blanc import LoupBlanc
from roles import RoleFactory


class TestVictoryConditions:
    """Tests des conditions de victoire."""

    def test_villagers_win(self):
        """Test la victoire des villageois."""
        gm = GameManager()

        for i in range(3):
            player = Player(f"Villager{i}", f"@v{i}:matrix.org")
            player.role = Villageois()
            player.role.assign_to_player(player)
            gm.players[player.user_id] = player

        wolf = Player("Wolf", "@wolf:matrix.org")
        wolf.role = LoupGarou()
        wolf.role.assign_to_player(wolf)
        wolf.is_alive = False
        gm.players[wolf.user_id] = wolf

        winner = gm.check_victory()
        assert winner == Team.GENTIL

    def test_wolves_win(self):
        """Test la victoire des loups."""
        gm = GameManager()

        for i in range(2):
            wolf = Player(f"Wolf{i}", f"@w{i}:matrix.org")
            wolf.role = LoupGarou()
            wolf.role.assign_to_player(wolf)
            gm.players[wolf.user_id] = wolf

        for i in range(3):
            villager = Player(f"Villager{i}", f"@v{i}:matrix.org")
            villager.role = Villageois()
            villager.role.assign_to_player(villager)
            villager.is_alive = False
            gm.players[villager.user_id] = villager

        winner = gm.check_victory()
        assert winner == Team.MECHANT

    def test_couple_win(self):
        """Test la victoire du couple."""
        gm = GameManager()

        lover1 = Player("Lover1", "@l1:matrix.org")
        lover1.role = Villageois()
        lover1.role.assign_to_player(lover1)

        lover2 = Player("Lover2", "@l2:matrix.org")
        lover2.role = LoupGarou()
        lover2.role.assign_to_player(lover2)

        lover1.lover = lover2
        lover2.lover = lover1

        gm.players[lover1.user_id] = lover1
        gm.players[lover2.user_id] = lover2

        dead_player = Player("Dead", "@dead:matrix.org")
        dead_player.role = Villageois()
        dead_player.role.assign_to_player(dead_player)
        dead_player.is_alive = False
        gm.players[dead_player.user_id] = dead_player

        winner = gm.check_victory()
        assert winner == Team.COUPLE

    def test_no_winner_yet(self):
        """Test qu'il n'y a pas encore de gagnant."""
        gm = GameManager()

        for i in range(3):
            villager = Player(f"Villager{i}", f"@v{i}:matrix.org")
            villager.role = Villageois()
            villager.role.assign_to_player(villager)
            gm.players[villager.user_id] = villager

        for i in range(2):
            wolf = Player(f"Wolf{i}", f"@w{i}:matrix.org")
            wolf.role = LoupGarou()
            wolf.role.assign_to_player(wolf)
            gm.players[wolf.user_id] = wolf

        winner = gm.check_victory()
        assert winner is None


class TestLoupBlancVictory:
    """Tests de la victoire du Loup Blanc."""

    def test_loup_blanc_solo_win(self):
        """Test que le Loup Blanc gagne seul (Team.NEUTRE)."""
        gm = GameManager()

        lb = Player("LoupBlanc", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        gm.players[lb.user_id] = lb

        dead1 = Player("Dead1", "@d1:matrix.org")
        dead1.role = Villageois()
        dead1.role.assign_to_player(dead1)
        dead1.is_alive = False
        gm.players[dead1.user_id] = dead1

        dead2 = Player("Dead2", "@d2:matrix.org")
        dead2.role = LoupGarou()
        dead2.role.assign_to_player(dead2)
        dead2.is_alive = False
        gm.players[dead2.user_id] = dead2

        winner = gm.check_win_condition()
        assert winner == Team.NEUTRE

    def test_loup_blanc_does_not_trigger_wolf_victory(self):
        """Test que le LB seul ne déclenche PAS la victoire des loups."""
        gm = GameManager()

        lb = Player("LoupBlanc", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        gm.players[lb.user_id] = lb

        villager = Player("Villager", "@v:matrix.org")
        villager.role = Villageois()
        villager.role.assign_to_player(villager)
        gm.players[villager.user_id] = villager

        winner = gm.check_win_condition()
        assert winner is None

    def test_loup_blanc_loses_with_regular_wolves(self):
        """Test que le LB perd quand les loups réguliers gagnent."""
        gm = GameManager()

        lb = Player("LoupBlanc", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        gm.players[lb.user_id] = lb

        wolf = Player("Wolf", "@w:matrix.org")
        wolf.role = LoupGarou()
        wolf.role.assign_to_player(wolf)
        gm.players[wolf.user_id] = wolf

        winner = gm.check_win_condition()
        assert winner == Team.MECHANT

    def test_loup_blanc_with_couple_win(self):
        """Test que le LB peut gagner avec son couple."""
        gm = GameManager()

        lb = Player("LoupBlanc", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)

        lover = Player("Lover", "@lover:matrix.org")
        lover.role = Villageois()
        lover.role.assign_to_player(lover)

        lb.lover = lover
        lover.lover = lb

        gm.players[lb.user_id] = lb
        gm.players[lover.user_id] = lover

        dead = Player("Dead", "@dead:matrix.org")
        dead.role = LoupGarou()
        dead.role.assign_to_player(dead)
        dead.is_alive = False
        gm.players[dead.user_id] = dead

        winner = gm.check_win_condition()
        assert winner == Team.COUPLE


class TestCoupleVictory:
    """Tests de la victoire du couple."""

    def test_couple_wins_no_team_check(self):
        """Test que le couple gagne si les 2 derniers vivants sont amoureux."""
        gm = GameManager()

        lover1 = Player("Wolf", "@w:matrix.org")
        lover1.role = LoupGarou()
        lover1.role.assign_to_player(lover1)

        lover2 = Player("Villager", "@v:matrix.org")
        lover2.role = Villageois()
        lover2.role.assign_to_player(lover2)

        lover1.lover = lover2
        lover2.lover = lover1

        gm.players[lover1.user_id] = lover1
        gm.players[lover2.user_id] = lover2

        dead = Player("Dead", "@dead:matrix.org")
        dead.role = Villageois()
        dead.role.assign_to_player(dead)
        dead.is_alive = False
        gm.players[dead.user_id] = dead

        winner = gm.check_win_condition()
        assert winner == Team.COUPLE

    def test_couple_does_not_win_with_others_alive(self):
        """Test que le couple ne gagne pas s'il reste d'autres joueurs."""
        gm = GameManager()

        lover1 = Player("L1", "@l1:matrix.org")
        lover1.role = Villageois()
        lover1.role.assign_to_player(lover1)

        lover2 = Player("L2", "@l2:matrix.org")
        lover2.role = Villageois()
        lover2.role.assign_to_player(lover2)

        lover1.lover = lover2
        lover2.lover = lover1

        other = Player("Other", "@other:matrix.org")
        other.role = LoupGarou()
        other.role.assign_to_player(other)

        gm.players[lover1.user_id] = lover1
        gm.players[lover2.user_id] = lover2
        gm.players[other.user_id] = other

        winner = gm.check_win_condition()
        assert winner is None


class TestHasEvilRole:
    """Tests de la vérification de rôle méchant."""

    def test_has_evil_role_with_wolf(self):
        """Test qu'une partie avec un loup a un rôle méchant."""
        gm = GameManager()

        v = Player("V", "@v:matrix.org")
        v.role = Villageois()
        v.role.assign_to_player(v)
        gm.players[v.user_id] = v

        w = Player("W", "@w:matrix.org")
        w.role = LoupGarou()
        w.role.assign_to_player(w)
        gm.players[w.user_id] = w

        assert gm.has_evil_role() is True

    def test_has_evil_role_without_wolf(self):
        """Test qu'une partie sans loup n'a pas de rôle méchant."""
        gm = GameManager()

        for i in range(3):
            v = Player(f"V{i}", f"@v{i}:matrix.org")
            v.role = Villageois()
            v.role.assign_to_player(v)
            gm.players[v.user_id] = v

        assert gm.has_evil_role() is False

    def test_has_evil_role_with_loup_blanc(self):
        """Test que le Loup Blanc est considéré méchant (Team.MECHANT)."""
        gm = GameManager()

        lb = Player("LB", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        gm.players[lb.user_id] = lb

        v = Player("V", "@v:matrix.org")
        v.role = Villageois()
        v.role.assign_to_player(v)
        gm.players[v.user_id] = v

        assert gm.has_evil_role() is True

    def test_start_game_fails_without_evil_role(self):
        """Test que start_game échoue sans rôle méchant."""
        gm = GameManager()
        for i in range(5):
            gm.add_player(f"Player{i}", f"user_{i}")

        result = gm.set_roles({
            RoleType.VILLAGEOIS: 5
        })

        assert result["success"] is False
        assert "méchant" in result["message"] or "obligatoire" in result["message"]


def _make_game_night(*specs) -> GameManager:
    """Crée une partie en phase NIGHT."""
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestMercenaireNeutreVictory:
    """Un Mercenaire NEUTRE ne doit pas bloquer la victoire des loups."""

    def test_neutre_mercenaire_does_not_block_wolf_victory(self):
        """Si seuls des loups + un Mercenaire NEUTRE sont vivants, les loups gagnent."""
        game = _make_game_night(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Mercenaire", "m1", RoleType.MERCENAIRE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["a1"].kill()
        game.players["b1"].kill()
        game.players["e1"].kill()

        assert game.players["m1"].get_team() == Team.NEUTRE

        result = game.check_win_condition()
        assert result == Team.MECHANT

    def test_gentil_mercenaire_blocks_wolf_victory(self):
        """Un Mercenaire devenu GENTIL bloque bien la victoire des loups."""
        game = _make_game_night(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Mercenaire", "m1", RoleType.MERCENAIRE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["m1"].role.team = Team.GENTIL

        game.players["a1"].kill()
        game.players["b1"].kill()
        game.players["e1"].kill()

        result = game.check_win_condition()
        assert result is None


class TestWinCheckAfterStartNight:
    """Vérifie que end_vote_phase revérifie la victoire après _start_night."""

    def test_loup_bavard_last_wolf_dies_village_wins(self):
        """Le Loup Bavard (dernier loup) meurt → le village gagne."""
        from roles.loup_bavard import LoupBavard

        game = GameManager()
        for pseudo, uid in [("A", "a1"), ("B", "b1"), ("C", "c1"),
                            ("D", "d1"), ("LB", "lb1")]:
            game.add_player(pseudo, uid)

        for uid in ["a1", "b1", "c1", "d1"]:
            from roles.villageois import Villageois as V
            role = V()
            role.assign_to_player(game.players[uid])
        lb_role = LoupBavard()
        lb_role.assign_to_player(game.players["lb1"])

        game.phase = GamePhase.VOTE
        game.day_count = 1
        game.night_count = 1

        lb_role.word_to_say = "fromage"
        lb_role.has_said_word = False

        result = game.end_vote_phase()

        assert not game.players["lb1"].is_alive
        assert result.get("winner") == Team.GENTIL
        assert game.phase == GamePhase.ENDED

    def test_loup_bavard_not_last_wolf_game_continues(self):
        """Un Loup Bavard meurt mais il reste d'autres loups → pas de victoire."""
        from roles.loup_bavard import LoupBavard

        game = GameManager()
        for pseudo, uid in [("A", "a1"), ("B", "b1"), ("C", "c1"),
                            ("D", "d1"), ("LB", "lb1"), ("W", "w1")]:
            game.add_player(pseudo, uid)

        for uid in ["a1", "b1", "c1", "d1"]:
            from roles.villageois import Villageois as V
            role = V()
            role.assign_to_player(game.players[uid])
        lb_role = LoupBavard()
        lb_role.assign_to_player(game.players["lb1"])
        wolf_role = LoupGarou()
        wolf_role.assign_to_player(game.players["w1"])

        game.phase = GamePhase.VOTE
        game.day_count = 1
        game.night_count = 1

        lb_role.word_to_say = "fromage"
        lb_role.has_said_word = False

        result = game.end_vote_phase()

        assert not game.players["lb1"].is_alive
        assert result.get("winner") is None
        assert game.phase == GamePhase.NIGHT


class TestWinCheckAfterStartDay:
    """Vérifie que end_night revérifie la victoire après _start_day."""

    def test_mercenaire_deadline_plus_lover_cascade(self):
        """Le Mercenaire meurt (deadline) + son amoureux (dernier loup) → village gagne."""
        from roles.mercenaire import Mercenaire

        game = GameManager()
        for pseudo, uid in [("A", "a1"), ("B", "b1"), ("C", "c1"),
                            ("Merc", "m1"), ("Wolf", "w1")]:
            game.add_player(pseudo, uid)

        for uid in ["a1", "b1", "c1"]:
            from roles.villageois import Villageois as V
            role = V()
            role.assign_to_player(game.players[uid])
        merc_role = Mercenaire()
        merc_role.assign_to_player(game.players["m1"])
        wolf_role = LoupGarou()
        wolf_role.assign_to_player(game.players["w1"])

        game.players["m1"].lover = game.players["w1"]
        game.players["w1"].lover = game.players["m1"]

        merc_role.deadline = 2
        merc_role.days_elapsed = 2
        merc_role.has_won = False

        game.phase = GamePhase.NIGHT
        game.day_count = 2
        game.night_count = 2

        result = game.end_night()

        assert not game.players["m1"].is_alive
        assert not game.players["w1"].is_alive
        assert result.get("winner") == Team.GENTIL
        assert game.phase == GamePhase.ENDED

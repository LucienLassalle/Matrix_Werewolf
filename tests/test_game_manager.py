"""Tests de base du game manager : création, phases, joueurs, intégration.

Les tests de victoire sont dans test_game_victory.py.
Les tests de mécaniques spéciales sont dans test_game_mechanics.py.
"""

import pytest
from game.game_manager import GameManager
from models.enums import GamePhase, Team, RoleType
from models.player import Player
from roles.villageois import Villageois
from roles.loup_garou import LoupGarou
from roles import RoleFactory


class TestGameManagerBasics:
    """Tests de base du game manager."""

    def test_game_creation(self):
        """Test la création d'un game manager."""
        gm = GameManager()

        assert gm.phase == GamePhase.SETUP
        assert len(gm.players) == 0
        assert gm.day_count == 0

    def test_start_game(self):
        """Test le démarrage d'une partie avec player_ids."""
        gm = GameManager()

        player_ids = [f"@player{i}:matrix.org" for i in range(8)]
        gm.start_game(player_ids)

        assert gm.phase == GamePhase.NIGHT
        assert len(gm.players) == 8
        assert gm.day_count == 0

        for player in gm.players.values():
            assert player.role is not None

    def test_minimum_players(self):
        """Test qu'il faut un minimum de joueurs."""
        gm = GameManager()

        result = gm.start_game(["@player1:matrix.org"])
        assert result["success"] == False


class TestGamePhases:
    """Tests des phases de jeu."""

    def test_night_phase(self):
        """Test la phase de nuit."""
        gm = GameManager()

        player_ids = [f"@player{i}:matrix.org" for i in range(8)]
        gm.start_game(player_ids)

        assert gm.phase == GamePhase.NIGHT

    def test_day_phase_transition(self):
        """Test la transition nuit → jour."""
        gm = GameManager()

        player_ids = [f"@player{i}:matrix.org" for i in range(8)]
        gm.start_game(player_ids)

        gm.set_phase(GamePhase.DAY)
        assert gm.phase == GamePhase.DAY

    def test_vote_phase(self):
        """Test la phase de vote."""
        gm = GameManager()

        player_ids = [f"@player{i}:matrix.org" for i in range(8)]
        gm.start_game(player_ids)
        gm.night_count = 1

        result = gm.start_vote_phase()
        if gm.phase == GamePhase.NIGHT:
            gm.set_phase(GamePhase.DAY)
            result = gm.start_vote_phase()

        assert gm.phase == GamePhase.VOTE


class TestPlayerManagement:
    """Tests de la gestion des joueurs."""

    def test_get_player(self):
        """Test la récupération d'un joueur."""
        gm = GameManager()

        player = Player("Alice", "@alice:matrix.org")
        player.role = Villageois()
        player.role.assign_to_player(player)
        gm.players[player.user_id] = player

        retrieved = gm.get_player("@alice:matrix.org")
        assert retrieved == player
        assert retrieved.pseudo == "Alice"

    def test_get_alive_players(self):
        """Test la récupération des joueurs vivants."""
        gm = GameManager()

        alive1 = Player("Alive1", "@a1:matrix.org")
        alive1.role = Villageois()
        gm.players[alive1.user_id] = alive1

        alive2 = Player("Alive2", "@a2:matrix.org")
        alive2.role = Villageois()
        gm.players[alive2.user_id] = alive2

        dead = Player("Dead", "@dead:matrix.org")
        dead.role = Villageois()
        dead.is_alive = False
        gm.players[dead.user_id] = dead

        alive_players = gm.get_living_players()
        assert len(alive_players) == 2
        assert dead not in alive_players

    def test_get_wolves(self):
        """Test la récupération des loups."""
        gm = GameManager()

        wolf1 = Player("Wolf1", "@w1:matrix.org")
        wolf1.role = LoupGarou()
        wolf1.role.assign_to_player(wolf1)
        gm.players[wolf1.user_id] = wolf1

        wolf2 = Player("Wolf2", "@w2:matrix.org")
        wolf2.role = LoupGarou()
        wolf2.role.assign_to_player(wolf2)
        gm.players[wolf2.user_id] = wolf2

        villager = Player("Villager", "@v:matrix.org")
        villager.role = Villageois()
        villager.role.assign_to_player(villager)
        gm.players[villager.user_id] = villager

        wolves = gm.get_living_wolves()
        assert len(wolves) == 2
        assert villager not in wolves


class TestIntegration:
    """Tests d'intégration complets."""

    def test_full_game_cycle(self):
        """Test un cycle complet de jeu."""
        gm = GameManager()

        player_ids = [f"@player{i}:matrix.org" for i in range(8)]
        gm.start_game(player_ids)

        assert gm.phase == GamePhase.NIGHT
        assert gm.day_count == 0

        results = gm.resolve_night()

        gm.set_phase(GamePhase.DAY)
        assert gm.phase == GamePhase.DAY

        gm.set_phase(GamePhase.VOTE)
        assert gm.phase == GamePhase.VOTE

        winner = gm.check_victory()

    def test_game_with_multiple_roles(self):
        """Test une partie avec plusieurs rôles différents."""
        gm = GameManager()

        player_ids = [f"@player{i}:matrix.org" for i in range(10)]
        gm.start_game(player_ids)

        role_types = set()
        for player in gm.players.values():
            role_types.add(player.role.role_type)

        assert len(role_types) >= 2


class TestGetPlayerByPseudo:
    """Vérifie la recherche étendue de joueurs."""

    def test_by_pseudo(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("Alice") is not None

    def test_by_pseudo_case_insensitive(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("alice") is not None

    def test_by_matrix_id(self):
        game = GameManager()
        game.add_player("Alice", "@alice:matrix.org")
        p = game.get_player_by_pseudo("@alice:matrix.org")
        assert p is not None
        assert p.user_id == "@alice:matrix.org"

    def test_by_partial_matrix_id(self):
        game = GameManager()
        game.add_player("Alice", "@alice:matrix.org")
        p = game.get_player_by_pseudo("alice:matrix.org")
        assert p is not None

    def test_by_display_name(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        game.players["user_1"].display_name = "Alice Wonderland"
        p = game.get_player_by_pseudo("Alice Wonderland")
        assert p is not None

    def test_not_found(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("NotExist") is None

"""Tests pour la persistance des inscriptions et la sauvegarde des résultats."""

import os
import pytest
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from database.game_db import GameDatabase
from game.game_manager import GameManager
from models.enums import GamePhase, Team, RoleType
from models.player import Player
from roles import RoleFactory


# ==================== Tests GameDatabase — Inscriptions ====================

class TestRegistrationPersistence:
    """Vérifie que les inscriptions sont correctement stockées en BDD."""
    
    def setup_method(self):
        """Crée une BDD temporaire pour chaque test."""
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = GameDatabase(self.tmp.name)
    
    def teardown_method(self):
        self.db.close()
        os.unlink(self.tmp.name)
    
    def test_save_and_load_registration(self):
        """Une inscription sauvegardée est retrouvée après rechargement."""
        self.db.save_registration("@alice:server.com", "alice")
        
        regs = self.db.load_registrations()
        assert regs == {"@alice:server.com": "alice"}
    
    def test_multiple_registrations(self):
        """Plusieurs inscriptions sont toutes retrouvées."""
        self.db.save_registration("@alice:server.com", "alice")
        self.db.save_registration("@bob:server.com", "bob")
        self.db.save_registration("@charlie:server.com", "charlie")
        
        regs = self.db.load_registrations()
        assert len(regs) == 3
        assert regs["@alice:server.com"] == "alice"
        assert regs["@bob:server.com"] == "bob"
        assert regs["@charlie:server.com"] == "charlie"
    
    def test_duplicate_registration_updates(self):
        """Une double inscription met à jour le display_name."""
        self.db.save_registration("@alice:server.com", "alice")
        self.db.save_registration("@alice:server.com", "Alice_New")
        
        regs = self.db.load_registrations()
        assert len(regs) == 1
        assert regs["@alice:server.com"] == "Alice_New"
    
    def test_remove_registration(self):
        """La suppression d'une inscription fonctionne."""
        self.db.save_registration("@alice:server.com", "alice")
        self.db.save_registration("@bob:server.com", "bob")
        
        self.db.remove_registration("@alice:server.com")
        
        regs = self.db.load_registrations()
        assert len(regs) == 1
        assert "@alice:server.com" not in regs
        assert "@bob:server.com" in regs
    
    def test_clear_registrations(self):
        """Le vidage des inscriptions supprime tout."""
        self.db.save_registration("@alice:server.com", "alice")
        self.db.save_registration("@bob:server.com", "bob")
        
        self.db.clear_registrations()
        
        regs = self.db.load_registrations()
        assert regs == {}
    
    def test_load_empty_registrations(self):
        """Le chargement sans inscriptions retourne un dict vide."""
        regs = self.db.load_registrations()
        assert regs == {}
    
    def test_registrations_survive_reconnection(self):
        """Les inscriptions persistent après fermeture et réouverture de la BDD."""
        self.db.save_registration("@alice:server.com", "alice")
        self.db.save_registration("@bob:server.com", "bob")
        
        # Fermer et rouvrir
        self.db.close()
        db2 = GameDatabase(self.tmp.name)
        
        regs = db2.load_registrations()
        assert len(regs) == 2
        assert regs["@alice:server.com"] == "alice"
        
        db2.close()


# ==================== Tests GameDatabase — Détection crash ====================

class TestCrashDetection:
    """Vérifie la détection de partie en cours (crash recovery)."""
    
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = GameDatabase(self.tmp.name)
    
    def teardown_method(self):
        self.db.close()
        os.unlink(self.tmp.name)
    
    def test_no_active_game_by_default(self):
        """Pas de partie active par défaut."""
        assert self.db.has_active_game() is False
    
    def test_active_game_detected(self):
        """Une partie NIGHT est détectée comme active."""
        players = self._make_players(5)
        self.db.save_game_state(
            phase=GamePhase.NIGHT,
            day_count=1,
            start_time=datetime.now(),
            players=players,
            votes={},
            wolf_votes={}
        )
        assert self.db.has_active_game() is True
    
    def test_ended_game_not_active(self):
        """Une partie ENDED n'est pas active."""
        players = self._make_players(5)
        self.db.save_game_state(
            phase=GamePhase.ENDED,
            day_count=3,
            start_time=datetime.now(),
            players=players,
            votes={},
            wolf_votes={}
        )
        assert self.db.has_active_game() is False
    
    def test_setup_game_not_active(self):
        """Une partie SETUP n'est pas active."""
        players = self._make_players(5)
        self.db.save_game_state(
            phase=GamePhase.SETUP,
            day_count=0,
            start_time=datetime.now(),
            players=players,
            votes={},
            wolf_votes={}
        )
        assert self.db.has_active_game() is False
    
    def test_cleared_game_not_active(self):
        """Après clear_current_game, pas de partie active."""
        players = self._make_players(5)
        self.db.save_game_state(
            phase=GamePhase.NIGHT,
            day_count=1,
            start_time=datetime.now(),
            players=players,
            votes={},
            wolf_votes={}
        )
        self.db.clear_current_game()
        assert self.db.has_active_game() is False
    
    def _make_players(self, count):
        """Crée des joueurs factices avec rôles."""
        players = {}
        for i in range(count):
            uid = f"@player{i}:server.com"
            p = Player(f"player{i}", uid)
            role = RoleFactory.create_role(
                RoleType.LOUP_GAROU if i == 0 else RoleType.VILLAGEOIS
            )
            role.assign_to_player(p)
            players[uid] = p
        return players


# ==================== Tests GameManager — Reset ====================

class TestGameManagerReset:
    """Vérifie que le reset du GameManager fonctionne correctement."""
    
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.gm = GameManager(db_path=self.tmp.name)
    
    def teardown_method(self):
        self.gm.db.close()
        os.unlink(self.tmp.name)
    
    def test_reset_clears_players(self):
        """Reset vide les joueurs."""
        self.gm.add_player("alice", "@alice:s")
        self.gm.add_player("bob", "@bob:s")
        
        self.gm.reset()
        
        assert len(self.gm.players) == 0
        assert len(self.gm._player_order) == 0
    
    def test_reset_restores_setup_phase(self):
        """Reset remet la phase à SETUP."""
        self.gm.phase = GamePhase.ENDED
        
        self.gm.reset()
        
        assert self.gm.phase == GamePhase.SETUP
    
    def test_reset_clears_counters(self):
        """Reset remet les compteurs à zéro."""
        self.gm.day_count = 5
        self.gm.night_count = 5
        
        self.gm.reset()
        
        assert self.gm.day_count == 0
        assert self.gm.night_count == 0
    
    def test_reset_generates_new_game_id(self):
        """Reset génère un nouvel ID de partie."""
        old_id = self.gm.game_id
        
        self.gm.reset()
        
        assert self.gm.game_id != old_id
    
    def test_reset_clears_roles(self):
        """Reset vide les rôles disponibles."""
        self.gm.available_roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))
        self.gm.extra_roles.append(RoleFactory.create_role(RoleType.LOUP_GAROU))
        
        self.gm.reset()
        
        assert len(self.gm.available_roles) == 0
        assert len(self.gm.extra_roles) == 0
    
    def test_reset_preserves_db(self):
        """Reset conserve la connexion BDD."""
        db_ref = self.gm.db
        
        self.gm.reset()
        
        assert self.gm.db is db_ref
    
    def test_reset_preserves_cupidon_config(self):
        """Reset conserve la config cupidon_wins_with_couple."""
        self.gm.cupidon_wins_with_couple = False
        
        self.gm.reset()
        
        # La config est préservée (pas réinitialisée)
        assert self.gm.cupidon_wins_with_couple is False
    
    def test_start_game_after_reset(self):
        """Après reset, start_game fonctionne normalement."""
        # Première partie
        ids = [f"@p{i}:s" for i in range(6)]
        result = self.gm.start_game(ids)
        assert result["success"] is True
        
        # Fin de partie
        self.gm.end_game(Team.GENTIL)
        assert self.gm.phase == GamePhase.ENDED
        
        # Reset
        self.gm.reset()
        assert self.gm.phase == GamePhase.SETUP
        
        # Deuxième partie
        ids2 = [f"@q{i}:s" for i in range(6)]
        result2 = self.gm.start_game(ids2)
        assert result2["success"] is True
        assert len(self.gm.players) == 6
    
    def test_reset_clears_pending_mayor_succession(self):
        """Reset annule la succession de maire en cours."""
        p = Player("test", "@test:s")
        self.gm._pending_mayor_succession = p
        
        self.gm.reset()
        
        assert self.gm._pending_mayor_succession is None


# ==================== Tests GameManager — end_game saves results ====================

class TestEndGameSavesResults:
    """Vérifie que end_game() sauvegarde correctement les résultats."""
    
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.gm = GameManager(db_path=self.tmp.name)
    
    def teardown_method(self):
        self.gm.db.close()
        os.unlink(self.tmp.name)
    
    def test_end_game_saves_to_history(self):
        """end_game sauvegarde la partie dans l'historique."""
        ids = [f"@p{i}:s" for i in range(6)]
        self.gm.start_game(ids)
        
        # Vérifier qu'il n'y a pas encore d'historique
        assert self.gm.db.is_first_run()
        
        self.gm.end_game(Team.GENTIL)
        
        # L'historique devrait maintenant avoir 1 entrée
        assert not self.gm.db.is_first_run()
    
    def test_end_game_populates_leaderboard(self):
        """end_game met à jour le leaderboard."""
        ids = [f"@p{i}:s" for i in range(6)]
        self.gm.start_game(ids)
        
        self.gm.end_game(Team.GENTIL)
        
        leaderboard = self.gm.db.get_leaderboard()
        assert len(leaderboard) > 0
    
    def test_end_game_clears_current_game(self):
        """end_game nettoie l'état du jeu en cours."""
        ids = [f"@p{i}:s" for i in range(6)]
        self.gm.start_game(ids)
        
        # Vérifier qu'il y a un état sauvegardé
        assert self.gm.db.has_active_game()
        
        self.gm.end_game(Team.GENTIL)
        
        # L'état doit être nettoyé
        assert not self.gm.db.has_active_game()
    
    def test_end_game_sets_phase_ended(self):
        """end_game met la phase à ENDED."""
        ids = [f"@p{i}:s" for i in range(6)]
        self.gm.start_game(ids)
        
        self.gm.end_game(Team.GENTIL)
        
        assert self.gm.phase == GamePhase.ENDED


# ==================== Tests Chasseur — killed_during_day ====================

class TestChasseurKilledDuringDay:
    """Vérifie que le Chasseur propage correctement killed_during_day."""
    
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.gm = GameManager(db_path=self.tmp.name)
    
    def teardown_method(self):
        self.gm.db.close()
        os.unlink(self.tmp.name)
    
    def test_chasseur_killed_at_night_shoots_during_day(self):
        """Le Chasseur tué la nuit tire de jour (killed_during_day=True)."""
        from roles.chasseur import Chasseur
        from models.enums import ActionType
        
        # Setup
        chasseur_player = Player("hunter", "@hunter:s")
        target = Player("target", "@target:s")
        
        role = Chasseur()
        role.assign_to_player(chasseur_player)
        target_role = RoleFactory.create_role(RoleType.VILLAGEOIS)
        target_role.assign_to_player(target)
        
        self.gm.players["@hunter:s"] = chasseur_player
        self.gm.players["@target:s"] = target
        
        # Tuer le chasseur de nuit
        role.on_player_death(self.gm, chasseur_player, killed_during_day=False)
        chasseur_player.is_alive = False
        
        assert role.killed_during_day is False
        assert role.can_shoot_now is True
        
        # Le chasseur tire → killed_during_day devrait être True (inverse de sa mort)
        result = role.perform_action(self.gm, ActionType.KILL, target)
        assert result["success"] is True
        assert not target.is_alive
    
    def test_chasseur_killed_during_day_shoots_at_night(self):
        """Le Chasseur tué le jour tire la nuit (killed_during_day=False)."""
        from roles.chasseur import Chasseur
        from models.enums import ActionType
        
        chasseur_player = Player("hunter", "@hunter:s")
        target = Player("target", "@target:s")
        
        role = Chasseur()
        role.assign_to_player(chasseur_player)
        target_role = RoleFactory.create_role(RoleType.VILLAGEOIS)
        target_role.assign_to_player(target)
        
        self.gm.players["@hunter:s"] = chasseur_player
        self.gm.players["@target:s"] = target
        
        # Tuer le chasseur de jour
        role.on_player_death(self.gm, chasseur_player, killed_during_day=True)
        chasseur_player.is_alive = False
        
        assert role.killed_during_day is True
        assert role.can_shoot_now is True
        
        # Le chasseur tire
        result = role.perform_action(self.gm, ActionType.KILL, target)
        assert result["success"] is True


# ==================== Tests _start_game retourne bool ====================

class TestStartGameReturnsBool:
    """Vérifie que _start_game retourne True/False correctement."""
    
    @pytest.fixture
    def mock_bot(self):
        """Crée un bot minimal avec mocks."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        
        bot = MagicMock()
        bot.registered_players = {f"@p{i}:s": f"p{i}" for i in range(6)}
        bot.game_manager = GameManager(db_path=tmp.name)
        bot.game_manager.cupidon_wins_with_couple = True
        bot.client = AsyncMock()
        bot.client.send_message = AsyncMock()
        bot._accepting_registrations = True
        bot._game_events = []
        bot.room_manager = AsyncMock()
        bot.notification_manager = AsyncMock()
        bot.message_handler = MagicMock()
        bot._night_hour = 21
        bot._tmp_path = tmp.name
        
        yield bot
        
        bot.game_manager.db.close()
        os.unlink(tmp.name)
    
    @pytest.mark.asyncio
    async def test_start_game_not_enough_players(self, mock_bot):
        """start_game retourne False avec < 5 joueurs."""
        from matrix_bot.bot_controller import WerewolfBot
        
        mock_bot.registered_players = {"@p0:s": "p0", "@p1:s": "p1"}
        
        # Appeler _start_game comme méthode non-liée
        result = await WerewolfBot._start_game(mock_bot)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_start_game_enough_players(self, mock_bot):
        """start_game retourne True avec >= 5 joueurs."""
        from matrix_bot.bot_controller import WerewolfBot
        
        mock_bot.registered_players = {f"@p{i}:s": f"p{i}" for i in range(6)}
        
        # _create_special_rooms, _send_role_notifications, _build_roles_announcement
        # doivent être des AsyncMock ou des MagicMock retournant des coroutines
        mock_bot._create_special_rooms = AsyncMock()
        mock_bot._send_role_notifications = AsyncMock()
        mock_bot._build_roles_announcement = MagicMock(return_value="test roles")
        
        result = await WerewolfBot._start_game(mock_bot)
        assert result is True

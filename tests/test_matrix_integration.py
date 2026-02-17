"""Tests complets de l'intégration Matrix."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, time

from matrix_bot.room_manager import RoomManager
from matrix_bot.scheduler import GameScheduler, wait_until_new_game, day_name_fr
from matrix_bot.message_handler import MessageHandler
from matrix_bot.notifications import NotificationManager
from matrix_bot.bot_controller import WerewolfBot
from models.enums import GamePhase


class TestRoomManager:
    """Tests du gestionnaire de salons."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock du client Matrix."""
        client = Mock()
        client.create_room = AsyncMock(return_value="!room123:matrix.org")
        client.send_message = AsyncMock()
        client.send_dm = AsyncMock()
        client.invite_user = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_create_all_rooms(self, mock_client):
        """Test la création de tous les salons."""
        rm = RoomManager(mock_client, "!space:matrix.org")
        
        player_ids = ["@p1:matrix.org", "@p2:matrix.org", "@p3:matrix.org"]
        rooms = await rm.create_all_rooms(player_ids)
        
        assert "village" in rooms
        assert "dead" in rooms
        assert rm.village_room is not None
        assert rm.dead_room is not None
    
    @pytest.mark.asyncio
    async def test_create_wolves_room(self, mock_client):
        """Test la création du salon des loups."""
        rm = RoomManager(mock_client, "!space:matrix.org")
        
        wolf_ids = ["@wolf1:matrix.org", "@wolf2:matrix.org"]
        wolves_room = await rm.create_wolves_room(wolf_ids)
        
        assert wolves_room is not None
        assert rm.wolves_room is not None
    
    @pytest.mark.asyncio
    async def test_create_couple_room(self, mock_client):
        """Test la création du salon du couple."""
        rm = RoomManager(mock_client, "!space:matrix.org")
        
        lover_ids = ["@lover1:matrix.org", "@lover2:matrix.org"]
        couple_room = await rm.create_couple_room(lover_ids)
        
        assert couple_room is not None
        assert rm.couple_room is not None
    
    @pytest.mark.asyncio
    async def test_send_to_village(self, mock_client):
        """Test l'envoi de message au village."""
        rm = RoomManager(mock_client, "!space:matrix.org")
        rm.village_room = "!village:matrix.org"
        
        await rm.send_to_village("Test message")
        
        mock_client.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_rooms(self, mock_client):
        """Test le nettoyage des salons (suppression réelle)."""
        mock_client.get_room_members = AsyncMock(return_value=["@p1:matrix.org", "@bot:matrix.org"])
        mock_client.kick_user = AsyncMock()
        mock_client.delete_room = AsyncMock()
        mock_client.remove_room_from_space = AsyncMock()
        mock_client.user_id = "@bot:matrix.org"
        inner_client = Mock()
        inner_client.room_forget = AsyncMock()
        mock_client.client = inner_client
        
        rm = RoomManager(mock_client, "!space:matrix.org")
        rm.village_room = "!village:matrix.org"
        rm.wolves_room = "!wolves:matrix.org"
        
        await rm.cleanup_rooms()
        
        assert rm.village_room is None
        assert rm.wolves_room is None
        # Vérifie que les rooms sont bien supprimées
        assert mock_client.get_room_members.call_count >= 2
        assert mock_client.kick_user.call_count >= 2  # 1 per room (non-bot member)
        assert mock_client.delete_room.call_count >= 2


class TestGameScheduler:
    """Tests du planificateur de jeu."""
    
    def test_scheduler_initialization(self):
        """Test l'initialisation du scheduler."""
        scheduler = GameScheduler(
            night_start=time(21, 0),
            day_start=time(8, 0),
            vote_start=time(19, 0)
        )
        
        assert scheduler.night_start == time(21, 0)
        assert scheduler.day_start == time(8, 0)
        assert scheduler.vote_start == time(19, 0)
        assert scheduler.current_day == 0
    
    def test_start_game(self):
        """Test le démarrage du planning."""
        scheduler = GameScheduler()
        
        start_time = datetime.now()
        scheduler.start_game(start_time)
        
        assert scheduler.game_start_time == start_time
        assert scheduler.current_day == 1
        assert scheduler._running is True
    
    def test_stop_game(self):
        """Test l'arrêt du planning."""
        scheduler = GameScheduler()
        scheduler.start_game()
        
        scheduler.stop()
        
        assert scheduler._running is False
    
    def test_get_phase_name(self):
        """Test la récupération du nom de phase."""
        scheduler = GameScheduler()
        
        assert scheduler.get_phase_name(GamePhase.NIGHT) == "Nuit"
        assert scheduler.get_phase_name(GamePhase.DAY) == "Jour"
        assert scheduler.get_phase_name(GamePhase.VOTE) == "Vote"


class TestMessageHandler:
    """Tests du gestionnaire de messages."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock du client nio."""
        client = Mock()
        client.add_event_callback = Mock()
        return client
    
    def test_message_handler_creation(self, mock_client):
        """Test la création du message handler."""
        handler = MessageHandler(mock_client, "@bot:matrix.org")
        
        assert handler.bot_user_id == "@bot:matrix.org"
        assert handler.client == mock_client
    
    def test_parse_target(self):
        """Test le parsing d'une cible."""
        target = MessageHandler.parse_target(["Alice"])
        assert target == "Alice"
        
        target = MessageHandler.parse_target(["@Alice:matrix.org"])
        assert target == "Alice:matrix.org"
        
        target = MessageHandler.parse_target(["Bob", "Smith"])
        assert target == "Bob Smith"
    
    def test_extract_user_id(self):
        """Test l'extraction du nom d'utilisateur."""
        username = MessageHandler.extract_user_id("@alice:matrix.org")
        assert username == "alice"
        
        username = MessageHandler.extract_user_id("bob")
        assert username == "bob"


class TestNotificationManager:
    """Tests du gestionnaire de notifications."""
    
    @pytest.fixture
    def mock_room_manager(self):
        """Mock du room manager."""
        rm = Mock()
        rm.send_dm = AsyncMock()
        return rm
    
    def test_notification_manager_creation(self, mock_room_manager):
        """Test la création du notification manager."""
        nm = NotificationManager(mock_room_manager)
        
        assert nm.room_manager == mock_room_manager
    
    @pytest.mark.asyncio
    async def test_send_role_assignment(self, mock_room_manager):
        """Test l'envoi d'une assignation de rôle."""
        from roles.villageois import Villageois
        
        nm = NotificationManager(mock_room_manager)
        role = Villageois()
        
        await nm.send_role_assignment("@player:matrix.org", role)
        
        mock_room_manager.send_dm.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_death_notification(self, mock_room_manager):
        """Test l'envoi d'une notification de mort."""
        from roles.chasseur import Chasseur
        
        nm = NotificationManager(mock_room_manager)
        role = Chasseur()
        
        await nm.send_death_notification("@player:matrix.org", role)
        
        mock_room_manager.send_dm.assert_called_once()
        # Vérifier que le message mentionne le chasseur
        call_args = mock_room_manager.send_dm.call_args
        assert "Chasseur" in call_args[0][1]


class TestBotController:
    """Tests du contrôleur principal du bot."""
    
    @pytest.fixture
    def bot(self):
        """Crée un bot pour les tests."""
        return WerewolfBot(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            access_token="test_token",
            space_id="!space:matrix.org",
            lobby_room_id="!lobby:matrix.org"
        )
    
    def test_bot_creation(self, bot):
        """Test la création du bot."""
        assert bot.homeserver == "https://matrix.org"
        assert bot.user_id == "@bot:matrix.org"
        assert bot.space_id == "!space:matrix.org"
        assert bot.lobby_room_id == "!lobby:matrix.org"
        assert bot.running is False
    
    @pytest.mark.asyncio
    async def test_handle_registration(self, bot):
        """Test la gestion d'une inscription."""
        bot.lobby_room_id = "!lobby:matrix.org"
        bot.client.send_message = AsyncMock()
        
        # Initialiser message_handler si None
        if bot.message_handler is None:
            bot.message_handler = Mock()
            bot.message_handler.extract_user_id = Mock(return_value='alice')
        else:
            with patch.object(bot.message_handler, 'extract_user_id', return_value='alice'):
                pass
        await bot._handle_registration("!lobby:matrix.org", "@alice:matrix.org")
        
        assert "@alice:matrix.org" in bot.registered_players
    
    def test_game_manager_integration(self, bot):
        """Test l'intégration avec le game manager."""
        assert bot.game_manager is not None
        assert bot.command_handler is not None
        assert bot.command_handler.game_manager == bot.game_manager


class TestIntegration:
    """Tests d'intégration complets."""
    
    @pytest.mark.asyncio
    async def test_room_creation_flow(self):
        """Test le flux complet de création de salons."""
        mock_client = Mock()
        mock_client.create_room = AsyncMock(return_value="!room:matrix.org")
        mock_client.send_message = AsyncMock()
        mock_client.invite_user = AsyncMock()
        
        rm = RoomManager(mock_client, "!space:matrix.org")
        
        # Créer tous les salons
        player_ids = [f"@p{i}:matrix.org" for i in range(8)]
        await rm.create_all_rooms(player_ids)
        
        # Créer salon des loups
        wolf_ids = [f"@w{i}:matrix.org" for i in range(2)]
        await rm.create_wolves_room(wolf_ids)
        
        # Vérifier que tout est créé
        assert rm.village_room is not None
        assert rm.wolves_room is not None
        assert rm.dead_room is not None
    
    def test_scheduler_phase_transitions(self):
        """Test les transitions de phases."""
        scheduler = GameScheduler()
        phases_called = []
        
        def on_phase(phase):
            phases_called.append(phase)
        
        scheduler.on_night_start = on_phase
        scheduler.on_day_start = on_phase
        scheduler.on_vote_start = on_phase
        
        scheduler.start_game()
        
        # Le scheduler devrait être en cours
        assert scheduler._running is True


class TestEdgeCases:
    """Tests des cas limites."""
    
    @pytest.mark.asyncio
    async def test_empty_wolf_list(self):
        """Test avec une liste de loups vide."""
        mock_client = Mock()
        mock_client.create_room = AsyncMock(return_value="!room:matrix.org")
        
        rm = RoomManager(mock_client, "!space:matrix.org")
        
        # Ne devrait pas créer de salon
        room = await rm.create_wolves_room([])
        assert room is None
    
    @pytest.mark.asyncio
    async def test_invalid_couple(self):
        """Test avec un couple invalide (pas 2 joueurs)."""
        mock_client = Mock()
        mock_client.create_room = AsyncMock(return_value="!room:matrix.org")
        
        rm = RoomManager(mock_client, "!space:matrix.org")
        
        # Un seul amoureux (invalide)
        room = await rm.create_couple_room(["@lover:matrix.org"])
        assert room is None
        
        # Trois amoureux (invalide)
        room = await rm.create_couple_room(["@l1:matrix.org", "@l2:matrix.org", "@l3:matrix.org"])
        assert room is None
    
    def test_scheduler_without_start(self):
        """Test le scheduler sans démarrage."""
        scheduler = GameScheduler()
        
        # Devrait retourner None
        time_delta = scheduler.get_time_until_next_phase()
        assert time_delta is None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])


class TestRoomTypeHelpers:
    """Tests des helpers d'identification de salon."""
    
    @pytest.fixture
    def room_manager(self):
        """Crée un RoomManager avec des rooms assignées."""
        client = Mock()
        rm = RoomManager(client, "!space:matrix.org")
        rm.village_room = "!village:matrix.org"
        rm.wolves_room = "!wolves:matrix.org"
        rm.couple_room = "!couple:matrix.org"
        rm.dead_room = "!dead:matrix.org"
        rm.lobby_room = "!lobby:matrix.org"
        return rm
    
    def test_is_village_room(self, room_manager):
        """Test identification du salon village."""
        assert room_manager.is_village_room("!village:matrix.org") is True
        assert room_manager.is_village_room("!wolves:matrix.org") is False
        assert room_manager.is_village_room("!random:matrix.org") is False
    
    def test_is_wolves_room(self, room_manager):
        """Test identification du salon des loups."""
        assert room_manager.is_wolves_room("!wolves:matrix.org") is True
        assert room_manager.is_wolves_room("!village:matrix.org") is False
    
    def test_is_couple_room(self, room_manager):
        """Test identification du salon du couple."""
        assert room_manager.is_couple_room("!couple:matrix.org") is True
        assert room_manager.is_couple_room("!village:matrix.org") is False
    
    def test_is_dm_room(self, room_manager):
        """Test identification d'un salon DM (tout salon inconnu)."""
        assert room_manager.is_dm_room("!dm_random:matrix.org") is True
        # Les salons connus ne sont PAS des DMs
        assert room_manager.is_dm_room("!village:matrix.org") is False
        assert room_manager.is_dm_room("!wolves:matrix.org") is False
        assert room_manager.is_dm_room("!couple:matrix.org") is False
        assert room_manager.is_dm_room("!dead:matrix.org") is False
        assert room_manager.is_dm_room("!lobby:matrix.org") is False


class TestDeleteRoom:
    """Tests de la suppression de salons."""
    
    @pytest.mark.asyncio
    async def test_delete_room_kicks_members_and_leaves(self):
        """Test que delete_room kick les membres puis quitte."""
        client = Mock()
        client.user_id = "@bot:matrix.org"
        client.get_room_members = AsyncMock(return_value=[
            "@p1:matrix.org", "@p2:matrix.org", "@bot:matrix.org"
        ])
        client.kick_user = AsyncMock()
        client.delete_room = AsyncMock()
        client.remove_room_from_space = AsyncMock()
        inner_client = Mock()
        inner_client.room_forget = AsyncMock()
        client.client = inner_client
        
        rm = RoomManager(client, "!space:matrix.org")
        await rm.delete_room("!room:matrix.org")
        
        # Bot ne se kick pas lui-même
        assert client.kick_user.call_count == 2
        client.kick_user.assert_any_call("!room:matrix.org", "@p1:matrix.org", "Partie terminée")
        client.kick_user.assert_any_call("!room:matrix.org", "@p2:matrix.org", "Partie terminée")
        # Bot quitte le salon
        client.delete_room.assert_called_once_with("!room:matrix.org")
    
    @pytest.mark.asyncio
    async def test_delete_room_handles_none(self):
        """Test que delete_room ne fait rien avec None."""
        client = Mock()
        client.get_room_members = AsyncMock()
        
        rm = RoomManager(client, "!space:matrix.org")
        await rm.delete_room(None)
        
        client.get_room_members.assert_not_called()


class TestRegistrationBlocking:
    """Tests du blocage des inscriptions pendant une partie."""
    
    @pytest.fixture
    def bot(self):
        bot = WerewolfBot(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            access_token="test_token",
            space_id="!space:matrix.org",
            lobby_room_id="!lobby:matrix.org"
        )
        bot.client.send_message = AsyncMock()
        bot.message_handler = Mock()
        bot.message_handler.extract_user_id = Mock(return_value='alice')
        return bot
    
    @pytest.mark.asyncio
    async def test_registration_open_by_default(self, bot):
        """Test que les inscriptions sont ouvertes par défaut."""
        assert bot._accepting_registrations is True
    
    @pytest.mark.asyncio
    async def test_registration_blocked_during_game(self, bot):
        """Test que les inscriptions sont refusées pendant une partie."""
        bot._accepting_registrations = False
        
        await bot._handle_registration("!lobby:matrix.org", "@alice:matrix.org")
        
        assert "@alice:matrix.org" not in bot.registered_players
        bot.client.send_message.assert_called_once()
        call_args = bot.client.send_message.call_args
        assert "fermées" in call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_registration_works_when_open(self, bot):
        """Test que les inscriptions fonctionnent quand ouvertes."""
        await bot._handle_registration("!lobby:matrix.org", "@alice:matrix.org")
        
        assert "@alice:matrix.org" in bot.registered_players

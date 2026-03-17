"""Contrôleur principal du bot Werewolf.

La logique est répartie en trois fichiers via des mixins :
- bot_controller.py  : cycle de vie, boucle de jeu, commandes, UI
- phase_handlers.py  : transitions de phase (nuit → jour → vote)
- role_handlers.py   : événements liés aux rôles spéciaux
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional


from matrix_bot.matrix_client import MatrixClientWrapper
from matrix_bot.room_manager import RoomManager
from matrix_bot.scheduler import GameScheduler
from matrix_bot.message_handler import MessageHandler
from matrix_bot.phase_handlers import PhaseHandlersMixin
from matrix_bot.role_handlers import RoleHandlersMixin
from matrix_bot.ui_builders import UIBuildersMixin
from matrix_bot.command_router import CommandRouterMixin
from matrix_bot.bot_lifecycle import BotLifecycleMixin
from matrix_bot.bot_rooms import BotRoomsMixin
from matrix_bot.bot_message_handlers import BotMessageHandlersMixin
from matrix_bot.bot_notifications import BotNotificationsMixin
from matrix_bot.notifications import NotificationManager

from game.game_manager import GameManager
from game.leaderboard import LeaderboardManager
from commands.command_handler import CommandHandler
from models.enums import GamePhase, Team, RoleType
from models.player import Player
from utils.message_distortion import MessageDistorter

logger = logging.getLogger(__name__)


class WerewolfBot(
    BotLifecycleMixin,
    BotRoomsMixin,
    BotMessageHandlersMixin,
    BotNotificationsMixin,
    PhaseHandlersMixin,
    RoleHandlersMixin,
    UIBuildersMixin,
    CommandRouterMixin,
):
    """Bot Matrix pour gérer une partie de Loup-Garou."""
    
    def __init__(
        self,
        homeserver: str,
        user_id: str,
        access_token: str,
        space_id: str,
        lobby_room_id: str,
        password: str = None,
        test_user_id: str = None,
        test_user_password: str = None,
        test_user_token: str = None,
        test_user2_id: str = None,
        test_user2_password: str = None,
        test_user2_token: str = None,
        runtests: bool = False,
        disabled_roles: set = None
    ):
        # Configuration
        self.homeserver = homeserver
        self.user_id = user_id
        self.space_id = space_id
        self.lobby_room_id = lobby_room_id
        
        # Configuration des comptes de test
        self._test_user_id = test_user_id
        self._test_user_password = test_user_password
        self._test_user_token = test_user_token
        self._test_user2_id = test_user2_id
        self._test_user2_password = test_user2_password
        self._test_user2_token = test_user2_token
        self.runtests = runtests
        self.disabled_roles = disabled_roles or set()
        # Préfixe de commande (lu une seule fois depuis .env)
        self.command_prefix = os.getenv('COMMAND_PREFIX', '!')
        
        # Composants
        self.client = MatrixClientWrapper(homeserver, user_id, access_token, password=password)
        self.room_manager = RoomManager(self.client, space_id, command_prefix=self.command_prefix)
        
        # Horaires depuis le .env (ou valeurs par défaut)
        from datetime import time as dtime
        self._night_hour = int(os.getenv('NIGHT_START_HOUR', '21'))
        self._day_hour = int(os.getenv('DAY_START_HOUR', '8'))
        self._vote_hour = int(os.getenv('VOTE_START_HOUR', '19'))
        self._max_days = int(os.getenv('GAME_MAX_DURATION_DAYS', '7'))
        self._game_start_day = int(os.getenv('GAME_START_DAY', '6'))   # 0=Lundi … 6=Dimanche
        self._game_start_hour = int(os.getenv('GAME_START_HOUR', '12'))
        
        # Le scheduler lit lui-même le .env pour ses horaires
        self.scheduler = GameScheduler()
        self.message_handler: Optional[MessageHandler] = None
        self.notification_manager: Optional[NotificationManager] = None
        self.message_distorter = MessageDistorter()
        
        # Configuration
        self.distort_little_girl_messages = os.getenv('LITTLE_GIRL_DISTORT_MESSAGES', 'true').lower() == 'true'
        self.mentaliste_advance_hours = float(os.getenv('MENTALISTE_ADVANCE_HOURS', '2'))
        self._cupidon_wins_with_couple = os.getenv('CUPIDON_WINS_WITH_COUPLE', 'true').lower() == 'true'
        
        # Jeu
        self.game_manager = GameManager()
        self.game_manager.cupidon_wins_with_couple = self._cupidon_wins_with_couple
        self.game_manager.disabled_roles = self.disabled_roles
        self.command_handler = CommandHandler(self.game_manager, command_prefix=self.command_prefix)
        self.leaderboard_manager = LeaderboardManager(self.game_manager.db)
        
        # Lier les callbacks Matrix au game manager
        # NOTE: Les méthodes _remove_wolf_from_room et _mute_player sont async,
        # mais le game_manager les appelle depuis du code sync.
        # On wrappe avec ensure_future pour que les coroutines s'exécutent réellement.
        self.game_manager.on_remove_wolf_from_room = lambda uid: asyncio.ensure_future(self._remove_wolf_from_room(uid))
        self.game_manager.on_mute_player = lambda uid: asyncio.ensure_future(self._mute_player(uid))
        
        # État
        self.registered_players: Dict[str, str] = {}  # matrix_id -> display_name
        self._accepting_registrations = True
        self._wolves_in_room: set = set()  # user_ids des loups dans le salon
        self._sorciere_notified = False  # Si la Sorcière a été notifiée du wolf target
        self._wolf_votes_locked = False  # True quand tous les loups ont voté (vote verrouillé)
        self._wolf_deadline_task: Optional[asyncio.Task] = None  # Timeout deadline vote loups
        self._mayor_succession_task: Optional[asyncio.Task] = None  # Timeout succession maire
        self._vote_reminder_task: Optional[asyncio.Task] = None  # Rappels de vote
        self._chasseur_timeout_tasks: Dict[str, asyncio.Task] = {}  # Timeout tir du chasseur (user_id → task)
        self._last_vote_snapshot: Dict[str, str] = {}  # Snapshot des votes pour détecter les changements
        self._game_events: List[str] = []  # Historique des événements pour le récap de fin
        self._kill_signal_task: Optional[asyncio.Task] = None  # Surveillance du signal kill admin
        self._jailed_user_id: Optional[str] = None  # Prisonnier actuel du geolier
        self._seating_message_event_id: Optional[str] = None  # Event ID du message d'assise
        self.running = False

    async def _update_seating_message(self):
        """Met a jour le message d'ordre d'assise en le modifiant."""
        if not self._seating_message_event_id:
            return
        if not self.room_manager.village_room:
            return

        seating_message = self._build_seating_message()
        if not seating_message:
            return

        await self.client.edit_message(
            self.room_manager.village_room,
            self._seating_message_event_id,
            seating_message,
            formatted=True,
        )

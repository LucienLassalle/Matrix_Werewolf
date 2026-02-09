"""Initialisation du package matrix_bot."""

from matrix_bot.bot_controller import WerewolfBot
from matrix_bot.matrix_client import MatrixClientWrapper
from matrix_bot.room_manager import RoomManager
from matrix_bot.scheduler import GameScheduler
from matrix_bot.message_handler import MessageHandler
from matrix_bot.notifications import NotificationManager

__all__ = [
    'WerewolfBot',
    'MatrixClientWrapper',
    'RoomManager',
    'GameScheduler',
    'MessageHandler',
    'NotificationManager'
]

"""
Backend Loup-Garou pour Matrix Bot

Ce package fournit toute la logique nécessaire pour gérer une partie de Loup-Garou.
"""

__version__ = "1.0.0"
__author__ = "Werewolf-Matrix Team"

from game.game_manager import GameManager
from commands.command_handler import CommandHandler
from models.enums import RoleType, Phase, Team, ActionType
from models.player import Player
from roles import RoleFactory

__all__ = [
    'GameManager',
    'CommandHandler',
    'RoleType',
    'Phase',
    'Team',
    'ActionType',
    'Player',
    'RoleFactory'
]

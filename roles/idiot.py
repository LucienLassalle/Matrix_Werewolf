"""Rôle Idiot."""

from models.role import Role
from models.enums import RoleType, Team
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Idiot(Role):
    """L'Idiot - Est gracié une fois mais perd son droit de vote."""
    
    def __init__(self):
        super().__init__(RoleType.IDIOT, Team.GENTIL)
    
    def get_description(self) -> str:
        return "L'Idiot - Si vous êtes élu pour être exécuté, vous êtes gracié une fois, mais vous perdez votre droit de vote."
    
    def on_voted_out(self, game: 'GameManager') -> bool:
        """Appelé quand l'idiot est voté. Retourne True s'il est sauvé."""
        if not self.player.has_been_pardoned:
            self.player.has_been_pardoned = True
            self.player.can_vote = False
            return True  # L'idiot est sauvé
        return False  # L'idiot meurt

    def get_state(self) -> dict:
        return {}

    def restore_state(self, data: dict, players: dict):
        pass

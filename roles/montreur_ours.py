"""Rôle Montreur d'Ours."""

from models.role import Role
from models.enums import RoleType, Team
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class MontreurOurs(Role):
    """Montreur d'Ours - Grogne si un loup est à côté de lui."""
    
    def __init__(self):
        super().__init__(RoleType.MONTREUR_OURS, Team.GENTIL)
    
    def get_description(self) -> str:
        return "Montreur d'Ours - Chaque matin, votre ours grogne si un loup est immédiatement à votre droite ou à votre gauche."
    
    def check_for_wolves(self, game: 'GameManager') -> bool:
        """Vérifie s'il y a des loups à côté."""
        if not self.player or not self.player.is_alive:
            return False
        
        neighbors = game.get_neighbors(self.player)
        for neighbor in neighbors:
            if neighbor.is_alive and neighbor.get_team() == Team.MECHANT:
                return True
        return False

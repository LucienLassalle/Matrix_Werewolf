"""Rôle Loup-Garou."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class LoupGarou(Role):
    """Loup-Garou - Vote chaque nuit pour tuer quelqu'un."""

    emoji = "🐺"
    
    def __init__(self):
        super().__init__(RoleType.LOUP_GAROU, Team.MECHANT)
        self.voted_for = None
    
    def get_description(self) -> str:
        return "Loup-Garou - Chaque nuit, vous votez avec les autres loups pour éliminer un villageois."
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return action_type == ActionType.VOTE and self.player and self.player.is_alive
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.VOTE:
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            self.voted_for = target
            return {"success": True, "message": f"Vous avez voté pour {target.pseudo}"}
        
        return {"success": False, "message": "Action non disponible"}
    
    def can_vote_with_wolves(self) -> bool:
        return True

    def on_night_start(self, game: 'GameManager'):
        """Réinitialise le vote au début de la nuit."""
        self.voted_for = None

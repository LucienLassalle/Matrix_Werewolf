"""Rôle Loup-Noir."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class LoupNoir(Role):
    """Loup-Noir - Peut convertir la victime des loups en loup au lieu de la tuer.
    
    Chaque nuit, le Loup Noir peut choisir de convertir la cible des loups
    au lieu de la dévorer. La cible rejoint alors la meute.
    Si le Garde protège la cible, la conversion est aussi bloquée.
    """
    
    def __init__(self):
        super().__init__(RoleType.LOUP_NOIR, Team.MECHANT)
        self.wants_to_convert = False
    
    def get_description(self) -> str:
        return ("Loup-Noir - Chaque nuit, vous pouvez choisir de convertir la victime des loups "
                "en loup-garou au lieu de la dévorer. Utilisez `/convertir` pour activer la conversion.")
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_vote_with_wolves(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        if not self.player or not self.player.is_alive:
            return False
        
        if action_type == ActionType.VOTE:
            return True
        if action_type == ActionType.CONVERT:
            return not self.wants_to_convert  # Peut toggle une fois par nuit
        
        return False
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.CONVERT:
            if self.wants_to_convert:
                return {"success": False, "message": "Vous avez déjà choisi de convertir cette nuit"}
            
            self.wants_to_convert = True
            return {
                "success": True,
                "message": ("🐺 Vous avez choisi de **convertir** la victime des loups cette nuit.\n"
                           "La cible deviendra un loup-garou au lieu de mourir.")
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def on_night_start(self, game: 'GameManager'):
        """Réinitialise le choix au début de la nuit."""
        self.wants_to_convert = False

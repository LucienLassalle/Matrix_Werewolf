"""Rôle Sorcière."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Sorciere(Role):
    """Sorcière - Dispose de 2 potions : une de vie et une de mort.
    
    Peut utiliser les DEUX potions la même nuit (règles Wolfy).
    Chaque potion n'est utilisable qu'une seule fois dans la partie.
    """
    
    def __init__(self):
        super().__init__(RoleType.SORCIERE, Team.GENTIL)
        self.has_life_potion = True
        self.has_death_potion = True
        self.has_healed_tonight = False
        self.has_poisoned_tonight = False
    
    def get_description(self) -> str:
        return ("Sorcière - Vous avez 2 potions : une pour sauver la victime des loups "
                "et une pour tuer quelqu'un. Chaque potion n'est utilisable qu'une seule fois "
                "dans la partie, mais vous pouvez utiliser les deux la même nuit.")
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        if not self.player or not self.player.is_alive:
            return False
        
        if action_type == ActionType.HEAL:
            return self.has_life_potion and not self.has_healed_tonight
        elif action_type == ActionType.POISON:
            return self.has_death_potion and not self.has_poisoned_tonight
        
        return False
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.HEAL:
            if not self.has_life_potion:
                return {"success": False, "message": "Vous n'avez plus de potion de vie"}
            
            if self.has_healed_tonight:
                return {"success": False, "message": "Vous avez déjà utilisé votre potion de vie cette nuit"}
            
            if not target:
                return {"success": False, "message": "Cible invalide"}
            
            self.has_life_potion = False
            self.has_healed_tonight = True
            return {
                "success": True,
                "message": f"Vous avez sauvé {target.pseudo}",
                "target": target
            }
        
        elif action_type == ActionType.POISON:
            if not self.has_death_potion:
                return {"success": False, "message": "Vous n'avez plus de potion de mort"}
            
            if self.has_poisoned_tonight:
                return {"success": False, "message": "Vous avez déjà utilisé votre potion de mort cette nuit"}
            
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            if target == self.player:
                return {"success": False, "message": "Vous ne pouvez pas vous empoisonner vous-même"}
            
            self.has_death_potion = False
            self.has_poisoned_tonight = True
            # NE PAS tuer ici - l'action_manager gère la mort à la résolution
            return {
                "success": True,
                "message": f"Vous avez empoisonné {target.pseudo}",
                "target": target
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def on_night_start(self, game: 'GameManager'):
        """Réinitialise l'état au début de la nuit."""
        self.has_healed_tonight = False
        self.has_poisoned_tonight = False

    def get_state(self) -> dict:
        return {
            'has_life_potion': self.has_life_potion,
            'has_death_potion': self.has_death_potion,
        }

    def restore_state(self, data: dict, players: dict):
        self.has_life_potion = data.get('has_life_potion', True)
        self.has_death_potion = data.get('has_death_potion', True)

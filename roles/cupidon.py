"""Rôle Cupidon."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager
    from models.player import Player


class Cupidon(Role):
    """Cupidon - Marie deux personnes durant la première nuit."""
    
    def __init__(self):
        super().__init__(RoleType.CUPIDON, Team.GENTIL)
        self.has_used_power = False
    
    def get_description(self) -> str:
        return ("Cupidon - Durant la première nuit, vous pouvez marier deux personnes. "
                "Si l'une meurt, l'autre meurt aussi.")
    
    def can_act_at_night(self) -> bool:
        return not self.has_used_power
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.MARRY and 
                self.player and 
                self.player.is_alive and 
                not self.has_used_power)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.MARRY:
            if self.has_used_power:
                return {"success": False, "message": "Vous avez déjà utilisé votre pouvoir"}
            
            target1 = kwargs.get('target1')
            target2 = kwargs.get('target2')
            
            if not target1 or not target2:
                return {"success": False, "message": "Vous devez choisir deux personnes"}
            
            if target1 == target2:
                return {"success": False, "message": "Vous ne pouvez pas marier une personne avec elle-même"}
            
            if not target1.is_alive or not target2.is_alive:
                return {"success": False, "message": "Les deux cibles doivent être vivantes"}
            
            if target1.lover or target2.lover:
                return {"success": False, "message": "Une des personnes est déjà en couple"}
            
            # Créer le lien amoureux
            target1.lover = target2
            target2.lover = target1
            
            self.has_used_power = True
            
            # Vérifier si Cupidon peut gagner avec le couple
            couple_team = self._get_couple_win_condition(target1, target2)
            
            return {
                "success": True,
                "message": f"Vous avez marié {target1.pseudo} et {target2.pseudo}",
                "couple": [target1, target2],
                "couple_team": couple_team
            }
        
        return {"success": False, "message": "Action non disponible"}

    def get_state(self) -> dict:
        return {'has_used_power': self.has_used_power}

    def restore_state(self, data: dict, players: dict):
        self.has_used_power = data.get('has_used_power', False)
    
    def _get_couple_win_condition(self, player1: 'Player', player2: 'Player') -> str:
        """Détermine la condition de victoire du couple."""
        team1 = player1.get_team()
        team2 = player2.get_team()
        
        if team1 != team2:
            return "COUPLE"  # Le couple gagne seul si équipes différentes
        else:
            return team1.value  # Le couple gagne avec leur équipe commune

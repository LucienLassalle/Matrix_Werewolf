"""Rôle Voyante d'Aura."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class VoyanteAura(Role):
    """Voyante d'Aura - Voit si un joueur est Gentil, Neutre ou Méchant."""

    emoji = "🌈"
    is_info_role = True
    
    def __init__(self):
        super().__init__(RoleType.VOYANTE_AURA, Team.GENTIL)
        self.has_used_power_tonight = False
    
    def get_description(self) -> str:
        return "Voyante d'Aura - Chaque nuit, vous pouvez voir si un joueur est Gentil, Neutre ou Méchant."
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.SEE_AURA and 
                self.player and 
                self.player.is_alive and 
                not self.has_used_power_tonight)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.SEE_AURA:
            if not target or not target.is_alive or target == self.player:
                return {"success": False, "message": "Cible invalide"}
            
            self.has_used_power_tonight = True
            team = target.get_team()
            aura_names = {
                Team.GENTIL: "Gentil 🏘️",
                Team.MECHANT: "Méchant 🐺",
                Team.NEUTRE: "Neutre ❓",
            }
            aura = aura_names.get(team, team.value)
            return {
                "success": True,
                "message": f"{target.pseudo} est **{aura}**",
                "aura": aura
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def on_night_start(self, game: 'GameManager'):
        self.has_used_power_tonight = False

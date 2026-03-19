"""Rôle Dictateur."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Dictateur(Role):
    """Dictateur - Peut prendre le pouvoir et forcer un vote."""

    emoji = "⚡"
    
    def __init__(self):
        super().__init__(RoleType.DICTATEUR, Team.GENTIL)
        self.has_used_power = False
        self.is_armed = False
    
    def get_description(self) -> str:
        return ("Dictateur - Vous préparez votre coup d'etat la nuit, puis le jour "
            "vous eliminez quelqu'un. Si vous tuez un loup, vous devenez maire. "
            "Sinon, vous mourrez.")
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.DICTATOR_KILL and 
                self.player and 
                self.player.is_alive and 
                not self.has_used_power)

    def get_state(self) -> dict:
        return {
            'has_used_power': self.has_used_power,
            'is_armed': self.is_armed
        }

    def restore_state(self, data: dict, players: dict):
        self.has_used_power = data.get('has_used_power', False)
        self.is_armed = data.get('is_armed', False)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.DICTATOR_KILL:
            if self.has_used_power:
                return {"success": False, "message": "Vous avez déjà utilisé votre pouvoir"}

            from models.enums import GamePhase
            if game.phase == GamePhase.NIGHT:
                if target is not None:
                    return {"success": False, "message": "Utilisez !dictateur sans cible la nuit"}
                if self.is_armed:
                    return {"success": False, "message": "Votre pouvoir est déjà armé"}
                self.is_armed = True
                return {
                    "success": True,
                    "message": "Pouvoir armé. Vous pourrez éliminer une cible demain.",
                    "armed": True
                }
            
            if game.phase not in (GamePhase.DAY, GamePhase.VOTE):
                return {"success": False, "message": "Le Dictateur ne peut agir que durant le jour"}

            if not self.is_armed:
                return {
                    "success": False,
                    "message": "Vous devez d'abord utiliser !dictateur la nuit"
                }

            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            if target == self.player:
                return {"success": False, "message": "Vous ne pouvez pas vous cibler vous-même"}

            self.has_used_power = True
            self.is_armed = False
            
            # Le coup d'état annule le vote en cours
            if game.phase == GamePhase.VOTE:
                game.vote_manager.clear_votes()
                game.phase = GamePhase.DAY
            
            if target.get_team() == Team.MECHANT:
                # Le dictateur tue un loup, il devient maire
                dead = game.kill_player(target, killed_during_day=True)
                
                # Vérifier que le Dictateur est toujours vivant
                # (il peut mourir en cascade s'il était amoureux de la cible)
                if self.player.is_alive:
                    # Retirer le titre de maire à l'ancien maire (s'il existe)
                    for p in game.players.values():
                        if p.is_mayor and p != self.player:
                            p.is_mayor = False
                    # Annuler toute succession en cours (la cible était peut-être maire)
                    game._pending_mayor_succession = None
                    self.player.is_mayor = True
                    return {
                        "success": True,
                        "message": f"Vous avez éliminé {target.pseudo}, un loup ! Vous êtes maintenant maire.",
                        "became_mayor": True,
                        "target": target,
                        "deaths": dead
                    }
                else:
                    # Le Dictateur est mort en cascade (amoureux)
                    return {
                        "success": True,
                        "message": f"Vous avez éliminé {target.pseudo}, un loup ! Mais vous êtes mort.e de chagrin...",
                        "became_mayor": False,
                        "target": target,
                        "deaths": dead
                    }
            else:
                # Le dictateur tue un innocent, il meurt aussi
                dead_target = game.kill_player(target, killed_during_day=True)
                dead_self = []
                if self.player.is_alive:  # Pas déjà mort par cascade amoureux
                    dead_self = game.kill_player(self.player, killed_during_day=True)
                return {
                    "success": True,
                    "message": f"Vous avez éliminé {target.pseudo}, qui n'était pas un loup. Vous mourrez.",
                    "became_mayor": False,
                    "target": target,
                    "deaths": dead_target + dead_self
                }
        
        return {"success": False, "message": "Action non disponible"}

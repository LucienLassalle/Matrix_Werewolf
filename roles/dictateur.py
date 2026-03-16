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
    
    def get_description(self) -> str:
        return ("Dictateur - Vous pouvez prendre le pouvoir et décider d'éliminer quelqu'un. "
                "Si vous tuez un loup, vous devenez maire. Sinon, vous mourrez.")
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.DICTATOR_KILL and 
                self.player and 
                self.player.is_alive and 
                not self.has_used_power)

    def get_state(self) -> dict:
        return {'has_used_power': self.has_used_power}

    def restore_state(self, data: dict, players: dict):
        self.has_used_power = data.get('has_used_power', False)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.DICTATOR_KILL:
            if self.has_used_power:
                return {"success": False, "message": "Vous avez déjà utilisé votre pouvoir"}
            
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            if target == self.player:
                return {"success": False, "message": "Vous ne pouvez pas vous cibler vous-même"}
            
            # Le Dictateur ne peut agir que durant le jour
            from models.enums import GamePhase
            if game.phase not in (GamePhase.DAY, GamePhase.VOTE):
                return {"success": False, "message": "Le Dictateur ne peut agir que durant le jour"}
            
            self.has_used_power = True
            
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

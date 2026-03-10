"""Rôle Voleur."""

import os

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Voleur(Role):
    """Voleur - Peut voler un rôle durant la première nuit.
    
    Options mutuellement exclusives :
    - Voir 2 cartes non-utilisées puis en choisir une
    - Échanger son rôle avec celui d'un autre joueur
    - Ne rien faire (reste Voleur, équivalent Villageois)
    
    Si le Voleur tire 2 cartes mais ne choisit pas, la première
    est automatiquement assignée à la fin de la nuit.
    """
    
    def __init__(self):
        super().__init__(RoleType.VOLEUR, Team.GENTIL)
        self.has_used_power = False
        self.drawn_roles: Optional[List[Role]] = None
    
    def get_description(self) -> str:
        p = os.getenv('COMMAND_PREFIX', '!')
        return ("Voleur - La première nuit, vous pouvez soit tirer 2 cartes non-utilisées et en choisir une, "
        "soit échanger votre rôle avec celui d'un autre joueur, soit ne rien faire et rester Voleur (équivalent Villageois).\n\n")
    
    def can_act_at_night(self) -> bool:
        return not self.has_used_power
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        if not self.player or not self.player.is_alive or self.has_used_power:
            return False
        
        if action_type == ActionType.DRAW_ROLES:
            return self.drawn_roles is None  # Pas encore tiré
        
        if action_type == ActionType.STEAL_ROLE:
            return True  # Soit choisir parmi les tirées, soit échanger
        
        return False
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if self.has_used_power:
            return {"success": False, "message": "Vous avez déjà utilisé votre pouvoir"}
        
        if action_type == ActionType.DRAW_ROLES:
            # Tirer 2 cartes non-utilisées
            if self.drawn_roles is not None:
                return {"success": False, "message": "Vous avez déjà tiré vos cartes"}
            
            extra_roles = getattr(game, 'extra_roles', [])
            if len(extra_roles) < 2:
                return {"success": False, "message": "Pas assez de cartes disponibles"}
            
            self.drawn_roles = extra_roles[:2]
            p = os.getenv('COMMAND_PREFIX', '!')
            return {
                "success": True,
                "message": (f"Vous avez tiré : **{self.drawn_roles[0].name}** et "
                           f"**{self.drawn_roles[1].name}**.\n"
                           f"Choisissez avec {p}voleur-choisir 1 ou {p}voleur-choisir 2"),
                "roles": [r.role_type.value for r in self.drawn_roles]
            }
        
        elif action_type == ActionType.STEAL_ROLE:
            if self.drawn_roles:
                # Choisir parmi les cartes tirées
                choice = kwargs.get('choice', 0)
                if choice < 0 or choice >= len(self.drawn_roles):
                    return {"success": False, "message": "Choix invalide (1 ou 2)"}
                
                chosen_role = self.drawn_roles[choice]
                self.player.original_role_name = "Voleur"
                chosen_role.assign_to_player(self.player)
                self.has_used_power = True
                
                # Appeler on_game_start pour initialiser le nouveau rôle
                # (ex: Mercenaire a besoin d'une cible)
                chosen_role.on_game_start(game)
                
                return {
                    "success": True,
                    "message": f"Vous êtes maintenant **{chosen_role.name}** !",
                    "new_role": chosen_role
                }
            
            elif target:
                # Échanger avec un autre joueur
                if self.drawn_roles is not None:
                    return {"success": False,
                            "message": "Vous avez déjà tiré des cartes, choisissez parmi elles"}
                
                if not target.is_alive or target == self.player:
                    return {"success": False, "message": "Cible invalide"}
                
                if not target.role:
                    return {"success": False, "message": "La cible n'a pas de rôle"}
                
                # Sauvegarder les rôles avant l'échange
                voleur_role = self  # Le rôle Voleur actuel
                target_role = target.role
                
                # Marquer les rôles d'origine avant l'échange
                self.player.original_role_name = "Voleur"
                target.original_role_name = target_role.name
                
                # Le Voleur reçoit le rôle de la cible
                target_role.assign_to_player(self.player)
                
                # La cible reçoit le rôle Voleur (équivalent Villageois, pouvoir épuisé)
                voleur_role.has_used_power = True
                voleur_role.assign_to_player(target)
                
                # Initialiser le nouveau rôle du Voleur
                # (ex: Mercenaire a besoin d'une cible)
                target_role.on_game_start(game)
                
                return {
                    "success": True,
                    "message": (f"Vous avez échangé votre rôle avec {target.pseudo}. "
                               f"Vous êtes maintenant **{target_role.name}** !"),
                    "new_role": target_role,
                    "swapped_target": target  # Pour notification de la cible
                }
            
            else:
                return {"success": False, "message": "Cible ou choix requis"}
        
        return {"success": False, "message": "Action non disponible"}

    def get_state(self) -> dict:
        return {'has_used_power': self.has_used_power}

    def restore_state(self, data: dict, players: dict):
        self.has_used_power = data.get('has_used_power', False)

"""Gestionnaire d'actions."""

from typing import Dict, List, Optional
from models.player import Player
from models.enums import ActionType, Team, RoleType


class ActionManager:
    """Gère les actions des joueurs durant la nuit."""
    
    def __init__(self):
        self.pending_actions: List[dict] = []
        self.night_deaths: List[Player] = []
        self.saved_players: List[Player] = []
        
    def register_action(self, player: Player, action_type: ActionType, target=None, **kwargs) -> dict:
        """Enregistre une action à effectuer.
        
        Note : Ne re-vérifie PAS can_perform_action car perform_action()
        a déjà validé et consommé la ressource (ex: potion de la Sorcière).
        """
        if not player.role:
            return {"success": False, "message": "Vous n'avez pas de rôle"}
        
        action = {
            "player": player,
            "action_type": action_type,
            "target": target,
            "kwargs": kwargs
        }
        
        self.pending_actions.append(action)
        return {"success": True, "message": "Action enregistrée"}
    
    def execute_night_actions(self, game) -> dict:
        """Exécute toutes les actions de la nuit dans l'ordre approprié.
        
        Ordre de résolution :
        1. Protection du Garde
        2. Vote des loups (avec conversion Loup Noir si active)
        3. Sorcière (heal et/ou poison)
        4. Loup Blanc (kill)
        5. Actions de vision (déjà résolues, juste log)
        
        Returns:
            dict avec wolf_target, deaths, saved, converted, actions
        """
        results = {
            "wolf_target": None,
            "deaths": [],
            "saved": [],
            "converted": None,
            "actions": []
        }
        
        # 1. Protection du garde
        for action in self.pending_actions:
            if action["action_type"] == ActionType.PROTECT:
                target = action["target"]
                if target and target.is_alive:
                    target.is_protected = True
                    results["actions"].append({
                        "type": "protect",
                        "success": True,
                        "target": target
                    })
        
        # 2. Vote des loups (via le vote manager)
        wolf_target = game.vote_manager.get_most_voted(is_wolf_vote=True)
        if wolf_target:
            results["wolf_target"] = wolf_target
            
            # Vérifier si le Loup Noir veut convertir
            loup_noir_converts = False
            for p in game.players.values():
                if (p.is_alive and p.role and 
                    p.role.role_type == RoleType.LOUP_NOIR and
                    hasattr(p.role, 'wants_to_convert') and 
                    p.role.wants_to_convert):
                    loup_noir_converts = True
                    break
            
            if wolf_target.is_protected:
                # Garde protège contre meurtre ET conversion
                self.saved_players.append(wolf_target)
            elif loup_noir_converts and wolf_target.get_team() != Team.MECHANT:
                # Convertir au lieu de tuer
                from roles.loup_garou import LoupGarou
                new_role = LoupGarou()
                new_role.assign_to_player(wolf_target)
                results["converted"] = wolf_target
                results["actions"].append({
                    "type": "convert",
                    "success": True,
                    "target": wolf_target
                })
            elif loup_noir_converts and wolf_target.get_team() == Team.MECHANT:
                # Cible déjà méchante, la conversion échoue → tuer normalement
                self.night_deaths.append(wolf_target)
                results["actions"].append({
                    "type": "convert",
                    "success": False,
                    "target": wolf_target
                })
            else:
                # Meurtre classique
                self.night_deaths.append(wolf_target)
        
        # 3. Actions de la sorcière (heal et/ou poison, les deux possibles la même nuit)
        for action in self.pending_actions:
            if action["action_type"] == ActionType.HEAL:
                target = action["target"]
                if target and target in self.night_deaths:
                    self.night_deaths.remove(target)
                    self.saved_players.append(target)
                    results["saved"].append(target)
                # Note : si la cible n'est pas dans night_deaths
                # (ex: protégée par Garde ou convertie par Loup Noir),
                # la potion est quand même consommée (dans perform_action)
                results["actions"].append({
                    "type": "heal",
                    "success": True,
                    "target": target
                })
            
            elif action["action_type"] == ActionType.POISON:
                target = action["target"]
                if target and target.is_alive:
                    self.night_deaths.append(target)
                results["actions"].append({
                    "type": "poison",
                    "success": True,
                    "target": target
                })
        
        # 4. Actions du loup blanc (kill) — le Garde protège aussi
        for action in self.pending_actions:
            if action["action_type"] == ActionType.KILL:
                target = action["target"]
                if target and target.is_alive:
                    if target.is_protected:
                        results["actions"].append({
                            "type": "kill",
                            "success": False,
                            "target": target,
                            "reason": "protected"
                        })
                    else:
                        self.night_deaths.append(target)
                        results["actions"].append({
                            "type": "kill",
                            "success": True,
                            "target": target
                        })
        
        # 5. Actions de vision (déjà exécutées lors de l'enregistrement)
        for action in self.pending_actions:
            if action["action_type"] in [ActionType.SEE_ROLE, ActionType.SEE_AURA]:
                results["actions"].append({
                    "type": action["action_type"].value,
                    "success": True,
                    "target": action["target"]
                })
        
        # Appliquer les morts (dé-dupliquer, inclure les amoureux)
        seen = set()
        for dead_player in self.night_deaths:
            if dead_player.is_alive and dead_player.user_id not in seen:
                seen.add(dead_player.user_id)
                # Sauvegarder l'amoureux avant le kill (Player.kill cascade)
                lover = dead_player.lover if dead_player.lover and dead_player.lover.is_alive else None
                dead_player.kill()
                results["deaths"].append(dead_player)
                # Si l'amoureux est mort par cascade, l'ajouter aussi
                if lover and not lover.is_alive and lover.user_id not in seen:
                    seen.add(lover.user_id)
                    results["deaths"].append(lover)
        
        self.pending_actions.clear()
        return results
    
    def reset(self):
        """Réinitialise le gestionnaire d'actions."""
        self.pending_actions.clear()
        self.night_deaths.clear()
        self.saved_players.clear()
    
    def cancel_player_actions(self, user_id: str):
        """Annule toutes les actions enregistrées d'un joueur."""
        self.pending_actions = [
            action for action in self.pending_actions 
            if action["player"].user_id != user_id
        ]
        
        # Retirer des morts planifiées
        self.night_deaths = [
            player for player in self.night_deaths 
            if player.user_id != user_id
        ]

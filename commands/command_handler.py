"""Gestionnaire de commandes pour le jeu."""

from typing import Dict, Callable, Optional
from models.enums import ActionType
from game.game_manager import GameManager
from models.player import Player


class CommandHandler:
    """Gère l'exécution des commandes du jeu."""
    
    def __init__(self, game: GameManager):
        self.game = game
        self.game_manager = game  # Alias pour compatibilité
        self.commands: Dict[str, Callable] = {
            "vote": self.handle_vote,
            "tuer": self.handle_kill,
            "cupidon": self.handle_cupidon,
            "sorciere-sauve": self.handle_witch_heal,
            "sorciere-tue": self.handle_witch_poison,
            "voleur-echange": self.handle_thief_swap,
            "voleur-tirer": self.handle_thief_draw,
            "voyante": self.handle_seer,
            "lg": self.handle_become_werewolf,
            "enfant": self.handle_choose_mentor,
            "medium": self.handle_medium,
            "garde": self.handle_guard,
            "corbeau": self.handle_curse,
            "curse": self.handle_curse,
            "voleur-choisir": self.handle_thief_choose,
            "convertir": self.handle_convert,
            "dictateur": self.handle_dictator,
            "maire": self.handle_maire,
        }
    
    def handle_command(self, user_id: str, command: str, target=None) -> dict:
        """Gère une commande avec une cible déjà résolue (interface bot)."""
        player = self.game.get_player_by_user_id(user_id)
        if not player:
            return {"success": False, "message": "Joueur non trouvé"}
        
        if not player.is_alive:
            is_chasseur_tuer = (command == "tuer" and player.role
                                and player.role.role_type.value == "CHASSEUR")
            is_maire_succession = (command == "maire"
                                   and self.game._pending_mayor_succession == player)
            if not is_chasseur_tuer and not is_maire_succession:
                return {"success": False, "message": "Vous êtes mort"}
        
        handler = self.commands.get(command)
        if not handler:
            return {"success": False, "message": f"Commande inconnue : /{command}"}
        
        args = [target] if target else []
        return handler(player, args)
    
    def execute_command(self, user_id: str, command: str, args: list) -> dict:
        """Exécute une commande."""
        player = self.game.get_player_by_user_id(user_id)
        if not player:
            return {"success": False, "message": "Joueur non trouvé"}
        
        if not player.is_alive:
            # Exceptions pour les joueurs morts
            is_chasseur_tuer = (command == "tuer" and player.role
                                and player.role.role_type.value == "CHASSEUR")
            is_maire_succession = (command == "maire"
                                   and self.game._pending_mayor_succession == player)
            if not is_chasseur_tuer and not is_maire_succession:
                return {"success": False, "message": "Vous êtes mort"}
        
        handler = self.commands.get(command)
        if not handler:
            return {"success": False, "message": f"Commande inconnue : /{command}"}
        
        return handler(player, args)
    
    def handle_vote(self, player: Player, args: list) -> dict:
        """Gère /vote {pseudo}."""
        if not args:
            return {"success": False, "message": "Usage : /vote {pseudo}"}
        
        target_pseudo = args[0]
        target = self.game.get_player_by_pseudo(target_pseudo)
        
        if not target:
            return {"success": False, "message": f"Joueur {target_pseudo} non trouvé"}
        
        # Vérifier si c'est un vote de loup (pendant la nuit) ou un vote de village (pendant le vote)
        if self.game.phase.value == "NIGHT":
            # Vote de loup
            if not player.role or not player.role.can_vote_with_wolves():
                return {"success": False, "message": "Vous ne pouvez pas voter avec les loups"}
            
            return self.game.vote_manager.cast_vote(player, target, is_wolf_vote=True)
        
        elif self.game.phase.value == "VOTE":
            # Vote du village
            return self.game.vote_manager.cast_vote(player, target, is_wolf_vote=False)
        
        else:
            return {"success": False, "message": "Ce n'est pas le moment de voter"}
    
    def handle_kill(self, player: Player, args: list) -> dict:
        """Gère /tuer {pseudo} - Pour le Chasseur, Dictateur, Loup Blanc."""
        if not args:
            return {"success": False, "message": "Usage : /tuer {pseudo}"}
        
        target_pseudo = args[0]
        target = self.game.get_player_by_pseudo(target_pseudo)
        
        if not target:
            return {"success": False, "message": f"Joueur {target_pseudo} non trouvé"}
        
        if not player.role:
            return {"success": False, "message": "Vous n'avez pas de rôle"}
        
        # Déterminer le type d'action en fonction du rôle
        role_type = player.role.role_type.value
        
        if role_type == "CHASSEUR":
            return player.role.perform_action(self.game, ActionType.KILL, target)
        
        elif role_type == "DICTATEUR":
            return player.role.perform_action(self.game, ActionType.DICTATOR_KILL, target)
        
        elif role_type == "LOUP_BLANC":
            result = player.role.perform_action(self.game, ActionType.KILL, target)
            if result["success"]:
                self.game.action_manager.register_action(player, ActionType.KILL, target)
            return result
        
        else:
            return {"success": False, "message": "Vous ne pouvez pas utiliser cette commande"}
    
    def handle_cupidon(self, player: Player, args: list) -> dict:
        """Gère /cupidon {pseudo1} {pseudo2}."""
        if len(args) < 2:
            return {"success": False, "message": "Usage : /cupidon {pseudo1} {pseudo2}"}
        
        target1 = self.game.get_player_by_pseudo(args[0])
        target2 = self.game.get_player_by_pseudo(args[1])
        
        if not target1 or not target2:
            return {"success": False, "message": "Un des joueurs n'a pas été trouvé"}
        
        if not player.role or player.role.role_type.value != "CUPIDON":
            return {"success": False, "message": "Vous n'êtes pas Cupidon"}
        
        return player.role.perform_action(self.game, ActionType.MARRY, None, target1=target1, target2=target2)
    
    def handle_witch_heal(self, player: Player, args: list) -> dict:
        """Gère /sorciere-sauve {pseudo}.
        
        Règle originale : la Sorcière ne peut sauver QUE la victime des loups.
        """
        if not args:
            return {"success": False, "message": "Usage : /sorciere-sauve {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role or player.role.role_type.value != "SORCIERE":
            return {"success": False, "message": "Vous n'êtes pas la Sorcière"}
        
        # Vérifier que la cible est bien la victime des loups
        wolf_target = self.game.vote_manager.get_most_voted(is_wolf_vote=True)
        if not wolf_target:
            return {"success": False, "message": "Les loups n'ont pas encore voté, vous ne pouvez pas utiliser votre potion de vie"}
        if target != wolf_target:
            return {"success": False, "message": f"Vous ne pouvez sauver que la victime des loups ({wolf_target.pseudo})"}
        
        result = player.role.perform_action(self.game, ActionType.HEAL, target)
        if result["success"]:
            self.game.action_manager.register_action(player, ActionType.HEAL, target)
        return result
    
    def handle_witch_poison(self, player: Player, args: list) -> dict:
        """Gère /sorciere-tue {pseudo}."""
        if not args:
            return {"success": False, "message": "Usage : /sorciere-tue {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role or player.role.role_type.value != "SORCIERE":
            return {"success": False, "message": "Vous n'êtes pas la Sorcière"}
        
        result = player.role.perform_action(self.game, ActionType.POISON, target)
        if result["success"]:
            self.game.action_manager.register_action(player, ActionType.POISON, target)
        return result
    
    def handle_thief_swap(self, player: Player, args: list) -> dict:
        """Gère /voleur-echange {pseudo}."""
        if not args:
            return {"success": False, "message": "Usage : /voleur-echange {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role or player.role.role_type.value != "VOLEUR":
            return {"success": False, "message": "Vous n'êtes pas le Voleur"}
        
        return player.role.perform_action(self.game, ActionType.STEAL_ROLE, target)
    
    def handle_thief_draw(self, player: Player, args: list) -> dict:
        """Gère /voleur-tirer."""
        if not player.role or player.role.role_type.value != "VOLEUR":
            return {"success": False, "message": "Vous n'êtes pas le Voleur"}
        
        return player.role.perform_action(self.game, ActionType.DRAW_ROLES)
    
    def handle_seer(self, player: Player, args: list) -> dict:
        """Gère /voyante {pseudo} - Pour Voyante et Voyante d'Aura."""
        if not args:
            return {"success": False, "message": "Usage : /voyante {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role:
            return {"success": False, "message": "Vous n'avez pas de rôle"}
        
        role_type = player.role.role_type.value
        
        if role_type == "VOYANTE":
            result = player.role.perform_action(self.game, ActionType.SEE_ROLE, target)
            if result["success"]:
                self.game.action_manager.register_action(player, ActionType.SEE_ROLE, target)
            return result
        
        elif role_type == "VOYANTE_AURA":
            result = player.role.perform_action(self.game, ActionType.SEE_AURA, target)
            if result["success"]:
                self.game.action_manager.register_action(player, ActionType.SEE_AURA, target)
            return result
        
        elif role_type == "LOUP_VOYANT":
            result = player.role.perform_action(self.game, ActionType.SEE_ROLE, target)
            if result["success"]:
                self.game.action_manager.register_action(player, ActionType.SEE_ROLE, target)
            return result
        
        else:
            return {"success": False, "message": "Vous ne pouvez pas utiliser cette commande"}
    
    def handle_become_werewolf(self, player: Player, args: list) -> dict:
        """Gère /lg - Pour le Loup Voyant."""
        if not player.role or player.role.role_type.value != "LOUP_VOYANT":
            return {"success": False, "message": "Vous n'êtes pas le Loup Voyant"}
        
        return player.role.perform_action(self.game, ActionType.BECOME_WEREWOLF)
    
    def handle_choose_mentor(self, player: Player, args: list) -> dict:
        """Gère /enfant {pseudo}."""
        if not args:
            return {"success": False, "message": "Usage : /enfant {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role or player.role.role_type.value != "ENFANT_SAUVAGE":
            return {"success": False, "message": "Vous n'êtes pas l'Enfant Sauvage"}
        
        return player.role.perform_action(self.game, ActionType.CHOOSE_MENTOR, target)
    
    def handle_medium(self, player: Player, args: list) -> dict:
        """Gère /medium {pseudo}."""
        if not args:
            return {"success": False, "message": "Usage : /medium {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role or player.role.role_type.value != "MEDIUM":
            return {"success": False, "message": "Vous n'êtes pas le Médium"}
        
        result = player.role.perform_action(self.game, ActionType.SPEAK_WITH_DEAD, target)
        if result["success"]:
            self.game.action_manager.register_action(player, ActionType.SPEAK_WITH_DEAD, target)
        return result
    
    def handle_guard(self, player: Player, args: list) -> dict:
        """Gère /garde {pseudo}."""
        if not args:
            return {"success": False, "message": "Usage : /garde {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role or player.role.role_type.value != "GARDE":
            return {"success": False, "message": "Vous n'êtes pas le Garde"}
        
        result = player.role.perform_action(self.game, ActionType.PROTECT, target)
        if result["success"]:
            self.game.action_manager.register_action(player, ActionType.PROTECT, target)
        return result
    
    def handle_curse(self, player: Player, args: list) -> dict:
        """Gère /corbeau {pseudo} ou /curse {pseudo}."""
        if not args:
            return {"success": False, "message": "Usage : /corbeau {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role or player.role.role_type.value != "CORBEAU":
            return {"success": False, "message": "Vous n'êtes pas le Corbeau"}
        
        result = player.role.perform_action(self.game, ActionType.ADD_VOTES, target)
        if result["success"]:
            self.game.action_manager.register_action(player, ActionType.ADD_VOTES, target)
        return result
    
    def handle_thief_choose(self, player: Player, args: list) -> dict:
        """Gère /voleur-choisir {1|2}."""
        if not player.role or player.role.role_type.value != "VOLEUR":
            return {"success": False, "message": "Vous n'êtes pas le Voleur"}
        
        if not args:
            return {"success": False, "message": "Usage : /voleur-choisir {1|2}"}
        
        try:
            choice = int(args[0]) - 1  # Convertir 1-based à 0-based
        except (ValueError, IndexError):
            return {"success": False, "message": "Choix invalide. Utilisez 1 ou 2."}
        
        return player.role.perform_action(self.game, ActionType.STEAL_ROLE, choice=choice)
    
    def handle_convert(self, player: Player, args: list) -> dict:
        """Gère /convertir - Pour le Loup Noir.
        
        Active la conversion : la cible des loups sera convertie
        en loup-garou au lieu d'être tuée.
        """
        if not player.role or player.role.role_type.value != "LOUP_NOIR":
            return {"success": False, "message": "Vous n'êtes pas le Loup Noir"}
        
        return player.role.perform_action(self.game, ActionType.CONVERT)
    
    def handle_dictator(self, player: Player, args: list) -> dict:
        """Gère /dictateur {pseudo} - Pour le Dictateur.
        
        Élimine un joueur sans vote. Si c'est un loup, le Dictateur
        devient maire. Sinon, le Dictateur meurt aussi.
        """
        if not args:
            return {"success": False, "message": "Usage : /dictateur {pseudo}"}
        
        target = self.game.get_player_by_pseudo(args[0])
        
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not player.role or player.role.role_type.value != "DICTATEUR":
            return {"success": False, "message": "Vous n'êtes pas le Dictateur"}
        
        return player.role.perform_action(self.game, ActionType.DICTATOR_KILL, target)
    
    def handle_maire(self, player: Player, args: list) -> dict:
        """Gère /maire {pseudo} - Désigner un successeur en tant que maire mort."""
        if not args:
            return {"success": False, "message": "Usage : /maire {pseudo}"}
        
        if self.game._pending_mayor_succession != player:
            return {"success": False, "message": "Vous n'êtes pas autorisé à désigner un maire"}
        
        target = self.game.get_player_by_pseudo(args[0])
        if not target:
            return {"success": False, "message": f"Joueur {args[0]} non trouvé"}
        
        if not target.is_alive:
            return {"success": False, "message": "Vous devez désigner un joueur vivant"}
        
        return self.game.designate_mayor(target)

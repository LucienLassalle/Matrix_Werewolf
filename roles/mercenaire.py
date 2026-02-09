"""Rôle Mercenaire."""

from models.role import Role
from models.enums import RoleType, Team
from typing import TYPE_CHECKING
import random

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Mercenaire(Role):
    """Mercenaire - Doit faire éliminer une cible désignée dans les 2 premiers jours."""
    
    def __init__(self):
        super().__init__(RoleType.MERCENAIRE, Team.NEUTRE)
        self.target_assigned = False
        self.has_won = False
        self.days_elapsed = 0
        self.deadline = 2  # Nombre de jours pour accomplir la mission
    
    def get_description(self) -> str:
        return ("Mercenaire - Le premier jour, vous recevez le nom d'une personne "
                "que vous devez faire éliminer par le vote dans les 2 premiers jours. "
                "Si vous réussissez, vous rejoignez le camp du village. "
                "Si vous échouez, vous mourrez.")
    
    def on_game_start(self, game: 'GameManager'):
        """Assigne une cible aléatoire au début de la partie."""
        if not self.target_assigned:
            living_players = game.get_living_players()
            possible_targets = [p for p in living_players if p != self.player]
            
            if possible_targets:
                self.player.target = random.choice(possible_targets)
                self.target_assigned = True
    
    def on_day_start(self, game: 'GameManager'):
        """Compte les jours et vérifie la deadline."""
        self.days_elapsed += 1
        
        # Vérifier la deadline (après le 2ème jour)
        if self.days_elapsed > self.deadline and not self.has_won:
            if self.player and self.player.is_alive:
                game.log(f"{self.player.pseudo} (Mercenaire) n'a pas accompli sa mission à temps !")
                # Mort différée : évite les cascades pendant la boucle on_day_start
                if hasattr(game, '_pending_kills'):
                    game._pending_kills.append(self.player)
                else:
                    game.kill_player(self.player, killed_during_day=False)
    
    def on_player_death(self, game: 'GameManager', dead_player, **kwargs):
        """Vérifie si la cible du mercenaire a été éliminée par le vote du village.
        
        Seule une élimination par vote du village compte (pas le Dictateur,
        pas le Chasseur). Le flag 'voted_out' est posé par end_vote_phase().
        """
        voted_out = kwargs.get('voted_out', False)
        if (voted_out and 
            self.player and 
            self.player.is_alive and
            self.player.target and 
            dead_player == self.player.target):
            self.has_won = True
            # Transition NEUTRE → GENTIL (rejoint le village)
            self.team = Team.GENTIL
            game.log(f"{self.player.pseudo} (Mercenaire) a accompli sa mission ! Il rejoint le village.")
    
    def check_win_condition(self, eliminated_player) -> bool:
        """Vérifie si le mercenaire a gagné."""
        return eliminated_player == self.player.target

"""Modèle pour les joueurs."""

from typing import Optional, Iterable
from models import role
from models.enums import RoleType, Team


class Player:
    """Représente un joueur dans la partie."""
    
    def __init__(self, pseudo: str, user_id: str):
        self.pseudo = pseudo
        self.user_id = user_id
        self._display_name: Optional[str] = None
        self.role: Optional['role.Role'] = None
        self.is_alive = True
        self.is_protected = False
        self.lovers: list['Player'] = []
        self.votes_against = 0
        self.can_vote = True
        self.is_mayor = False
        self.has_been_pardoned = False  # Pour l'idiot
        self.mentor: Optional['Player'] = None  # Pour l'enfant sauvage
        self.target: Optional['Player'] = None  # Pour le mercenaire
        self.messages_today: list[str] = []  # Pour le loup bavard
        self.original_role_name: Optional[str] = None  # Rôle d'origine (si changé via Voleur)
        self.is_jailed = False  # Pour le geolier
        
    def __repr__(self):
        return f"Player({self.pseudo}, {self.role.role_type if self.role else 'No role'}, {'alive' if self.is_alive else 'dead'})"
    
    @property
    def display_name(self) -> str:
        """Nom affiché du joueur (alias pour pseudo)."""
        return self._display_name or self.pseudo
    
    @display_name.setter
    def display_name(self, value: str):
        self._display_name = value
    
    def __eq__(self, other):
        if isinstance(other, Player):
            return self.user_id == other.user_id
        return False
    
    def __hash__(self):
        return hash(self.user_id)
    
    def get_team(self) -> Team:
        """Retourne l'équipe du joueur."""
        if self.role:
            return self.role.team
        return Team.NEUTRE
    
    def kill(self):
        """Tue le joueur."""
        self._kill_with_lovers(set())

    def _kill_with_lovers(self, visited: set[str]):
        if not self.is_alive or self.user_id in visited:
            return
        visited.add(self.user_id)
        self.is_alive = False
        for lover in list(self.lovers):
            if lover.is_alive:
                lover._kill_with_lovers(visited)

    def add_lover(self, other: 'Player'):
        if other and other != self and other not in self.lovers:
            self.lovers.append(other)

    def remove_lover(self, other: 'Player'):
        if other in self.lovers:
            self.lovers.remove(other)

    def clear_lovers(self):
        self.lovers = []

    def get_lovers(self) -> list['Player']:
        return list(self.lovers)

    @property
    def lover(self) -> Optional['Player']:
        """Compatibilite : retourne un amoureux si present."""
        return self.lovers[0] if self.lovers else None

    @lover.setter
    def lover(self, value: Optional['Player']):
        """Compatibilite : remplace la liste par un seul amoureux."""
        self.lovers = []
        if value:
            self.lovers.append(value)
    
    def add_message(self, message: str):
        """Ajoute un message à la liste des messages du jour."""
        self.messages_today.append(message)
    
    def reset_daily_data(self):
        """Réinitialise les données journalières (début de nuit).
        
        Note: votes_against n'est PAS réinitialisé ici car le Corbeau
        ajoute ses votes pendant la nuit et ils doivent persister
        jusqu'au vote du lendemain. La réinitialisation se fait
        dans _start_night() du GameManager (avant cet appel).
        """
        self.is_protected = False
        self.messages_today = []

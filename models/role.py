"""Modèle de base pour les rôles."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional
from models.enums import RoleType, Team, ActionType

if TYPE_CHECKING:
    from models.player import Player
    from game.game_manager import GameManager


# Noms lisibles pour chaque rôle
ROLE_DISPLAY_NAMES = {
    RoleType.VILLAGEOIS: "Villageois",
    RoleType.LOUP_GAROU: "Loup-Garou",
    RoleType.VOYANTE: "Voyante",
    RoleType.CHASSEUR: "Chasseur",
    RoleType.SORCIERE: "Sorcière",
    RoleType.CUPIDON: "Cupidon",
    RoleType.PETITE_FILLE: "Petite Fille",
    RoleType.VOLEUR: "Voleur",
    RoleType.LOUP_VOYANT: "Loup Voyant",
    RoleType.LOUP_BLANC: "Loup Blanc",
    RoleType.LOUP_NOIR: "Loup Noir",
    RoleType.LOUP_BAVARD: "Loup Bavard",
    RoleType.MONTREUR_OURS: "Montreur d'Ours",
    RoleType.CORBEAU: "Corbeau",
    RoleType.IDIOT: "Idiot",
    RoleType.ENFANT_SAUVAGE: "Enfant Sauvage",
    RoleType.MEDIUM: "Médium",
    RoleType.GARDE: "Garde",
    RoleType.VOYANTE_AURA: "Voyante d'Aura",
    RoleType.MERCENAIRE: "Mercenaire",
    RoleType.MENTALISTE: "Mentaliste",
    RoleType.DICTATEUR: "Dictateur",
    RoleType.CHASSEUR_DE_TETES: "Chasseur de T\u00eates",
}


class Role(ABC):
    """Classe de base abstraite pour tous les rôles."""
    
    def __init__(self, role_type: RoleType, team: Team):
        self.role_type = role_type
        self.team = team
        self.player: Optional['Player'] = None
    
    @property
    def name(self) -> str:
        """Nom lisible du rôle."""
        return ROLE_DISPLAY_NAMES.get(self.role_type, self.role_type.value)
    
    @property
    def description(self) -> str:
        """Description du rôle."""
        return self.get_description()
        
    def assign_to_player(self, player: 'Player'):
        """Assigne ce rôle à un joueur."""
        self.player = player
        player.role = self
    
    @abstractmethod
    def get_description(self) -> str:
        """Retourne la description du rôle."""
        pass
    
    def can_act_at_night(self) -> bool:
        """Indique si ce rôle a une action nocturne."""
        return False
    
    def on_game_start(self, game: 'GameManager'):
        """Appelé au début de la partie."""
        pass
    
    def on_night_start(self, game: 'GameManager'):
        """Appelé au début de la nuit."""
        pass
    
    def on_day_start(self, game: 'GameManager'):
        """Appelé au début du jour."""
        pass
    
    def on_player_death(self, game: 'GameManager', dead_player: 'Player', **kwargs):
        """Appelé quand un joueur meurt."""
        pass
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        """Vérifie si le rôle peut effectuer une action."""
        return False
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        """Effectue une action."""
        return {"success": False, "message": "Action non disponible pour ce rôle"}
    
    def can_vote_with_wolves(self) -> bool:
        """Indique si ce rôle peut voter avec les loups la nuit."""
        return self.team == Team.MECHANT

    def get_state(self) -> dict:
        """Sérialise l'état persistant du rôle (pour sauvegarde BDD).

        Les sous-classes surchargent cette méthode pour ajouter leurs
        attributs spécifiques. Les références à des Player sont stockées
        sous forme de ``user_id``.
        """
        return {}

    def restore_state(self, data: dict, players: dict):
        """Restaure l'état persistant du rôle depuis la BDD.

        Args:
            data: Dictionnaire retourné par ``get_state()``.
            players: Mapping ``user_id → Player`` (pour résoudre les refs).
        """
        pass

    def __repr__(self):
        return f"{self.role_type.value}"

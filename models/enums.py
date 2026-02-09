"""Énumérations pour le jeu Loup-Garou."""

from enum import Enum


class Team(Enum):
    """Équipes du jeu."""
    GENTIL = "GENTIL"
    MECHANT = "MECHANT"
    NEUTRE = "NEUTRE"
    COUPLE = "COUPLE"


class GamePhase(Enum):
    """Phases du jeu."""
    SETUP = "SETUP"
    NIGHT = "NIGHT"
    DAY = "DAY"
    VOTE = "VOTE"
    ENDED = "ENDED"


# Alias pour compatibilité arrière
Phase = GamePhase


class RoleType(Enum):
    """Types de rôles disponibles."""
    # Rôles de base
    VILLAGEOIS = "VILLAGEOIS"
    LOUP_GAROU = "LOUP_GAROU"
    VOYANTE = "VOYANTE"
    CHASSEUR = "CHASSEUR"
    SORCIERE = "SORCIERE"
    CUPIDON = "CUPIDON"
    PETITE_FILLE = "PETITE_FILLE"
    VOLEUR = "VOLEUR"
    
    # Rôles loups avancés
    LOUP_VOYANT = "LOUP_VOYANT"
    LOUP_BLANC = "LOUP_BLANC"
    LOUP_NOIR = "LOUP_NOIR"
    LOUP_BAVARD = "LOUP_BAVARD"
    
    # Rôles villageois avancés
    MONTREUR_OURS = "MONTREUR_OURS"
    CORBEAU = "CORBEAU"
    IDIOT = "IDIOT"
    ENFANT_SAUVAGE = "ENFANT_SAUVAGE"
    MEDIUM = "MEDIUM"
    GARDE = "GARDE"
    VOYANTE_AURA = "VOYANTE_AURA"
    
    # Rôles très avancés
    MERCENAIRE = "MERCENAIRE"
    MENTALISTE = "MENTALISTE"
    DICTATEUR = "DICTATEUR"


class ActionType(Enum):
    """Types d'actions possibles."""
    VOTE = "VOTE"
    KILL = "KILL"
    PROTECT = "PROTECT"
    SEE_ROLE = "SEE_ROLE"
    SEE_AURA = "SEE_AURA"
    HEAL = "HEAL"
    POISON = "POISON"
    MARRY = "MARRY"
    STEAL_ROLE = "STEAL_ROLE"
    DRAW_ROLES = "DRAW_ROLES"
    CONVERT = "CONVERT"
    CHOOSE_MENTOR = "CHOOSE_MENTOR"
    SPEAK_WITH_DEAD = "SPEAK_WITH_DEAD"
    ADD_VOTES = "ADD_VOTES"
    BECOME_WEREWOLF = "BECOME_WEREWOLF"
    DICTATOR_KILL = "DICTATOR_KILL"

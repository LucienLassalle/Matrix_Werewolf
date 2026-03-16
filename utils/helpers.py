"""Utilitaires pour le jeu."""

import time
import random
import string
from typing import List, Dict, Union
from models.player import Player
from models.enums import Team, RoleType


def format_player_list(players: List[Player], show_roles: bool = False) -> str:
    """
    Formate une liste de joueurs pour l'affichage.
    
    Args:
        players: Liste de joueurs
        show_roles: Afficher les rôles ou non
        
    Returns:
        Chaîne formatée
    """
    result = []
    for player in players:
        status = "✓" if player.is_alive else "✗"
        line = f"{status} {player.pseudo}"
        
        if show_roles and player.role:
            line += f" ({player.role.name})"
        
        if player.is_mayor:
            line += " 👑"
        
        if player.get_lovers():
            line += " 💕"
        
        result.append(line)
    
    return "\n".join(result)


def get_team_stats(players: List[Player]) -> dict:
    """
    Calcule les statistiques par équipe.
    
    Args:
        players: Liste de joueurs
        
    Returns:
        Dictionnaire avec les statistiques
    """
    stats = {
        Team.GENTIL: {"alive": 0, "dead": 0},
        Team.MECHANT: {"alive": 0, "dead": 0},
        Team.NEUTRE: {"alive": 0, "dead": 0}
    }
    
    for player in players:
        team = player.get_team()
        if player.is_alive:
            stats[team]["alive"] += 1
        else:
            stats[team]["dead"] += 1
    
    return stats


def format_game_summary(game) -> str:
    """
    Génère un résumé de la partie.
    
    Args:
        game: Instance de GameManager
        
    Returns:
        Résumé formaté
    """
    state = game.get_game_state()
    stats = get_team_stats(game.players)
    
    summary = f"""
╔════════════════════════════════════╗
║      RÉSUMÉ DE LA PARTIE          ║
╠════════════════════════════════════╣
║ Phase: {state['phase']:<27} ║
║ Jour: {state['day']:<28} ║
║ Nuit: {state['night']:<28} ║
╠════════════════════════════════════╣
║ Joueurs vivants: {state['living_players']}/{state['total_players']:<13} ║
║ Loups vivants: {state['wolves_alive']:<17} ║
╠════════════════════════════════════╣
║ Gentils: {stats[Team.GENTIL]['alive']} vivants, {stats[Team.GENTIL]['dead']} morts   ║
║ Méchants: {stats[Team.MECHANT]['alive']} vivants, {stats[Team.MECHANT]['dead']} morts  ║
║ Neutres: {stats[Team.NEUTRE]['alive']} vivants, {stats[Team.NEUTRE]['dead']} morts   ║
╚════════════════════════════════════╝
"""
    return summary


def validate_role_configuration(role_config: Dict[Union[str, RoleType], int], player_count: int) -> dict:
    """
    Valide une configuration de rôles.
    
    Args:
        role_config: Configuration des rôles (clés: RoleType ou str)
        player_count: Nombre de joueurs
        
    Returns:
        Résultat de la validation
    """
    # Normaliser les clés en RoleType
    def _to_role_type(key):
        if isinstance(key, RoleType):
            return key
        try:
            return RoleType(key)
        except (ValueError, KeyError):
            return None
    
    normalized = {}
    for key, count in role_config.items():
        rt = _to_role_type(key)
        if rt:
            normalized[rt] = count
    
    total_roles = sum(normalized.values())
    
    wolf_types = {RoleType.LOUP_GAROU, RoleType.LOUP_BLANC, RoleType.LOUP_NOIR,
                  RoleType.LOUP_BAVARD, RoleType.LOUP_VOYANT}
    wolf_count = sum(normalized.get(wt, 0) for wt in wolf_types)
    
    errors = []
    warnings = []
    
    if total_roles > player_count:
        errors.append(f"Trop de rôles configurés ({total_roles}) pour {player_count} joueurs")
    
    if wolf_count == 0:
        errors.append("Il faut au moins un loup dans la partie")
    
    # Rôles obligatoires
    mandatory_roles = {
        RoleType.SORCIERE: "Sorcière",
        RoleType.VOYANTE: "Voyante",
        RoleType.CHASSEUR: "Chasseur",
    }
    for rt, name in mandatory_roles.items():
        if normalized.get(rt, 0) == 0:
            errors.append(f"Le rôle {name} est obligatoire")
        elif normalized.get(rt, 0) > 1:
            errors.append(f"Maximum 1 {name} autorisé")
    
    if wolf_count >= player_count / 2:
        warnings.append("Attention: Il y a beaucoup de loups par rapport au nombre de joueurs")
    
    if player_count < 4:
        errors.append("Il faut au moins 4 joueurs pour une partie")
    
    if RoleType.VOYANTE in normalized and RoleType.VOYANTE_AURA in normalized:
        warnings.append("Voyante et Voyante d'Aura sont redondants")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def generate_game_id() -> str:
    """Génère un ID unique pour une partie."""
    timestamp = int(time.time())
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"GAME-{timestamp}-{random_part}"

"""Utilitaires pour le jeu."""

from typing import List
from models.player import Player
from models.enums import Team


def mask_wolf_message(message: str, sender_pseudo: str) -> str:
    """
    Masque les pseudos dans les messages des loups pour la petite fille.
    
    Args:
        message: Le message original
        sender_pseudo: Le pseudo de l'envoyeur
        
    Returns:
        Message avec pseudos masqués
    """
    # Remplacer le pseudo par "Loup-Garou"
    masked = message.replace(sender_pseudo, "Loup-Garou")
    return masked


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
            line += f" ({player.role.role_type.value})"
        
        if player.is_mayor:
            line += " 👑"
        
        if player.lover:
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


def validate_role_configuration(role_config: dict, player_count: int) -> dict:
    """
    Valide une configuration de rôles.
    
    Args:
        role_config: Configuration des rôles
        player_count: Nombre de joueurs
        
    Returns:
        Résultat de la validation
    """
    total_roles = sum(role_config.values())
    wolf_count = role_config.get("LOUP_GAROU", 0) + \
                 role_config.get("LOUP_BLANC", 0) + \
                 role_config.get("LOUP_NOIR", 0) + \
                 role_config.get("LOUP_BAVARD", 0) + \
                 role_config.get("LOUP_VOYANT", 0)
    
    errors = []
    warnings = []
    
    # Vérifications
    if total_roles > player_count:
        errors.append(f"Trop de rôles configurés ({total_roles}) pour {player_count} joueurs")
    
    if wolf_count == 0:
        errors.append("Il faut au moins un loup dans la partie")
    
    if wolf_count >= player_count / 2:
        warnings.append("Attention: Il y a beaucoup de loups par rapport au nombre de joueurs")
    
    if player_count < 4:
        errors.append("Il faut au moins 4 joueurs pour une partie")
    
    # Rôles incompatibles ou redondants
    if "VOYANTE" in role_config and "VOYANTE_AURA" in role_config:
        warnings.append("Voyante et Voyante d'Aura sont redondants")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def generate_game_id() -> str:
    """Génère un ID unique pour une partie."""
    import time
    import random
    import string
    
    timestamp = int(time.time())
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"GAME-{timestamp}-{random_part}"

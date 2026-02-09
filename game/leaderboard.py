"""Commandes pour le leaderboard et les statistiques."""

import logging
from database.game_db import GameDatabase

logger = logging.getLogger(__name__)


class LeaderboardManager:
    """Gère les commandes de statistiques et leaderboard."""
    
    def __init__(self, db: GameDatabase):
        self.db = db
    
    def get_leaderboard_message(self, limit: int = 10) -> str:
        """Génère un message formaté pour le leaderboard."""
        leaderboard = self.db.get_leaderboard(limit)
        
        if not leaderboard:
            return "📊 **Leaderboard**\n\nAucune partie enregistrée pour le moment."
        
        message = "🏆 **Leaderboard - Top Joueurs**\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, stats in enumerate(leaderboard):
            medal = medals[i] if i < 3 else f"{i+1}."
            
            message += (
                f"{medal} **{stats['pseudo']}**\n"
                f"   Parties: {stats['total_games']} | "
                f"Victoires: {stats['total_wins']} | "
                f"Taux: {stats['win_rate']:.1f}%\n\n"
            )
        
        return message
    
    def get_role_stats_message(self) -> str:
        """Génère un message formaté pour les statistiques de rôles."""
        role_stats = self.db.get_role_stats()
        
        if not role_stats:
            return "📊 **Statistiques par rôle**\n\nAucune donnée disponible."
        
        message = "📊 **Statistiques par rôle**\n\n"
        message += "🔥 **Rôles les plus victorieux:**\n\n"
        
        # Top 10 des rôles avec le meilleur taux de victoire
        for stats in role_stats[:10]:
            role_name = stats['role_type'].replace('_', ' ').title()
            message += (
                f"• **{role_name}**\n"
                f"  {stats['wins']}/{stats['games_played']} victoires "
                f"({stats['win_rate']:.1f}%)\n\n"
            )
        
        return message
    
    def get_player_stats_message(self, user_id: str, pseudo: str) -> str:
        """Génère un message formaté pour les stats d'un joueur."""
        stats = self.db.get_player_stats(user_id)
        
        if not stats:
            return f"📊 **Statistiques de {pseudo}**\n\nAucune partie jouée."
        
        global_stats = stats['global']
        role_stats = stats['roles']
        
        win_rate = (global_stats['total_wins'] / global_stats['total_games'] * 100 
                   if global_stats['total_games'] > 0 else 0)
        
        message = f"📊 **Statistiques de {pseudo}**\n\n"
        message += "📈 **Global:**\n"
        message += f"• Parties jouées: {global_stats['total_games']}\n"
        message += f"• Victoires: {global_stats['total_wins']}\n"
        message += f"• Défaites: {global_stats['total_games'] - global_stats['total_wins']}\n"
        message += f"• Taux de victoire: {win_rate:.1f}%\n"
        message += f"• Morts: {global_stats['total_deaths']}\n\n"
        
        if role_stats:
            message += "🎭 **Par rôle:**\n"
            for role in role_stats[:5]:  # Top 5 rôles joués
                role_name = role['role_type'].replace('_', ' ').title()
                role_win_rate = (role['wins'] / role['games'] * 100 
                               if role['games'] > 0 else 0)
                message += (
                    f"• **{role_name}**: {role['wins']}/{role['games']} "
                    f"({role_win_rate:.1f}%)\n"
                )
        
        return message
    
    def get_season_summary(self) -> str:
        """Génère un résumé de la saison en cours."""
        # TODO: Ajouter filtrage par période
        leaderboard = self.db.get_leaderboard(3)
        role_stats = self.db.get_role_stats()
        
        message = "🎮 **Résumé de la saison**\n\n"
        
        if leaderboard:
            message += "👑 **Top 3:**\n"
            for i, stats in enumerate(leaderboard):
                medal = ["🥇", "🥈", "🥉"][i]
                message += f"{medal} {stats['pseudo']} ({stats['total_wins']} victoires)\n"
            message += "\n"
        
        if role_stats:
            # Rôle avec le meilleur taux de victoire
            best_role = max(role_stats, key=lambda x: x['win_rate'])
            role_name = best_role['role_type'].replace('_', ' ').title()
            message += (
                f"🏆 **Rôle le plus fort:** {role_name}\n"
                f"   {best_role['win_rate']:.1f}% de victoires\n\n"
            )
            
            # Rôle le plus joué
            most_played = max(role_stats, key=lambda x: x['games_played'])
            role_name = most_played['role_type'].replace('_', ' ').title()
            message += (
                f"⭐ **Rôle le plus joué:** {role_name}\n"
                f"   {most_played['games_played']} parties\n"
            )
        
        return message

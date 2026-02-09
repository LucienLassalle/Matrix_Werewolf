"""Système de persistance avec SQLite."""

import sqlite3
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from models.player import Player
from models.enums import GamePhase, Team, RoleType

logger = logging.getLogger(__name__)


class GameDatabase:
    """Gère la persistance du jeu dans SQLite."""
    
    def __init__(self, db_path: str = "werewolf_game.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_database()
    
    def _init_database(self):
        """Initialise la base de données avec les tables nécessaires."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Table pour l'état du jeu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY,
                phase TEXT NOT NULL,
                day_count INTEGER NOT NULL,
                start_time TEXT,
                last_update TEXT NOT NULL,
                game_data TEXT NOT NULL
            )
        """)
        
        # Table pour les joueurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id TEXT PRIMARY KEY,
                pseudo TEXT NOT NULL,
                role_type TEXT,
                is_alive INTEGER NOT NULL,
                is_mayor INTEGER NOT NULL,
                is_protected INTEGER NOT NULL,
                lover_id TEXT,
                votes_against INTEGER NOT NULL,
                player_data TEXT
            )
        """)
        
        # Table pour les votes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                vote_type TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Table pour les statistiques
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                winner_team TEXT NOT NULL,
                total_players INTEGER NOT NULL,
                total_days INTEGER NOT NULL,
                game_data TEXT
            )
        """)
        
        # Table pour les statistiques des joueurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_stats (
                user_id TEXT NOT NULL,
                game_id TEXT NOT NULL,
                role_type TEXT NOT NULL,
                team TEXT NOT NULL,
                survived INTEGER NOT NULL,
                won INTEGER NOT NULL,
                kills INTEGER NOT NULL,
                PRIMARY KEY (user_id, game_id)
            )
        """)
        
        # Table pour le leaderboard
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                user_id TEXT PRIMARY KEY,
                pseudo TEXT NOT NULL,
                total_games INTEGER NOT NULL DEFAULT 0,
                total_wins INTEGER NOT NULL DEFAULT 0,
                total_deaths INTEGER NOT NULL DEFAULT 0,
                total_kills INTEGER NOT NULL DEFAULT 0,
                favorite_role TEXT,
                last_played TEXT
            )
        """)
        
        # Table pour les inscriptions (persistance crash-safe)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )
        """)
        
        self.conn.commit()
        logger.info(f"Base de données initialisée: {self.db_path}")
    
    def is_first_run(self) -> bool:
        """Vérifie si c'est le premier lancement (aucune partie jouée)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM game_history")
        row = cursor.fetchone()
        return row['count'] == 0 if row else True
    
    def save_game_state(
        self,
        phase: GamePhase,
        day_count: int,
        start_time: Optional[datetime],
        players: Dict[str, Player],
        votes: Dict,
        wolf_votes: Dict,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Sauvegarde l'état complet du jeu."""
        cursor = self.conn.cursor()
        
        # Sérialiser les données du jeu
        game_data = {
            'votes': votes,
            'wolf_votes': wolf_votes,
            'additional': additional_data or {}
        }
        
        # Sauvegarder l'état général
        cursor.execute("""
            INSERT OR REPLACE INTO game_state (id, phase, day_count, start_time, last_update, game_data)
            VALUES (1, ?, ?, ?, ?, ?)
        """, (
            phase.value,
            day_count,
            start_time.isoformat() if start_time else None,
            datetime.now().isoformat(),
            json.dumps(game_data)
        ))
        
        # Sauvegarder les joueurs
        cursor.execute("DELETE FROM players")
        for player in players.values():
            player_data = {
                'messages_today': player.messages_today,
                'has_been_pardoned': player.has_been_pardoned,
                'can_vote': player.can_vote
            }
            
            cursor.execute("""
                INSERT INTO players (
                    user_id, pseudo, role_type, is_alive, is_mayor,
                    is_protected, lover_id, votes_against, player_data
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player.user_id,
                player.pseudo,
                player.role.role_type.value if player.role else None,
                1 if player.is_alive else 0,
                1 if player.is_mayor else 0,
                1 if player.is_protected else 0,
                player.lover.user_id if player.lover else None,
                player.votes_against,
                json.dumps(player_data)
            ))
        
        # Sauvegarder les votes
        cursor.execute("DELETE FROM votes")
        for target_id, voters in votes.items():
            for voter_id in voters:
                cursor.execute("""
                    INSERT INTO votes (voter_id, target_id, vote_type, timestamp)
                    VALUES (?, ?, 'village', ?)
                """, (voter_id, target_id, datetime.now().isoformat()))
        
        for target_id, voters in wolf_votes.items():
            for voter_id in voters:
                cursor.execute("""
                    INSERT INTO votes (voter_id, target_id, vote_type, timestamp)
                    VALUES (?, ?, 'wolf', ?)
                """, (voter_id, target_id, datetime.now().isoformat()))
        
        self.conn.commit()
        logger.info(f"État du jeu sauvegardé (phase: {phase.value}, jour: {day_count})")
    
    def load_game_state(self) -> Optional[Dict[str, Any]]:
        """Charge l'état du jeu depuis la base de données."""
        cursor = self.conn.cursor()
        
        # Charger l'état général
        cursor.execute("SELECT * FROM game_state WHERE id = 1")
        game_row = cursor.fetchone()
        
        if not game_row:
            return None
        
        # Charger les joueurs
        cursor.execute("SELECT * FROM players")
        players_data = cursor.fetchall()
        
        # Charger les votes
        cursor.execute("SELECT * FROM votes WHERE vote_type = 'village'")
        village_votes = cursor.fetchall()
        
        cursor.execute("SELECT * FROM votes WHERE vote_type = 'wolf'")
        wolf_votes_data = cursor.fetchall()
        
        return {
            'phase': game_row['phase'],
            'day_count': game_row['day_count'],
            'start_time': game_row['start_time'],
            'game_data': json.loads(game_row['game_data']),
            'players': [dict(row) for row in players_data],
            'village_votes': [dict(row) for row in village_votes],
            'wolf_votes': [dict(row) for row in wolf_votes_data]
        }
    
    def clear_current_game(self):
        """Efface l'état du jeu en cours."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM game_state")
        cursor.execute("DELETE FROM players")
        cursor.execute("DELETE FROM votes")
        self.conn.commit()
        logger.info("État du jeu effacé")
    
    def save_game_result(
        self,
        game_id: str,
        start_time: datetime,
        end_time: datetime,
        winner_team: Team,
        players: Dict[str, Player],
        total_days: int
    ):
        """Sauvegarde les résultats d'une partie terminée."""
        cursor = self.conn.cursor()
        
        # Sauvegarder l'historique de la partie
        game_data = {
            'roles': {p.user_id: p.role.role_type.value for p in players.values()},
            'survivors': [p.user_id for p in players.values() if p.is_alive]
        }
        
        cursor.execute("""
            INSERT INTO game_history (
                game_id, start_time, end_time, winner_team,
                total_players, total_days, game_data
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id,
            start_time.isoformat() if start_time else datetime.now().isoformat(),
            end_time.isoformat(),
            winner_team.value,
            len(players),
            total_days,
            json.dumps(game_data)
        ))
        
        # Mettre à jour les statistiques des joueurs
        for player in players.values():
            # Déterminer si le joueur a gagné
            if winner_team == Team.NEUTRE:
                # Loup Blanc solo : seul le LB vivant gagne
                won = (player.role and 
                       player.role.role_type == RoleType.LOUP_BLANC and 
                       player.is_alive)
            elif winner_team == Team.COUPLE:
                # Couple : les amoureux vivants gagnent + Cupidon aussi
                if player.lover is not None and player.is_alive:
                    won = True
                elif (player.role and 
                      player.role.role_type == RoleType.CUPIDON):
                    won = True
                else:
                    won = False
            elif winner_team == Team.MECHANT:
                # Loups gagnent, mais le Loup Blanc perd avec eux
                if player.role and player.role.role_type == RoleType.LOUP_BLANC:
                    won = False
                else:
                    won = (player.get_team() == winner_team)
            else:
                won = (player.get_team() == winner_team)
            
            # Mercenaire : victoire individuelle (additive)
            if (player.role and 
                player.role.role_type == RoleType.MERCENAIRE and
                hasattr(player.role, 'has_won') and 
                player.role.has_won):
                won = True
            
            cursor.execute("""
                INSERT INTO player_stats (
                    user_id, game_id, role_type, team,
                    survived, won, kills
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                player.user_id,
                game_id,
                player.role.role_type.value,
                player.get_team().value,
                1 if player.is_alive else 0,
                1 if won else 0,
                0  # TODO: Tracker les kills
            ))
            
            # Mettre à jour le leaderboard
            cursor.execute("""
                INSERT INTO leaderboard (
                    user_id, pseudo, total_games, total_wins,
                    total_deaths, last_played
                )
                VALUES (?, ?, 1, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    pseudo = excluded.pseudo,
                    total_games = total_games + 1,
                    total_wins = total_wins + excluded.total_wins,
                    total_deaths = total_deaths + excluded.total_deaths,
                    last_played = excluded.last_played
            """, (
                player.user_id,
                player.pseudo,
                1 if won else 0,
                0 if player.is_alive else 1,
                datetime.now().isoformat()
            ))
        
        self.conn.commit()
        logger.info(f"Résultats de la partie {game_id} sauvegardés")
    
    def get_leaderboard(self, limit: int = 10) -> list:
        """Récupère le top des joueurs."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT user_id, pseudo, total_games, total_wins, total_deaths,
                   CAST(total_wins AS FLOAT) / total_games * 100 as win_rate
            FROM leaderboard
            WHERE total_games > 0
            ORDER BY total_wins DESC, win_rate DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_role_stats(self) -> list:
        """Récupère les statistiques par rôle."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT role_type,
                   COUNT(*) as games_played,
                   SUM(won) as wins,
                   CAST(SUM(won) AS FLOAT) / COUNT(*) * 100 as win_rate
            FROM player_stats
            GROUP BY role_type
            ORDER BY win_rate DESC
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_player_stats(self, user_id: str) -> Optional[Dict]:
        """Récupère les statistiques d'un joueur."""
        cursor = self.conn.cursor()
        
        # Stats globales
        cursor.execute("""
            SELECT * FROM leaderboard WHERE user_id = ?
        """, (user_id,))
        
        global_stats = cursor.fetchone()
        if not global_stats:
            return None
        
        # Stats par rôle
        cursor.execute("""
            SELECT role_type, COUNT(*) as games, SUM(won) as wins
            FROM player_stats
            WHERE user_id = ?
            GROUP BY role_type
            ORDER BY games DESC
        """, (user_id,))
        
        role_stats = [dict(row) for row in cursor.fetchall()]
        
        return {
            'global': dict(global_stats),
            'roles': role_stats
        }
    
    def close(self):
        """Ferme la connexion à la base de données."""
        if self.conn:
            self.conn.close()
            logger.info("Connexion à la base de données fermée")
    
    # ==================== Inscriptions (crash-safe) ====================
    
    def save_registration(self, user_id: str, display_name: str):
        """Sauvegarde une inscription joueur (persistante en cas de crash)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO registrations (user_id, display_name, registered_at)
            VALUES (?, ?, ?)
        """, (user_id, display_name, datetime.now().isoformat()))
        self.conn.commit()
        logger.info(f"Inscription sauvegardée en BDD: {display_name} ({user_id})")
    
    def remove_registration(self, user_id: str):
        """Supprime une inscription joueur."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM registrations WHERE user_id = ?", (user_id,))
        self.conn.commit()
        logger.info(f"Inscription supprimée: {user_id}")
    
    def load_registrations(self) -> Dict[str, str]:
        """Charge toutes les inscriptions depuis la BDD.
        
        Returns:
            Dict[user_id, display_name]
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, display_name FROM registrations")
        rows = cursor.fetchall()
        registrations = {row['user_id']: row['display_name'] for row in rows}
        if registrations:
            logger.info(f"{len(registrations)} inscription(s) restaurée(s) depuis la BDD")
        return registrations
    
    def clear_registrations(self):
        """Efface toutes les inscriptions (après démarrage de partie ou annulation)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM registrations")
        self.conn.commit()
        logger.info("Inscriptions effacées de la BDD")
    
    def has_active_game(self) -> bool:
        """Vérifie si une partie était en cours (pour détection de crash)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT phase FROM game_state WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            return False
        return row['phase'] not in ('SETUP', 'ENDED')

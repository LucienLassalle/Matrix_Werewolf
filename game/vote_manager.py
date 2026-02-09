"""Gestionnaire de votes."""

from typing import Dict, List, Optional
from models.player import Player
from models.enums import Team


class VoteManager:
    """Gère les votes durant la journée et la nuit.
    
    Les votes sont stockés sous forme voter_uid → target_uid pour
    faciliter la sérialisation et la cohérence.
    """
    
    def __init__(self):
        self.votes: Dict[str, str] = {}           # voter_uid → target_uid (village)
        self.wolf_votes: Dict[str, str] = {}       # voter_uid → target_uid (loups)
        self._player_cache: Dict[str, Player] = {} # uid → Player pour résolution
    
    def register_player(self, player: Player):
        """Enregistre un joueur dans le cache pour les résolutions."""
        if player:
            self._player_cache[player.user_id] = player
    
    def _cache_player(self, player: Player):
        """Ajoute un joueur au cache interne."""
        if player:
            self._player_cache[player.user_id] = player
    
    def _get_player(self, user_id: str) -> Optional[Player]:
        """Récupère un joueur depuis le cache."""
        return self._player_cache.get(user_id)
    
    # ==================== Méthodes principales ====================
    
    def cast_vote(self, voter: Player, target: Player, is_wolf_vote: bool = False) -> dict:
        """Enregistre un vote (village ou loup)."""
        if not voter.is_alive:
            return {"success": False, "message": "Vous êtes mort, vous ne pouvez pas voter"}
        
        if not voter.can_vote and not is_wolf_vote:
            return {"success": False, "message": "Vous n'avez pas le droit de vote"}
        
        if not target.is_alive:
            return {"success": False, "message": "Vous ne pouvez pas voter pour quelqu'un de mort"}
        
        self._cache_player(voter)
        self._cache_player(target)
        
        if is_wolf_vote:
            self.wolf_votes[voter.user_id] = target.user_id
        else:
            self.votes[voter.user_id] = target.user_id
        
        return {"success": True, "message": f"Vote enregistré pour {target.pseudo}"}
    
    def add_vote(self, voter: Player, target: Player):
        """Raccourci pour ajouter un vote de village."""
        self._cache_player(voter)
        self._cache_player(target)
        
        # Retirer l'ancien vote si existant (changement de cible)
        self.votes[voter.user_id] = target.user_id
    
    def add_wolf_vote(self, voter: Player, target: Player):
        """Raccourci pour ajouter un vote de loup."""
        self._cache_player(voter)
        self._cache_player(target)
        
        self.wolf_votes[voter.user_id] = target.user_id
    
    # ==================== Comptage ====================
    
    def count_votes(self) -> Dict[str, int]:
        """Compte les votes de village (avec poids du maire et votes_against du Corbeau).
        
        Returns:
            Dict[target_uid, nombre_de_votes]
        """
        counts: Dict[str, int] = {}
        for voter_uid, target_uid in self.votes.items():
            voter = self._player_cache.get(voter_uid)
            if voter and not voter.is_alive:
                continue  # Ignorer les votes des joueurs morts
            weight = 2 if voter and voter.is_mayor else 1
            counts[target_uid] = counts.get(target_uid, 0) + weight
        
        # Ajouter les votes_against (Corbeau, etc.)
        for uid, player in self._player_cache.items():
            if player.is_alive and player.votes_against > 0:
                counts[uid] = counts.get(uid, 0) + player.votes_against
        
        return counts
    
    def count_wolf_votes(self) -> Dict[str, int]:
        """Compte les votes des loups.
        
        Les votes des loups morts sont ignorés.
        
        Returns:
            Dict[target_uid, nombre_de_votes]
        """
        counts: Dict[str, int] = {}
        for voter_uid, target_uid in self.wolf_votes.items():
            voter = self._player_cache.get(voter_uid)
            if voter and not voter.is_alive:
                continue
            counts[target_uid] = counts.get(target_uid, 0) + 1
        return counts
    
    def get_vote_counts(self, is_wolf_vote: bool = False) -> Dict[str, int]:
        """Retourne le comptage des votes.
        
        Returns:
            Dict[target_uid, nombre_de_votes]
        """
        return self.count_wolf_votes() if is_wolf_vote else self.count_votes()
    
    # ==================== Résolution ====================
    
    def get_most_voted(self, is_wolf_vote: bool = False) -> Optional[Player]:
        """Retourne le joueur le plus voté.
        
        En cas d'égalité au vote du village, le Maire départage :
        si le Maire a voté pour un des candidats à égalité, celui-ci
        est éliminé.
        
        Returns:
            Le Player le plus voté, ou None en cas d'égalité/aucun vote.
        """
        counts = self.get_vote_counts(is_wolf_vote)
        
        if not counts:
            return None
        
        max_votes = max(counts.values())
        most_voted_uids = [uid for uid, c in counts.items() if c == max_votes]
        
        if len(most_voted_uids) == 1:
            return self._player_cache.get(most_voted_uids[0])
        
        # Égalité — le Maire départage (vote du village uniquement)
        if not is_wolf_vote:
            for player in self._player_cache.values():
                if player.is_mayor and player.is_alive and player.user_id in self.votes:
                    mayor_choice = self.votes[player.user_id]
                    if mayor_choice in most_voted_uids:
                        return self._player_cache.get(mayor_choice)
        
        return None
    
    # ==================== Réinitialisation ====================
    
    def reset_votes(self, wolf_votes: bool = False):
        """Réinitialise les votes."""
        if wolf_votes:
            self.wolf_votes.clear()
        else:
            self.votes.clear()
    
    def clear_votes(self):
        """Réinitialise les votes de village."""
        self.votes.clear()
    
    def clear_wolf_votes(self):
        """Réinitialise les votes de loups."""
        self.wolf_votes.clear()
    
    # ==================== Annulation ====================
    
    def remove_voter(self, user_id: str):
        """Retire tous les votes d'un joueur."""
        self.votes.pop(user_id, None)
        self.wolf_votes.pop(user_id, None)
    
    # ==================== Affichage ====================
    
    def get_vote_summary(self, is_wolf_vote: bool = False) -> str:
        """Génère un résumé des votes."""
        counts = self.get_vote_counts(is_wolf_vote)
        if not counts:
            return "Aucun vote enregistré."
        
        summary = "Résumé des votes:\n"
        for uid, vote_count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            player = self._player_cache.get(uid)
            name = player.pseudo if player else uid
            summary += f"- {name}: {vote_count} vote(s)\n"
        
        return summary

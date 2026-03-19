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
        self.mayor_votes_for: Dict[str, str] = {}  # voter_uid → target_uid (vote pour maire)
        self._player_cache: Dict[str, Player] = {} # uid → Player pour résolution
    
    def register_player(self, player: Player):
        """Enregistre un joueur dans le cache pour les résolutions."""
        if player:
            self._player_cache[player.user_id] = player
    
    # Alias pour compatibilité
    _cache_player = register_player
    
    def _get_player(self, user_id: str) -> Optional[Player]:
        """Récupère un joueur depuis le cache."""
        return self._player_cache.get(user_id)
    
    # ==================== Méthodes principales ====================
    
    def cast_vote(self, voter: Player, target: Player, is_wolf_vote: bool = False) -> dict:
        """Enregistre un vote (village ou loup)."""
        if not voter.is_alive:
            return {"success": False, "message": "Vous êtes mort.e, vous ne pouvez pas voter"}
        
        if not voter.can_vote and not is_wolf_vote:
            return {"success": False, "message": "Vous n'avez pas le droit de vote"}
        
        if not target.is_alive:
            return {"success": False, "message": "Vous ne pouvez pas voter pour quelqu'un de mort.e"}
        
        self._cache_player(voter)
        self._cache_player(target)
        
        if is_wolf_vote:
            self.wolf_votes[voter.user_id] = target.user_id
        else:
            self.votes[voter.user_id] = target.user_id
        
        return {"success": True, "message": f"Vote enregistré pour {target.pseudo}"}
    
    def cast_mayor_vote_for(self, voter: Player, target: Player) -> dict:
        """Enregistre un vote POUR un candidat à l'élection du maire."""
        if not voter.is_alive:
            return {"success": False, "message": "Vous êtes mort.e, vous ne pouvez pas voter"}
        if not voter.can_vote:
            return {"success": False, "message": "Vous n'avez pas le droit de vote"}
        if not target.is_alive:
            return {"success": False, "message": "Vous ne pouvez pas voter pour quelqu'un de mort.e"}
        
        self._cache_player(voter)
        self._cache_player(target)
        
        self.mayor_votes_for[voter.user_id] = target.user_id
        
        return {"success": True, "message": f"Vote pour **{target.pseudo}** enregistré"}
    
    def count_mayor_votes(self) -> Dict[str, int]:
        """Compte les votes pour l'élection du maire.
        
        Returns:
            Dict[target_uid, nombre_de_votes]
        """
        counts: Dict[str, int] = {}
        
        for voter_uid, target_uid in self.mayor_votes_for.items():
            voter = self._player_cache.get(voter_uid)
            if voter and not voter.is_alive:
                continue
            counts[target_uid] = counts.get(target_uid, 0) + 1
        
        return counts
    
    def get_mayor_vote_summary(self) -> str:
        """Génère un résumé des votes pour l'élection du maire."""
        counts = self.count_mayor_votes()
        if not counts:
            return "Aucun vote enregistré."

        voters_by_target: Dict[str, List[str]] = {}
        for voter_uid, target_uid in self.mayor_votes_for.items():
            voter = self._player_cache.get(voter_uid)
            if voter and not voter.is_alive:
                continue
            voter_name = voter.pseudo if voter else voter_uid
            voters_by_target.setdefault(target_uid, []).append(voter_name)
        
        summary = "Résumé des votes :\n"
        for uid, score in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            player = self._player_cache.get(uid)
            name = player.pseudo if player else uid
            voters = voters_by_target.get(uid, [])
            if voters:
                summary += f"- {name} : {score} vote(s) — {', '.join(voters)}\n"
            else:
                summary += f"- {name} : {score} vote(s)\n"
        
        return summary
    
    def reset_mayor_votes(self):
        """Réinitialise les votes pour l'élection du maire."""
        self.mayor_votes_for.clear()

    
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
        self.mayor_votes_for.pop(user_id, None)
    
    # ==================== Affichage ====================
    
    def get_vote_summary(self, is_wolf_vote: bool = False) -> str:
        """Génère un résumé des votes."""
        counts = self.get_vote_counts(is_wolf_vote)
        if not counts:
            return "Aucun vote enregistré."

        voters_by_target: Dict[str, List[str]] = {}
        vote_source = self.wolf_votes if is_wolf_vote else self.votes
        for voter_uid, target_uid in vote_source.items():
            voter = self._player_cache.get(voter_uid)
            if voter and not voter.is_alive:
                continue
            voter_name = voter.pseudo if voter else voter_uid
            if not is_wolf_vote and voter and voter.is_mayor:
                voter_name = f"{voter_name} (maire x2)"
            voters_by_target.setdefault(target_uid, []).append(voter_name)

        bonus_by_target: Dict[str, int] = {}
        if not is_wolf_vote:
            for uid, player in self._player_cache.items():
                if player.is_alive and player.votes_against > 0:
                    bonus_by_target[uid] = player.votes_against
        
        summary = "Résumé des votes:\n"
        for uid, vote_count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            player = self._player_cache.get(uid)
            name = player.pseudo if player else uid
            voters = voters_by_target.get(uid, [])
            bonus = bonus_by_target.get(uid)
            extras: List[str] = []
            if voters:
                extras.append(", ".join(voters))
            if bonus:
                extras.append(f"bonus: +{bonus}")
            if extras:
                summary += f"- {name}: {vote_count} vote(s) — {' | '.join(extras)}\n"
            else:
                summary += f"- {name}: {vote_count} vote(s)\n"
        
        return summary

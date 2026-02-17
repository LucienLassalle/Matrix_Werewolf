"""Tests unitaires pour le gestionnaire de jeu."""

import pytest
from game.game_manager import GameManager
from models.enums import RoleType, GamePhase, Team
from models.player import Player


class TestGameManager:
    """Tests pour le GameManager."""
    
    def setup_method(self):
        """Initialise une partie pour chaque test."""
        self.game = GameManager()
    
    def test_add_player(self):
        """Test l'ajout de joueurs."""
        result = self.game.add_player("Alice", "user_1")
        assert result["success"] == True
        assert len(self.game.players) == 1
        assert self.game.players["user_1"].pseudo == "Alice"
    
    def test_add_duplicate_player(self):
        """Test qu'on ne peut pas ajouter deux fois le même joueur."""
        self.game.add_player("Alice", "user_1")
        result = self.game.add_player("Bob", "user_1")
        assert result["success"] == False
    
    def test_start_game_not_enough_players(self):
        """Test qu'on ne peut pas démarrer avec moins de 5 joueurs."""
        self.game.add_player("Alice", "user_1")
        self.game.add_player("Bob", "user_2")
        result = self.game.start_game()
        assert result["success"] == False
    
    def test_start_game_success(self):
        """Test le démarrage d'une partie."""
        for i in range(5):
            self.game.add_player(f"Player{i}", f"user_{i}")
        
        self.game.set_roles({
            RoleType.LOUP_GAROU: 2,
            RoleType.VILLAGEOIS: 3
        })
        
        result = self.game.start_game()
        assert result["success"] == True
        assert self.game.phase == GamePhase.NIGHT
        
        for player in self.game.players.values():
            assert player.role is not None
    
    def test_get_living_players(self):
        """Test la récupération des joueurs vivants."""
        for i in range(3):
            self.game.add_player(f"Player{i}", f"user_{i}")
        
        assert len(self.game.get_living_players()) == 3
        
        self.game.players["user_0"].kill()
        assert len(self.game.get_living_players()) == 2
    
    def test_get_player_by_pseudo(self):
        """Test la recherche de joueur par pseudo."""
        self.game.add_player("Alice", "user_1")
        self.game.add_player("Bob", "user_2")
        
        player = self.game.get_player_by_pseudo("alice")
        assert player is not None
        assert player.pseudo == "Alice"
        
        player = self.game.get_player_by_pseudo("Charlie")
        assert player is None
    
    def test_neighbors(self):
        """Test la récupération des voisins."""
        for i in range(5):
            self.game.add_player(f"Player{i}", f"user_{i}")
        
        player = self.game.players["user_2"]
        neighbors = self.game.get_neighbors(player)
        
        assert len(neighbors) == 2
        assert self.game.players["user_1"] in neighbors
        assert self.game.players["user_3"] in neighbors
    
    def test_win_condition_wolves_win(self):
        """Test la condition de victoire des loups."""
        for i in range(8):
            self.game.add_player(f"Player{i}", f"user_{i}")
        
        self.game.set_roles({
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        
        self.game.start_game()
        
        # Tuer tous les non-loups
        for player in list(self.game.players.values()):
            if player.get_team() != Team.MECHANT:
                player.kill()
        
        winner = self.game.check_win_condition()
        assert winner is not None
        assert winner == Team.MECHANT
    
    def test_win_condition_village_wins(self):
        """Test la condition de victoire du village."""
        for i in range(7):
            self.game.add_player(f"Player{i}", f"user_{i}")
        
        self.game.set_roles({
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        
        self.game.start_game()
        
        for player in list(self.game.players.values()):
            if player.get_team() == Team.MECHANT:
                player.kill()
        
        winner = self.game.check_win_condition()
        assert winner is not None
        assert winner == Team.GENTIL


class TestPlayer:
    """Tests pour la classe Player."""
    
    def test_player_creation(self):
        """Test la création d'un joueur."""
        player = Player("Alice", "user_1")
        assert player.pseudo == "Alice"
        assert player.user_id == "user_1"
        assert player.is_alive == True
        assert player.can_vote == True
    
    def test_player_display_name(self):
        """Test la propriété display_name."""
        player = Player("Alice", "user_1")
        assert player.display_name == "Alice"
    
    def test_player_kill(self):
        """Test la mort d'un joueur."""
        player = Player("Alice", "user_1")
        player.kill()
        assert player.is_alive == False
    
    def test_lover_death(self):
        """Test que les amoureux meurent ensemble."""
        alice = Player("Alice", "user_1")
        bob = Player("Bob", "user_2")
        
        alice.lover = bob
        bob.lover = alice
        
        alice.kill()
        assert alice.is_alive == False
        assert bob.is_alive == False
    
    def test_reset_daily_data(self):
        """Test la réinitialisation des données journalières.
        
        Note: votes_against n'est PAS reset ici car le Corbeau en a besoin
        pendant la phase de vote. Le reset se fait dans _start_night().
        """
        player = Player("Alice", "user_1")
        player.votes_against = 5
        player.messages_today = ["test"]
        
        player.reset_daily_data()
        # votes_against est préservé (reset dans _start_night à la place)
        assert player.votes_against == 5
        assert len(player.messages_today) == 0


class TestVoteManagerBasic:
    """Tests de base pour le VoteManager."""
    
    def test_cast_vote(self):
        """Test l'enregistrement d'un vote."""
        from game.vote_manager import VoteManager
        
        vm = VoteManager()
        voter = Player("Alice", "user_1")
        target = Player("Bob", "user_2")
        
        result = vm.cast_vote(voter, target)
        assert result["success"] == True
        assert target.user_id in vm.votes.values()
    
    def test_cannot_vote_if_dead(self):
        """Test qu'un joueur mort ne peut pas voter."""
        from game.vote_manager import VoteManager
        
        vm = VoteManager()
        voter = Player("Alice", "user_1")
        target = Player("Bob", "user_2")
        
        voter.kill()
        result = vm.cast_vote(voter, target)
        assert result["success"] == False
    
    def test_mayor_double_vote(self):
        """Test que le maire compte pour 2 votes."""
        from game.vote_manager import VoteManager
        
        vm = VoteManager()
        mayor = Player("Alice", "user_1")
        mayor.is_mayor = True
        target = Player("Bob", "user_2")
        
        vm.cast_vote(mayor, target)
        counts = vm.get_vote_counts()
        assert counts[target.user_id] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

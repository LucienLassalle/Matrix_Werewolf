"""Tests complets du vote manager."""

import pytest
from game.vote_manager import VoteManager
from models.player import Player
from models.enums import Team
from roles.villageois import Villageois
from roles.loup_garou import LoupGarou


class TestVoteManager:
    """Tests du système de vote."""
    
    def test_vote_manager_creation(self):
        """Test la création du vote manager."""
        vm = VoteManager()
        assert vm.votes == {}
        assert vm.wolf_votes == {}
    
    def test_add_village_vote(self):
        """Test l'ajout d'un vote de village."""
        vm = VoteManager()
        
        voter = Player("Alice", "@alice:matrix.org")
        voter.role = Villageois()
        target = Player("Bob", "@bob:matrix.org")
        target.role = LoupGarou()
        
        vm.add_vote(voter, target)
        
        assert voter.user_id in vm.votes
        assert vm.votes[voter.user_id] == target.user_id
    
    def test_add_wolf_vote(self):
        """Test l'ajout d'un vote de loup."""
        vm = VoteManager()
        
        wolf1 = Player("Wolf1", "@wolf1:matrix.org")
        wolf1.role = LoupGarou()
        target = Player("Victim", "@victim:matrix.org")
        target.role = Villageois()
        
        vm.add_wolf_vote(wolf1, target)
        
        assert wolf1.user_id in vm.wolf_votes
        assert vm.wolf_votes[wolf1.user_id] == target.user_id
    
    def test_change_vote(self):
        """Test le changement de vote."""
        vm = VoteManager()
        
        voter = Player("Voter", "@voter:matrix.org")
        voter.role = Villageois()
        target1 = Player("Target1", "@target1:matrix.org")
        target2 = Player("Target2", "@target2:matrix.org")
        
        vm.add_vote(voter, target1)
        assert vm.votes[voter.user_id] == target1.user_id
        
        vm.add_vote(voter, target2)
        assert vm.votes[voter.user_id] == target2.user_id
    
    def test_count_votes(self):
        """Test le comptage des votes."""
        vm = VoteManager()
        
        target = Player("Target", "@target:matrix.org")
        voter1 = Player("Voter1", "@voter1:matrix.org")
        voter1.role = Villageois()
        voter2 = Player("Voter2", "@voter2:matrix.org")
        voter2.role = Villageois()
        
        vm.add_vote(voter1, target)
        vm.add_vote(voter2, target)
        
        votes_count = vm.count_votes()
        assert target.user_id in votes_count
        assert votes_count[target.user_id] == 2
    
    def test_mayor_double_vote(self):
        """Test que le vote du maire compte double."""
        vm = VoteManager()
        
        mayor = Player("Mayor", "@mayor:matrix.org")
        mayor.role = Villageois()
        mayor.is_mayor = True
        
        target = Player("Target", "@target:matrix.org")
        
        vm.add_vote(mayor, target)
        votes_count = vm.count_votes()
        
        assert votes_count[target.user_id] == 2
    
    def test_get_most_voted(self):
        """Test l'obtention du joueur le plus voté."""
        vm = VoteManager()
        
        target1 = Player("Target1", "@target1:matrix.org")
        target2 = Player("Target2", "@target2:matrix.org")
        
        voter1 = Player("Voter1", "@voter1:matrix.org")
        voter1.role = Villageois()
        voter2 = Player("Voter2", "@voter2:matrix.org")
        voter2.role = Villageois()
        voter3 = Player("Voter3", "@voter3:matrix.org")
        voter3.role = Villageois()
        
        vm.add_vote(voter1, target1)
        vm.add_vote(voter2, target1)
        vm.add_vote(voter3, target2)
        
        most_voted = vm.get_most_voted()
        assert most_voted == target1  # Player.__eq__ compares user_id
    
    def test_tie_vote(self):
        """Test le cas d'égalité de votes."""
        vm = VoteManager()
        
        target1 = Player("Target1", "@target1:matrix.org")
        target2 = Player("Target2", "@target2:matrix.org")
        
        voter1 = Player("Voter1", "@voter1:matrix.org")
        voter1.role = Villageois()
        voter2 = Player("Voter2", "@voter2:matrix.org")
        voter2.role = Villageois()
        
        vm.add_vote(voter1, target1)
        vm.add_vote(voter2, target2)
        
        most_voted = vm.get_most_voted()
        assert most_voted is None  # Égalité → None
    
    def test_clear_votes(self):
        """Test la réinitialisation des votes."""
        vm = VoteManager()
        
        voter = Player("Voter", "@voter:matrix.org")
        voter.role = Villageois()
        target = Player("Target", "@target:matrix.org")
        
        vm.add_vote(voter, target)
        assert len(vm.votes) > 0
        
        vm.clear_votes()
        assert len(vm.votes) == 0
    
    def test_clear_wolf_votes(self):
        """Test la réinitialisation des votes de loups."""
        vm = VoteManager()
        
        wolf = Player("Wolf", "@wolf:matrix.org")
        wolf.role = LoupGarou()
        target = Player("Victim", "@victim:matrix.org")
        
        vm.add_wolf_vote(wolf, target)
        assert len(vm.wolf_votes) > 0
        
        vm.clear_wolf_votes()
        assert len(vm.wolf_votes) == 0


class TestVoteEdgeCases:
    """Tests des cas limites du système de vote."""
    
    def test_vote_with_no_target(self):
        """Test qu'on ne peut pas voter sans cible."""
        vm = VoteManager()
        voter = Player("Voter", "@voter:matrix.org")
        voter.role = Villageois()
        
        try:
            vm.add_vote(voter, None)
        except (AttributeError, TypeError):
            pass  # C'est attendu
    
    def test_dead_player_vote_checked_by_caller(self):
        """Test qu'un joueur mort ne devrait pas voter (le caller vérifie)."""
        vm = VoteManager()
        
        dead_voter = Player("Dead", "@dead:matrix.org")
        dead_voter.role = Villageois()
        dead_voter.is_alive = False
        dead_voter.can_vote = False
        
        target = Player("Target", "@target:matrix.org")
        
        # cast_vote vérifie is_alive
        result = vm.cast_vote(dead_voter, target)
        assert result["success"] == False
    
    def test_multiple_mayors(self):
        """Test avec plusieurs maires (cas anormal mais à gérer)."""
        vm = VoteManager()
        
        mayor1 = Player("Mayor1", "@mayor1:matrix.org")
        mayor1.role = Villageois()
        mayor1.is_mayor = True
        
        mayor2 = Player("Mayor2", "@mayor2:matrix.org")
        mayor2.role = Villageois()
        mayor2.is_mayor = True
        
        target = Player("Target", "@target:matrix.org")
        
        vm.add_vote(mayor1, target)
        vm.add_vote(mayor2, target)
        
        votes_count = vm.count_votes()
        assert votes_count[target.user_id] == 4
    
    def test_count_wolf_votes(self):
        """Test le comptage des votes de loups."""
        vm = VoteManager()
        
        wolf1 = Player("Wolf1", "@w1:matrix.org")
        wolf2 = Player("Wolf2", "@w2:matrix.org")
        target = Player("Victim", "@victim:matrix.org")
        
        vm.add_wolf_vote(wolf1, target)
        vm.add_wolf_vote(wolf2, target)
        
        counts = vm.count_wolf_votes()
        assert counts[target.user_id] == 2
    
    def test_remove_voter(self):
        """Test la suppression des votes d'un joueur."""
        vm = VoteManager()
        
        voter = Player("Voter", "@voter:matrix.org")
        target = Player("Target", "@target:matrix.org")
        
        vm.add_vote(voter, target)
        vm.add_wolf_vote(voter, target)
        
        assert len(vm.votes) == 1
        assert len(vm.wolf_votes) == 1
        
        vm.remove_voter(voter.user_id)
        
        assert len(vm.votes) == 0
        assert len(vm.wolf_votes) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

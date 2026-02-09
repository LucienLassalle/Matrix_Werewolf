"""Tests de régression pour vérifier la compatibilité API."""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from models.role import Role
from roles import RoleFactory, create_role
from game.game_manager import GameManager
from game.vote_manager import VoteManager
from commands.command_handler import CommandHandler


class TestRoleAPI:
    """Vérifie que l'API des rôles est cohérente."""
    
    def test_create_role_factory(self):
        """Test la factory classique."""
        role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        assert isinstance(role, Role)
        assert role.role_type == RoleType.LOUP_GAROU
    
    def test_create_role_convenience(self):
        """Test la fonction create_role standalone."""
        role = create_role(RoleType.VOYANTE)
        assert isinstance(role, Role)
        assert role.role_type == RoleType.VOYANTE
    
    def test_role_base_properties(self):
        """Vérifie name, description, can_act_at_night sur le rôle de base."""
        role = RoleFactory.create_role(RoleType.VILLAGEOIS)
        assert role.name == "Villageois"
        assert isinstance(role.description, str)
        assert len(role.description) > 0
        assert role.can_act_at_night() == False
    
    def test_all_roles_have_team(self):
        """Tous les rôles doivent avoir une équipe."""
        for rt in RoleType:
            try:
                role = RoleFactory.create_role(rt)
                assert role.team in (Team.GENTIL, Team.MECHANT, Team.NEUTRE)
            except (ValueError, KeyError):
                pass  # RoleType non implémenté
    
    def test_night_active_roles(self):
        """Les rôles de nuit doivent retourner can_act_at_night() True."""
        night_roles = [
            RoleType.LOUP_GAROU, RoleType.VOYANTE, RoleType.SORCIERE,
            RoleType.GARDE, RoleType.CUPIDON, RoleType.LOUP_BLANC,
            RoleType.LOUP_VOYANT, RoleType.LOUP_NOIR, RoleType.MEDIUM,
        ]
        for rt in night_roles:
            role = RoleFactory.create_role(rt)
            assert role.can_act_at_night() == True, f"{rt.value} devrait agir la nuit"
    
    def test_passive_roles(self):
        """Les rôles passifs doivent retourner can_act_at_night() False."""
        passive_roles = [
            RoleType.VILLAGEOIS, RoleType.CHASSEUR, RoleType.IDIOT,
        ]
        for rt in passive_roles:
            role = RoleFactory.create_role(rt)
            assert role.can_act_at_night() == False, f"{rt.value} ne devrait pas agir la nuit"


class TestEnumsAPI:
    """Vérifie la cohérence des enums."""
    
    def test_gamephase_exists(self):
        assert hasattr(GamePhase, "SETUP")
        assert hasattr(GamePhase, "NIGHT")
        assert hasattr(GamePhase, "DAY")
        assert hasattr(GamePhase, "VOTE")
        assert hasattr(GamePhase, "ENDED")
    
    def test_phase_alias(self):
        """Phase est un alias de GamePhase pour rétrocompatibilité."""
        from models.enums import Phase
        assert Phase is GamePhase
    
    def test_team_couple(self):
        """Team.COUPLE doit exister."""
        assert hasattr(Team, "COUPLE")


class TestVoteManagerAPI:
    """Vérifie l'API du VoteManager."""
    
    def setup_method(self):
        self.vm = VoteManager()
        self.p1 = Player("Alice", "user_1")
        self.p2 = Player("Bob", "user_2")
        self.p3 = Player("Charlie", "user_3")
        self.vm.register_player(self.p1)
        self.vm.register_player(self.p2)
        self.vm.register_player(self.p3)
    
    def test_add_vote_and_count(self):
        self.vm.add_vote(self.p1, self.p2)
        counts = self.vm.count_votes()
        assert counts[self.p2.user_id] == 1
    
    def test_add_wolf_vote_and_count(self):
        self.vm.add_wolf_vote(self.p1, self.p2)
        counts = self.vm.count_wolf_votes()
        assert counts[self.p2.user_id] == 1
    
    def test_cast_vote_compat(self):
        """cast_vote doit toujours fonctionner."""
        result = self.vm.cast_vote(self.p1, self.p2)
        assert result["success"] == True
    
    def test_clear_votes(self):
        self.vm.add_vote(self.p1, self.p2)
        self.vm.clear_votes()
        assert len(self.vm.votes) == 0
    
    def test_clear_wolf_votes(self):
        self.vm.add_wolf_vote(self.p1, self.p2)
        self.vm.clear_wolf_votes()
        assert len(self.vm.wolf_votes) == 0
    
    def test_get_most_voted_returns_player(self):
        """get_most_voted retourne un Player."""
        self.vm.add_vote(self.p1, self.p2)
        self.vm.add_vote(self.p3, self.p2)
        most = self.vm.get_most_voted()
        assert isinstance(most, Player)
        assert most.user_id == self.p2.user_id
    
    def test_remove_voter(self):
        self.vm.add_vote(self.p1, self.p2)
        self.vm.remove_voter(self.p1.user_id)
        assert len(self.vm.votes) == 0


class TestGameManagerAPI:
    """Vérifie l'API du GameManager."""
    
    def test_players_is_dict(self):
        gm = GameManager()
        assert isinstance(gm.players, dict)
    
    def test_add_player(self):
        gm = GameManager()
        result = gm.add_player("Alice", "user_1")
        assert result["success"] == True
        assert "user_1" in gm.players
    
    def test_set_phase(self):
        gm = GameManager()
        gm.set_phase(GamePhase.NIGHT)
        assert gm.phase == GamePhase.NIGHT
    
    def test_get_player(self):
        gm = GameManager()
        gm.add_player("Alice", "user_1")
        p = gm.get_player("user_1")
        assert p is not None
        assert p.pseudo == "Alice"
    
    def test_get_player_by_pseudo(self):
        gm = GameManager()
        gm.add_player("Alice", "user_1")
        p = gm.get_player_by_pseudo("alice")
        assert p is not None
        assert p.user_id == "user_1"
    
    def test_check_victory_returns_team_or_none(self):
        gm = GameManager()
        for i in range(5):
            gm.add_player(f"P{i}", f"user_{i}")
        
        loup = RoleFactory.create_role(RoleType.LOUP_GAROU)
        loup.assign_to_player(gm.players["user_0"])
        
        for i in range(1, 5):
            v = RoleFactory.create_role(RoleType.VILLAGEOIS)
            v.assign_to_player(gm.players[f"user_{i}"])
        
        gm.phase = GamePhase.NIGHT
        result = gm.check_victory()
        assert result is None  # Game not over
        
        # Kill all villagers
        for i in range(1, 5):
            gm.players[f"user_{i}"].kill()
        
        result = gm.check_victory()
        assert result == Team.MECHANT
    
    def test_start_game_with_player_ids(self):
        gm = GameManager()
        gm.start_game(player_ids=["user_1", "user_2", "user_3", "user_4"])
        assert len(gm.players) == 4
        assert gm.phase == GamePhase.NIGHT
    
    def test_resolve_night_returns_uids(self):
        gm = GameManager()
        for i in range(5):
            gm.add_player(f"P{i}", f"user_{i}")
        gm.phase = GamePhase.NIGHT
        results = gm.resolve_night()
        assert "deaths" in results
        assert "saved" in results
        assert isinstance(results["deaths"], list)


class TestCommandHandlerAPI:
    """Vérifie l'API du CommandHandler."""
    
    def test_has_handle_command(self):
        gm = GameManager()
        ch = CommandHandler(gm)
        assert hasattr(ch, "handle_command")
        assert callable(ch.handle_command)
    
    def test_has_game_manager_alias(self):
        gm = GameManager()
        ch = CommandHandler(gm)
        assert hasattr(ch, "game_manager")
        assert ch.game_manager is gm


class TestPlayerAPI:
    """Vérifie l'API du Player."""
    
    def test_display_name(self):
        p = Player("Alice", "user_1")
        assert p.display_name == "Alice"
    
    def test_display_name_custom(self):
        p = Player("Alice", "user_1")
        p._display_name = "Alice au pays"
        assert p.display_name == "Alice au pays"
    
    def test_player_equality(self):
        p1 = Player("Alice", "user_1")
        p2 = Player("Alice", "user_1")
        assert p1 == p2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

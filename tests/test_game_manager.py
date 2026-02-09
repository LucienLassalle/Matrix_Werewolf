"""Tests complets du game manager."""

import pytest
from game.game_manager import GameManager
from models.enums import GamePhase, Team, RoleType
from models.player import Player
from roles.villageois import Villageois
from roles.loup_garou import LoupGarou
from roles.loup_blanc import LoupBlanc
from roles.voyante import Voyante
from roles.voleur import Voleur
from roles.corbeau import Corbeau
from roles import RoleFactory


class TestGameManagerBasics:
    """Tests de base du game manager."""
    
    def test_game_creation(self):
        """Test la création d'un game manager."""
        gm = GameManager()
        
        assert gm.phase == GamePhase.SETUP
        assert len(gm.players) == 0
        assert gm.day_count == 0
    
    def test_start_game(self):
        """Test le démarrage d'une partie avec player_ids."""
        gm = GameManager()
        
        player_ids = [f"@player{i}:matrix.org" for i in range(8)]
        gm.start_game(player_ids)
        
        assert gm.phase == GamePhase.NIGHT
        assert len(gm.players) == 8
        assert gm.day_count == 0
        
        for player in gm.players.values():
            assert player.role is not None
    
    def test_minimum_players(self):
        """Test qu'il faut un minimum de joueurs."""
        gm = GameManager()
        
        result = gm.start_game(["@player1:matrix.org"])
        assert result["success"] == False


class TestGamePhases:
    """Tests des phases de jeu."""
    
    def test_set_phase(self):
        """Test le changement de phase."""
        gm = GameManager()
        
        assert gm.phase == GamePhase.SETUP
        
        gm.set_phase(GamePhase.NIGHT)
        assert gm.phase == GamePhase.NIGHT
        
        gm.set_phase(GamePhase.DAY)
        assert gm.phase == GamePhase.DAY
        
        gm.set_phase(GamePhase.VOTE)
        assert gm.phase == GamePhase.VOTE
    
    def test_phase_progression(self):
        """Test la progression naturelle des phases."""
        gm = GameManager()
        player_ids = [f"@player{i}:matrix.org" for i in range(8)]
        gm.start_game(player_ids)
        
        assert gm.phase == GamePhase.NIGHT
        assert gm.day_count == 0
        
        gm.set_phase(GamePhase.DAY)
        assert gm.phase == GamePhase.DAY
        
        gm.set_phase(GamePhase.VOTE)
        assert gm.phase == GamePhase.VOTE
        
        gm.set_phase(GamePhase.NIGHT)
        assert gm.phase == GamePhase.NIGHT


class TestVictoryConditions:
    """Tests des conditions de victoire."""
    
    def test_villagers_win(self):
        """Test la victoire des villageois."""
        gm = GameManager()
        
        for i in range(3):
            player = Player(f"Villager{i}", f"@v{i}:matrix.org")
            player.role = Villageois()
            player.role.assign_to_player(player)
            gm.players[player.user_id] = player
        
        wolf = Player("Wolf", "@wolf:matrix.org")
        wolf.role = LoupGarou()
        wolf.role.assign_to_player(wolf)
        wolf.is_alive = False
        gm.players[wolf.user_id] = wolf
        
        winner = gm.check_victory()
        assert winner == Team.GENTIL
    
    def test_wolves_win(self):
        """Test la victoire des loups."""
        gm = GameManager()
        
        for i in range(2):
            wolf = Player(f"Wolf{i}", f"@w{i}:matrix.org")
            wolf.role = LoupGarou()
            wolf.role.assign_to_player(wolf)
            gm.players[wolf.user_id] = wolf
        
        for i in range(3):
            villager = Player(f"Villager{i}", f"@v{i}:matrix.org")
            villager.role = Villageois()
            villager.role.assign_to_player(villager)
            villager.is_alive = False
            gm.players[villager.user_id] = villager
        
        winner = gm.check_victory()
        assert winner == Team.MECHANT
    
    def test_couple_win(self):
        """Test la victoire du couple."""
        gm = GameManager()
        
        lover1 = Player("Lover1", "@l1:matrix.org")
        lover1.role = Villageois()
        lover1.role.assign_to_player(lover1)
        
        lover2 = Player("Lover2", "@l2:matrix.org")
        lover2.role = LoupGarou()
        lover2.role.assign_to_player(lover2)
        
        lover1.lover = lover2
        lover2.lover = lover1
        
        gm.players[lover1.user_id] = lover1
        gm.players[lover2.user_id] = lover2
        
        dead_player = Player("Dead", "@dead:matrix.org")
        dead_player.role = Villageois()
        dead_player.role.assign_to_player(dead_player)
        dead_player.is_alive = False
        gm.players[dead_player.user_id] = dead_player
        
        winner = gm.check_victory()
        assert winner == Team.COUPLE
    
    def test_no_winner_yet(self):
        """Test qu'il n'y a pas encore de gagnant."""
        gm = GameManager()
        
        for i in range(3):
            villager = Player(f"Villager{i}", f"@v{i}:matrix.org")
            villager.role = Villageois()
            villager.role.assign_to_player(villager)
            gm.players[villager.user_id] = villager
        
        for i in range(2):
            wolf = Player(f"Wolf{i}", f"@w{i}:matrix.org")
            wolf.role = LoupGarou()
            wolf.role.assign_to_player(wolf)
            gm.players[wolf.user_id] = wolf
        
        winner = gm.check_victory()
        assert winner is None


class TestPlayerManagement:
    """Tests de la gestion des joueurs."""
    
    def test_get_player(self):
        """Test la récupération d'un joueur."""
        gm = GameManager()
        
        player = Player("Alice", "@alice:matrix.org")
        player.role = Villageois()
        player.role.assign_to_player(player)
        gm.players[player.user_id] = player
        
        retrieved = gm.get_player("@alice:matrix.org")
        assert retrieved == player
        assert retrieved.pseudo == "Alice"
    
    def test_get_alive_players(self):
        """Test la récupération des joueurs vivants."""
        gm = GameManager()
        
        alive1 = Player("Alive1", "@a1:matrix.org")
        alive1.role = Villageois()
        gm.players[alive1.user_id] = alive1
        
        alive2 = Player("Alive2", "@a2:matrix.org")
        alive2.role = Villageois()
        gm.players[alive2.user_id] = alive2
        
        dead = Player("Dead", "@dead:matrix.org")
        dead.role = Villageois()
        dead.is_alive = False
        gm.players[dead.user_id] = dead
        
        alive_players = gm.get_living_players()
        assert len(alive_players) == 2
        assert dead not in alive_players
    
    def test_get_wolves(self):
        """Test la récupération des loups."""
        gm = GameManager()
        
        wolf1 = Player("Wolf1", "@w1:matrix.org")
        wolf1.role = LoupGarou()
        wolf1.role.assign_to_player(wolf1)
        gm.players[wolf1.user_id] = wolf1
        
        wolf2 = Player("Wolf2", "@w2:matrix.org")
        wolf2.role = LoupGarou()
        wolf2.role.assign_to_player(wolf2)
        gm.players[wolf2.user_id] = wolf2
        
        villager = Player("Villager", "@v:matrix.org")
        villager.role = Villageois()
        villager.role.assign_to_player(villager)
        gm.players[villager.user_id] = villager
        
        wolves = gm.get_living_wolves()
        assert len(wolves) == 2
        assert villager not in wolves


class TestNightResolution:
    """Tests de la résolution de nuit."""
    
    def test_resolve_night_no_deaths(self):
        """Test une nuit sans mort."""
        gm = GameManager()
        
        for i in range(5):
            player = Player(f"Player{i}", f"@p{i}:matrix.org")
            player.role = Villageois()
            player.role.assign_to_player(player)
            gm.players[player.user_id] = player
        
        gm.set_phase(GamePhase.NIGHT)
        results = gm.resolve_night()
        
        assert 'deaths' in results
        assert len(results['deaths']) == 0
    
    def test_resolve_night_with_wolf_kill(self):
        """Test une nuit avec une victime des loups."""
        gm = GameManager()
        
        victim = Player("Victim", "@victim:matrix.org")
        victim.role = Villageois()
        victim.role.assign_to_player(victim)
        gm.players[victim.user_id] = victim
        
        wolf = Player("Wolf", "@wolf:matrix.org")
        wolf.role = LoupGarou()
        wolf.role.assign_to_player(wolf)
        gm.players[wolf.user_id] = wolf
        
        gm.vote_manager.register_player(victim)
        gm.vote_manager.register_player(wolf)
        
        gm.set_phase(GamePhase.NIGHT)
        gm.vote_manager.add_wolf_vote(wolf, victim)
        
        results = gm.resolve_night()
        
        assert victim.user_id in results['deaths']
        assert victim.is_alive is False


class TestSpecialMechanics:
    """Tests des mécaniques spéciales."""
    
    def test_couple_death(self):
        """Test que les amoureux meurent ensemble."""
        gm = GameManager()
        
        lover1 = Player("Lover1", "@l1:matrix.org")
        lover1.role = Villageois()
        
        lover2 = Player("Lover2", "@l2:matrix.org")
        lover2.role = Villageois()
        
        lover1.lover = lover2
        lover2.lover = lover1
        
        gm.players[lover1.user_id] = lover1
        gm.players[lover2.user_id] = lover2
        
        lover1.kill()
        
        assert lover1.is_alive is False
        assert lover2.is_alive is False
    
    def test_mayor_election(self):
        """Test l'élection du maire."""
        gm = GameManager()
        
        player = Player("MayorElect", "@mayor:matrix.org")
        player.role = Villageois()
        player.role.assign_to_player(player)
        player.is_mayor = False
        gm.players[player.user_id] = player
        
        player.is_mayor = True
        
        assert player.is_mayor is True
        assert player.role.role_type.value == "VILLAGEOIS"
    
    def test_protected_player(self):
        """Test qu'un joueur protégé ne meurt pas."""
        gm = GameManager()
        
        victim = Player("Protected", "@protected:matrix.org")
        victim.role = Villageois()
        victim.role.assign_to_player(victim)
        victim.is_protected = True
        gm.players[victim.user_id] = victim
        
        wolf = Player("Wolf", "@wolf:matrix.org")
        wolf.role = LoupGarou()
        wolf.role.assign_to_player(wolf)
        gm.players[wolf.user_id] = wolf
        
        gm.vote_manager.register_player(victim)
        gm.vote_manager.register_player(wolf)
        
        gm.set_phase(GamePhase.NIGHT)
        gm.vote_manager.add_wolf_vote(wolf, victim)
        
        results = gm.resolve_night()
        
        assert victim.is_alive is True


class TestIntegration:
    """Tests d'intégration complets."""
    
    def test_full_game_cycle(self):
        """Test un cycle complet de jeu."""
        gm = GameManager()
        
        player_ids = [f"@player{i}:matrix.org" for i in range(8)]
        gm.start_game(player_ids)
        
        assert gm.phase == GamePhase.NIGHT
        assert gm.day_count == 0
        
        results = gm.resolve_night()
        
        gm.set_phase(GamePhase.DAY)
        assert gm.phase == GamePhase.DAY
        
        gm.set_phase(GamePhase.VOTE)
        assert gm.phase == GamePhase.VOTE
        
        winner = gm.check_victory()
    
    def test_game_with_multiple_roles(self):
        """Test une partie avec plusieurs rôles différents."""
        gm = GameManager()
        
        player_ids = [f"@player{i}:matrix.org" for i in range(10)]
        gm.start_game(player_ids)
        
        role_types = set()
        for player in gm.players.values():
            role_types.add(player.role.role_type)
        
        assert len(role_types) >= 2


class TestLoupBlancVictory:
    """Tests de la victoire du Loup Blanc."""
    
    def test_loup_blanc_solo_win(self):
        """Test que le Loup Blanc gagne seul (Team.NEUTRE)."""
        gm = GameManager()
        
        lb = Player("LoupBlanc", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        gm.players[lb.user_id] = lb
        
        # Tout le monde est mort sauf le LB
        dead1 = Player("Dead1", "@d1:matrix.org")
        dead1.role = Villageois()
        dead1.role.assign_to_player(dead1)
        dead1.is_alive = False
        gm.players[dead1.user_id] = dead1
        
        dead2 = Player("Dead2", "@d2:matrix.org")
        dead2.role = LoupGarou()
        dead2.role.assign_to_player(dead2)
        dead2.is_alive = False
        gm.players[dead2.user_id] = dead2
        
        winner = gm.check_win_condition()
        assert winner == Team.NEUTRE
    
    def test_loup_blanc_does_not_trigger_wolf_victory(self):
        """Test que le LB seul ne déclenche PAS la victoire des loups."""
        gm = GameManager()
        
        lb = Player("LoupBlanc", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        gm.players[lb.user_id] = lb
        
        villager = Player("Villager", "@v:matrix.org")
        villager.role = Villageois()
        villager.role.assign_to_player(villager)
        gm.players[villager.user_id] = villager
        
        # LB + 1 villageois → 1 wolf >= 1 non-wolf mais pas de regular_wolves
        winner = gm.check_win_condition()
        assert winner is None  # Le jeu continue
    
    def test_loup_blanc_loses_with_regular_wolves(self):
        """Test que le LB perd quand les loups réguliers gagnent."""
        gm = GameManager()
        
        lb = Player("LoupBlanc", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        gm.players[lb.user_id] = lb
        
        wolf = Player("Wolf", "@w:matrix.org")
        wolf.role = LoupGarou()
        wolf.role.assign_to_player(wolf)
        gm.players[wolf.user_id] = wolf
        
        # 2 wolves (1 regular + 1 LB), 0 non-wolves → wolves win, LB loses
        winner = gm.check_win_condition()
        assert winner == Team.MECHANT
    
    def test_loup_blanc_with_couple_win(self):
        """Test que le LB peut gagner avec son couple."""
        gm = GameManager()
        
        lb = Player("LoupBlanc", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        
        lover = Player("Lover", "@lover:matrix.org")
        lover.role = Villageois()
        lover.role.assign_to_player(lover)
        
        lb.lover = lover
        lover.lover = lb
        
        gm.players[lb.user_id] = lb
        gm.players[lover.user_id] = lover
        
        # Dead players
        dead = Player("Dead", "@dead:matrix.org")
        dead.role = LoupGarou()
        dead.role.assign_to_player(dead)
        dead.is_alive = False
        gm.players[dead.user_id] = dead
        
        winner = gm.check_win_condition()
        assert winner == Team.COUPLE


class TestCoupleVictory:
    """Tests de la victoire du couple."""
    
    def test_couple_wins_no_team_check(self):
        """Test que le couple gagne si les 2 derniers vivants sont amoureux (peu importe l'équipe)."""
        gm = GameManager()
        
        # Couple: un loup et un villageois
        lover1 = Player("Wolf", "@w:matrix.org")
        lover1.role = LoupGarou()
        lover1.role.assign_to_player(lover1)
        
        lover2 = Player("Villager", "@v:matrix.org")
        lover2.role = Villageois()
        lover2.role.assign_to_player(lover2)
        
        lover1.lover = lover2
        lover2.lover = lover1
        
        gm.players[lover1.user_id] = lover1
        gm.players[lover2.user_id] = lover2
        
        dead = Player("Dead", "@dead:matrix.org")
        dead.role = Villageois()
        dead.role.assign_to_player(dead)
        dead.is_alive = False
        gm.players[dead.user_id] = dead
        
        winner = gm.check_win_condition()
        assert winner == Team.COUPLE
    
    def test_couple_does_not_win_with_others_alive(self):
        """Test que le couple ne gagne pas s'il reste d'autres joueurs."""
        gm = GameManager()
        
        lover1 = Player("L1", "@l1:matrix.org")
        lover1.role = Villageois()
        lover1.role.assign_to_player(lover1)
        
        lover2 = Player("L2", "@l2:matrix.org")
        lover2.role = Villageois()
        lover2.role.assign_to_player(lover2)
        
        lover1.lover = lover2
        lover2.lover = lover1
        
        other = Player("Other", "@other:matrix.org")
        other.role = LoupGarou()
        other.role.assign_to_player(other)
        
        gm.players[lover1.user_id] = lover1
        gm.players[lover2.user_id] = lover2
        gm.players[other.user_id] = other
        
        winner = gm.check_win_condition()
        assert winner is None


class TestCorbeauVotes:
    """Tests de l'intégration des votes du Corbeau."""
    
    def test_corbeau_votes_counted_in_village_vote(self):
        """Test que les votes_against du Corbeau sont comptés dans le vote du village."""
        gm = GameManager()
        
        voter = Player("Voter", "@voter:matrix.org")
        voter.role = Villageois()
        gm.players[voter.user_id] = voter
        gm.vote_manager.register_player(voter)
        
        target = Player("Target", "@target:matrix.org")
        target.role = Villageois()
        target.votes_against = 2  # Corbeau a mis 2 votes
        gm.players[target.user_id] = target
        gm.vote_manager.register_player(target)
        
        other = Player("Other", "@other:matrix.org")
        other.role = Villageois()
        gm.players[other.user_id] = other
        gm.vote_manager.register_player(other)
        
        # Un seul vote normal + 2 votes du Corbeau
        gm.vote_manager.add_vote(voter, target)
        counts = gm.vote_manager.count_votes()
        
        assert counts[target.user_id] == 3  # 1 vote normal + 2 Corbeau
    
    def test_corbeau_can_also_vote_during_day(self):
        """Test que le Corbeau peut voter en plus de ses votes de nuit."""
        gm = GameManager()
        
        corbeau = Player("Corbeau", "@corbeau:matrix.org")
        corbeau.role = Villageois()  # Le rôle n'importe pas pour le vote
        gm.players[corbeau.user_id] = corbeau
        gm.vote_manager.register_player(corbeau)
        
        target = Player("Target", "@target:matrix.org")
        target.role = Villageois()
        target.votes_against = 2  # Corbeau a désigné cette cible la nuit
        gm.players[target.user_id] = target
        gm.vote_manager.register_player(target)
        
        # Le Corbeau vote aussi normalement pour la même cible
        gm.vote_manager.add_vote(corbeau, target)
        counts = gm.vote_manager.count_votes()
        
        # 1 vote normal du Corbeau + 2 votes_against = 3
        assert counts[target.user_id] == 3


class TestVoleurMechanics:
    """Tests des mécaniques du Voleur."""
    
    def test_voleur_extra_roles_generated(self):
        """Test que les cartes supplémentaires sont générées quand un Voleur est présent."""
        gm = GameManager()
        for i in range(5):
            gm.add_player(f"Player{i}", f"user_{i}")
        
        gm.set_roles({
            RoleType.VOLEUR: 1,
            RoleType.LOUP_GAROU: 1,
            RoleType.VILLAGEOIS: 3
        })
        
        gm.start_game()
        assert len(gm.extra_roles) == 2
    
    def test_voleur_no_extra_roles_without_voleur(self):
        """Test qu'il n'y a pas de cartes supplémentaires sans Voleur."""
        gm = GameManager()
        for i in range(5):
            gm.add_player(f"Player{i}", f"user_{i}")
        
        gm.set_roles({
            RoleType.LOUP_GAROU: 1,
            RoleType.VILLAGEOIS: 4
        })
        
        gm.start_game()
        assert len(gm.extra_roles) == 0
    
    def test_voleur_auto_resolve_drawn(self):
        """Test l'auto-résolution du Voleur qui a tiré mais pas choisi."""
        gm = GameManager()
        
        player = Player("Voleur", "user_voleur")
        voleur_role = Voleur()
        voleur_role.assign_to_player(player)
        gm.players[player.user_id] = player
        
        # Simuler des cartes tirées
        extra1 = RoleFactory.create_role(RoleType.VOYANTE)
        extra2 = RoleFactory.create_role(RoleType.CHASSEUR)
        voleur_role.drawn_roles = [extra1, extra2]
        
        gm._auto_resolve_voleur()
        
        # Le joueur a reçu automatiquement la première carte
        assert player.role.role_type == RoleType.VOYANTE
    
    def test_voleur_auto_resolve_no_draw(self):
        """Test l'auto-résolution du Voleur qui n'a rien fait."""
        gm = GameManager()
        
        player = Player("Voleur", "user_voleur")
        voleur_role = Voleur()
        voleur_role.assign_to_player(player)
        gm.players[player.user_id] = player
        
        gm._auto_resolve_voleur()
        
        # Le joueur reste Voleur mais le pouvoir est épuisé
        assert player.role.role_type == RoleType.VOLEUR
        assert player.role.has_used_power is True
    
    def test_get_roles_summary(self):
        """Test le résumé des rôles."""
        gm = GameManager()
        
        p1 = Player("P1", "user_1")
        p1.role = Villageois()
        p1.role.assign_to_player(p1)
        gm.players[p1.user_id] = p1
        
        p2 = Player("P2", "user_2")
        p2.role = Villageois()
        p2.role.assign_to_player(p2)
        gm.players[p2.user_id] = p2
        
        p3 = Player("P3", "user_3")
        p3.role = LoupGarou()
        p3.role.assign_to_player(p3)
        gm.players[p3.user_id] = p3
        
        summary = gm.get_roles_summary()
        assert RoleType.VILLAGEOIS in summary
        assert summary[RoleType.VILLAGEOIS]['count'] == 2
        assert RoleType.LOUP_GAROU in summary
        assert summary[RoleType.LOUP_GAROU]['count'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


class TestHasEvilRole:
    """Tests de la vérification de rôle méchant."""
    
    def test_has_evil_role_with_wolf(self):
        """Test qu'une partie avec un loup a un rôle méchant."""
        gm = GameManager()
        
        v = Player("V", "@v:matrix.org")
        v.role = Villageois()
        v.role.assign_to_player(v)
        gm.players[v.user_id] = v
        
        w = Player("W", "@w:matrix.org")
        w.role = LoupGarou()
        w.role.assign_to_player(w)
        gm.players[w.user_id] = w
        
        assert gm.has_evil_role() is True
    
    def test_has_evil_role_without_wolf(self):
        """Test qu'une partie sans loup n'a pas de rôle méchant."""
        gm = GameManager()
        
        for i in range(3):
            v = Player(f"V{i}", f"@v{i}:matrix.org")
            v.role = Villageois()
            v.role.assign_to_player(v)
            gm.players[v.user_id] = v
        
        assert gm.has_evil_role() is False
    
    def test_has_evil_role_with_loup_blanc(self):
        """Test que le Loup Blanc est considéré méchant (Team.MECHANT)."""
        gm = GameManager()
        
        lb = Player("LB", "@lb:matrix.org")
        lb.role = LoupBlanc()
        lb.role.assign_to_player(lb)
        gm.players[lb.user_id] = lb
        
        v = Player("V", "@v:matrix.org")
        v.role = Villageois()
        v.role.assign_to_player(v)
        gm.players[v.user_id] = v
        
        # Le LB est Team.MECHANT (même si sa victoire est NEUTRE)
        assert gm.has_evil_role() is True
    
    def test_start_game_fails_without_evil_role(self):
        """Test que start_game échoue sans rôle méchant."""
        gm = GameManager()
        for i in range(5):
            gm.add_player(f"Player{i}", f"user_{i}")
        
        gm.set_roles({
            RoleType.VILLAGEOIS: 5
        })
        
        result = gm.start_game()
        assert result["success"] is False
        assert "méchant" in result["message"]


class TestGetCupidonPlayer:
    """Tests de la récupération du Cupidon."""
    
    def test_get_cupidon_when_present(self):
        """Test la récupération du Cupidon quand il est présent."""
        from roles.cupidon import Cupidon
        
        gm = GameManager()
        
        cupidon_player = Player("Cupidon", "@cup:matrix.org")
        cupidon_player.role = Cupidon()
        cupidon_player.role.assign_to_player(cupidon_player)
        gm.players[cupidon_player.user_id] = cupidon_player
        
        result = gm.get_cupidon_player()
        assert result is not None
        assert result.user_id == "@cup:matrix.org"
    
    def test_get_cupidon_when_absent(self):
        """Test le retour None quand il n'y a pas de Cupidon."""
        gm = GameManager()
        
        v = Player("V", "@v:matrix.org")
        v.role = Villageois()
        v.role.assign_to_player(v)
        gm.players[v.user_id] = v
        
        result = gm.get_cupidon_player()
        assert result is None
    
    def test_get_cupidon_even_if_dead(self):
        """Test que le Cupidon est trouvé même mort."""
        from roles.cupidon import Cupidon
        
        gm = GameManager()
        
        cupidon_player = Player("Cupidon", "@cup:matrix.org")
        cupidon_player.role = Cupidon()
        cupidon_player.role.assign_to_player(cupidon_player)
        cupidon_player.is_alive = False
        gm.players[cupidon_player.user_id] = cupidon_player
        
        result = gm.get_cupidon_player()
        assert result is not None


# ═══════════════════════════════════════════════════════════
#  resolve_night : données wolf_target et converted
# ═══════════════════════════════════════════════════════════

def _make_game_night(*specs) -> GameManager:
    """Crée une partie en phase NIGHT."""
    from roles import RoleFactory
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestResolveNight:
    """Vérifie que resolve_night() retourne les bonnes données."""

    def test_resolve_night_includes_wolf_target(self):
        game = _make_game_night(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("V2", "v2", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.resolve_night()

        assert results["wolf_target"] == "v1"
        assert "v1" in results["deaths"]

    def test_resolve_night_includes_converted(self):
        game = _make_game_night(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("V2", "v2", RoleType.VILLAGEOIS),
        )
        from models.enums import ActionType
        ln = game.players["ln1"]
        target = game.players["v1"]

        ln.role.perform_action(game, ActionType.CONVERT)

        game.vote_manager.register_player(ln)
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(ln, target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.resolve_night()

        assert results["converted"] == "v1"
        assert "v1" not in results["deaths"]

    def test_resolve_night_no_conversion(self):
        game = _make_game_night(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("V2", "v2", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.resolve_night()

        assert results["converted"] is None
        assert "v1" in results["deaths"]

    def test_resolve_night_wrong_phase(self):
        game = _make_game_night(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY

        results = game.resolve_night()
        assert results["deaths"] == []
        assert results["wolf_target"] is None
        assert results["converted"] is None


# ═══════════════════════════════════════════════════════════
#  get_player_by_pseudo : recherche étendue
# ═══════════════════════════════════════════════════════════

class TestGetPlayerByPseudo:
    """Vérifie la recherche étendue de joueurs."""

    def test_by_pseudo(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("Alice") is not None

    def test_by_pseudo_case_insensitive(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("alice") is not None

    def test_by_matrix_id(self):
        game = GameManager()
        game.add_player("Alice", "@alice:matrix.org")
        p = game.get_player_by_pseudo("@alice:matrix.org")
        assert p is not None
        assert p.user_id == "@alice:matrix.org"

    def test_by_partial_matrix_id(self):
        game = GameManager()
        game.add_player("Alice", "@alice:matrix.org")
        p = game.get_player_by_pseudo("alice:matrix.org")
        assert p is not None

    def test_by_display_name(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        game.players["user_1"].display_name = "Alice Wonderland"
        p = game.get_player_by_pseudo("Alice Wonderland")
        assert p is not None

    def test_not_found(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("NotExist") is None


# ═══════════════════════════════════════════════════════════
#  Victoire des loups avec Mercenaire NEUTRE
# ═══════════════════════════════════════════════════════════

class TestMercenaireNeutreVictory:
    """Un Mercenaire NEUTRE ne doit pas bloquer la victoire des loups."""

    def test_neutre_mercenaire_does_not_block_wolf_victory(self):
        """Si seuls des loups + un Mercenaire NEUTRE sont vivants, les loups gagnent."""
        from roles import RoleFactory
        game = _make_game_night(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Mercenaire", "m1", RoleType.MERCENAIRE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        # Tuer tous les villageois
        game.players["a1"].kill()
        game.players["b1"].kill()
        game.players["e1"].kill()

        # Le Mercenaire est encore NEUTRE (mission non accomplie)
        assert game.players["m1"].get_team() == Team.NEUTRE

        result = game.check_win_condition()
        assert result == Team.MECHANT

    def test_gentil_mercenaire_blocks_wolf_victory(self):
        """Un Mercenaire devenu GENTIL bloque bien la victoire des loups."""
        from roles import RoleFactory
        game = _make_game_night(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Mercenaire", "m1", RoleType.MERCENAIRE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        # Le Mercenaire réussit sa mission → devient GENTIL
        game.players["m1"].role.team = Team.GENTIL

        # Tuer tous les villageois
        game.players["a1"].kill()
        game.players["b1"].kill()
        game.players["e1"].kill()

        result = game.check_win_condition()
        assert result is None  # Pas de victoire, la partie continue


class TestWinCheckAfterStartNight:
    """Vérifie que end_vote_phase revérifie la victoire après _start_night.

    Bug corrigé : si le Loup Bavard meurt au début de la nuit (mot non dit)
    et qu'il était le dernier loup, la victoire du village n'était pas
    détectée car check_win_condition n'était pas rappelé après _start_night.
    """

    def test_loup_bavard_last_wolf_dies_village_wins(self):
        """Le Loup Bavard (dernier loup) meurt → le village gagne."""
        from roles.loup_bavard import LoupBavard

        game = GameManager()
        for pseudo, uid in [("A", "a1"), ("B", "b1"), ("C", "c1"),
                            ("D", "d1"), ("LB", "lb1")]:
            game.add_player(pseudo, uid)

        # Assigner les rôles manuellement
        for uid in ["a1", "b1", "c1", "d1"]:
            from roles.villageois import Villageois
            role = Villageois()
            role.assign_to_player(game.players[uid])
        lb_role = LoupBavard()
        lb_role.assign_to_player(game.players["lb1"])

        # Simuler une partie en cours (VOTE) jour 1
        game.phase = GamePhase.VOTE
        game.day_count = 1
        game.night_count = 1

        # Le Loup Bavard a un mot mais ne l'a PAS dit
        lb_role.word_to_say = "fromage"
        lb_role.has_said_word = False

        # Résoudre le vote (pas de votes → pas d'élimination)
        result = game.end_vote_phase()

        # Le Loup Bavard devait mourir dans _start_night (mot non dit)
        assert not game.players["lb1"].is_alive

        # Victoire du village détectée immédiatement (pas d'attente au matin)
        assert result.get("winner") == Team.GENTIL
        assert game.phase == GamePhase.ENDED

    def test_loup_bavard_not_last_wolf_game_continues(self):
        """Un Loup Bavard meurt mais il reste d'autres loups → pas de victoire."""
        from roles.loup_bavard import LoupBavard

        game = GameManager()
        for pseudo, uid in [("A", "a1"), ("B", "b1"), ("C", "c1"),
                            ("D", "d1"), ("LB", "lb1"), ("W", "w1")]:
            game.add_player(pseudo, uid)

        for uid in ["a1", "b1", "c1", "d1"]:
            from roles.villageois import Villageois
            role = Villageois()
            role.assign_to_player(game.players[uid])
        lb_role = LoupBavard()
        lb_role.assign_to_player(game.players["lb1"])
        wolf_role = LoupGarou()
        wolf_role.assign_to_player(game.players["w1"])

        game.phase = GamePhase.VOTE
        game.day_count = 1
        game.night_count = 1

        lb_role.word_to_say = "fromage"
        lb_role.has_said_word = False

        result = game.end_vote_phase()

        assert not game.players["lb1"].is_alive
        assert result.get("winner") is None
        assert game.phase == GamePhase.NIGHT


class TestWinCheckAfterStartDay:
    """Vérifie que end_night revérifie la victoire après _start_day.

    Bug corrigé : si un joueur meurt au début du jour (ex: Mercenaire
    deadline dépassée + amoureux cascade) et que cela déclenche une
    condition de victoire, elle n'était pas détectée.
    """

    def test_mercenaire_deadline_plus_lover_cascade(self):
        """Le Mercenaire meurt (deadline) + son amoureux (dernier loup) → village gagne."""
        from roles.mercenaire import Mercenaire

        game = GameManager()
        for pseudo, uid in [("A", "a1"), ("B", "b1"), ("C", "c1"),
                            ("Merc", "m1"), ("Wolf", "w1")]:
            game.add_player(pseudo, uid)

        for uid in ["a1", "b1", "c1"]:
            from roles.villageois import Villageois
            role = Villageois()
            role.assign_to_player(game.players[uid])
        merc_role = Mercenaire()
        merc_role.assign_to_player(game.players["m1"])
        wolf_role = LoupGarou()
        wolf_role.assign_to_player(game.players["w1"])

        # Faire du Mercenaire et du Loup un couple
        game.players["m1"].lover = game.players["w1"]
        game.players["w1"].lover = game.players["m1"]

        # Le Mercenaire a raté sa deadline (2 jours déjà écoulés)
        merc_role.deadline = 2
        merc_role.days_elapsed = 2  # on_day_start va incrémenter à 3 > deadline
        merc_role.has_won = False

        # Simuler la nuit 2 (phase NIGHT, prête à être résolue)
        game.phase = GamePhase.NIGHT
        game.day_count = 2  # sera incrémenté à 3 par end_night
        game.night_count = 2

        result = game.end_night()

        # Le Mercenaire meurt au début du jour 3 (deadline dépassée)
        assert not game.players["m1"].is_alive
        # L'amoureux (loup) meurt en cascade
        assert not game.players["w1"].is_alive
        # Victoire du village détectée immédiatement
        assert result.get("winner") == Team.GENTIL
        assert game.phase == GamePhase.ENDED

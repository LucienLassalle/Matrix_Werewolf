"""Tests des mécaniques spéciales : nuit, Corbeau, Voleur, Cupidon, resolve_night."""

import pytest
from game.game_manager import GameManager
from models.enums import GamePhase, Team, RoleType
from models.player import Player
from roles.villageois import Villageois
from roles.loup_garou import LoupGarou
from roles.voleur import Voleur
from roles.corbeau import Corbeau
from roles import RoleFactory


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

        gm.vote_manager.add_vote(voter, target)
        counts = gm.vote_manager.count_votes()

        assert counts[target.user_id] == 3

    def test_corbeau_can_also_vote_during_day(self):
        """Test que le Corbeau peut voter en plus de ses votes de nuit."""
        gm = GameManager()

        corbeau = Player("Corbeau", "@corbeau:matrix.org")
        corbeau.role = Villageois()
        gm.players[corbeau.user_id] = corbeau
        gm.vote_manager.register_player(corbeau)

        target = Player("Target", "@target:matrix.org")
        target.role = Villageois()
        target.votes_against = 2
        gm.players[target.user_id] = target
        gm.vote_manager.register_player(target)

        gm.vote_manager.add_vote(corbeau, target)
        counts = gm.vote_manager.count_votes()

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
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1
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
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 1
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

        extra1 = RoleFactory.create_role(RoleType.VOYANTE)
        extra2 = RoleFactory.create_role(RoleType.CHASSEUR)
        voleur_role.drawn_roles = [extra1, extra2]

        gm._auto_resolve_voleur()

        assert player.role.role_type == RoleType.VOYANTE

    def test_voleur_auto_resolve_no_draw(self):
        """Test l'auto-résolution du Voleur qui n'a rien fait."""
        gm = GameManager()

        player = Player("Voleur", "user_voleur")
        voleur_role = Voleur()
        voleur_role.assign_to_player(player)
        gm.players[player.user_id] = player

        gm._auto_resolve_voleur()

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

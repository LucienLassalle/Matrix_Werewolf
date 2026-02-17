"""Tests de non-régression pour les bugs corrigés lors de l'audit.

Couvre :
1. reset() réinitialise mayor_election_done
2. resolve_mayor_election() ne s'exécute qu'une fois
3. can_vote_mayor() renvoie False après élection
4. end_vote_phase() ne relance pas l'élection au 2e vote
5. Garde : une seule protection par nuit
6. Garde : has_used_power_tonight reset entre les nuits
7. Idiot gracié (can_vote=False) ne peut pas voter pour le maire
8. Corbeau ne peut pas se maudire lui-même
9. _start_day() pending_kills avec killed_during_day=True
"""

import pytest
from unittest.mock import MagicMock, patch

from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def make_game(*specs, phase=GamePhase.NIGHT) -> GameManager:
    """Crée une partie avec les joueurs/rôles donnés."""
    game = GameManager(db_path=":memory:")
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = phase
    return game


# ═══════════════════════════════════════════════════════════
#  1. Mayor election : unicité
# ═══════════════════════════════════════════════════════════

class TestMayorElectionUniqueness:
    """L'élection du maire ne doit se produire qu'une seule fois."""

    def _make_vote_game(self):
        """Crée une partie prête pour le vote avec night_count=1."""
        game = make_game(
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Charlie", "c1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Diane", "d1", RoleType.VILLAGEOIS),
            phase=GamePhase.VOTE,
        )
        game.night_count = 1
        return game

    def test_resolve_mayor_election_once(self):
        """resolve_mayor_election() réussit la première fois, échoue la deuxième."""
        game = self._make_vote_game()

        # Première élection : succès
        game.vote_manager.cast_mayor_vote_for(game.players["a1"], game.players["b1"])
        result1 = game.resolve_mayor_election()
        assert result1["success"]
        assert result1["elected"] is game.players["b1"]
        assert game.mayor_election_done

        # Deuxième appel : échec
        result2 = game.resolve_mayor_election()
        assert not result2["success"]
        assert "déjà eu lieu" in result2["message"]

    def test_can_vote_mayor_false_after_election(self):
        """can_vote_mayor() renvoie False après l'élection."""
        game = self._make_vote_game()
        assert game.can_vote_mayor()  # Avant l'élection

        game.resolve_mayor_election()
        assert not game.can_vote_mayor()  # Après l'élection

    def test_end_vote_phase_no_double_election(self):
        """end_vote_phase() ne relance pas l'élection au deuxième cycle de vote."""
        game = self._make_vote_game()

        # Premier end_vote_phase déclenche l'élection
        game.vote_manager.cast_mayor_vote_for(game.players["a1"], game.players["b1"])
        game.vote_manager.cast_vote(game.players["a1"], game.players["c1"])
        result1 = game.end_vote_phase()
        assert result1["success"]
        assert result1.get("mayor_result") is not None
        elected = result1["mayor_result"]["elected"]

        # Après end_vote_phase, la partie a avancé à la nuit puis au jour suivant
        # Relançons un cycle de vote
        game.phase = GamePhase.VOTE
        game.vote_manager.reset_votes()
        game.vote_manager.cast_vote(game.players["a1"], game.players["d1"])
        result2 = game.end_vote_phase()
        assert result2["success"]
        # Pas de nouvelle élection
        assert result2.get("mayor_result") is None

    def test_reset_clears_mayor_election_done(self):
        """reset() réinitialise mayor_election_done pour la nouvelle partie."""
        game = self._make_vote_game()
        game.resolve_mayor_election()
        assert game.mayor_election_done

        game.reset()
        assert not game.mayor_election_done

    def test_mayor_election_done_survives_phase_transitions(self):
        """mayor_election_done reste True à travers les changements de phase."""
        game = self._make_vote_game()
        game.resolve_mayor_election()

        game.phase = GamePhase.NIGHT
        assert game.mayor_election_done

        game.phase = GamePhase.DAY
        assert game.mayor_election_done

        game.phase = GamePhase.VOTE
        assert game.mayor_election_done


# ═══════════════════════════════════════════════════════════
#  2. Garde : une seule protection par nuit
# ═══════════════════════════════════════════════════════════

class TestGardeOneProtectionPerNight:
    """Le garde ne peut protéger qu'un seul joueur par nuit."""

    def _make_garde_game(self):
        return make_game(
            ("Garde", "g1", RoleType.GARDE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )

    def test_second_protection_same_night_fails(self):
        """Protéger un deuxième joueur la même nuit échoue."""
        game = self._make_garde_game()
        garde = game.players["g1"].role

        result1 = garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        assert result1["success"]

        result2 = garde.perform_action(game, ActionType.PROTECT, game.players["b1"])
        assert not result2["success"]
        assert "déjà protégé" in result2["message"]

    def test_has_used_power_tonight_set_after_protect(self):
        """has_used_power_tonight passe à True après protection."""
        game = self._make_garde_game()
        garde = game.players["g1"].role
        assert not garde.has_used_power_tonight

        garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        assert garde.has_used_power_tonight

    def test_power_resets_on_night_start(self):
        """has_used_power_tonight se réinitialise au début de la nuit suivante."""
        game = self._make_garde_game()
        garde = game.players["g1"].role

        garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        assert garde.has_used_power_tonight

        garde.on_night_start(game)
        assert not garde.has_used_power_tonight

    def test_can_protect_different_person_after_reset(self):
        """Après reset, le garde peut protéger quelqu'un d'autre (pas la même personne)."""
        game = self._make_garde_game()
        garde = game.players["g1"].role

        # Nuit 1 : protège Alice
        garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        garde.on_night_start(game)

        # Nuit 2 : ne peut pas re-protéger Alice (last_protected)
        result_same = garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        assert not result_same["success"]
        assert "même personne" in result_same["message"]

        # Nuit 2 : peut protéger Bob
        result_diff = garde.perform_action(game, ActionType.PROTECT, game.players["b1"])
        assert result_diff["success"]

    def test_last_protected_updates_correctly(self):
        """last_protected pointe vers la dernière personne protégée."""
        game = self._make_garde_game()
        garde = game.players["g1"].role

        garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        assert garde.last_protected is game.players["a1"]

        garde.on_night_start(game)
        garde.perform_action(game, ActionType.PROTECT, game.players["b1"])
        assert garde.last_protected is game.players["b1"]


# ═══════════════════════════════════════════════════════════
#  3. Idiot gracié ne peut pas voter pour le maire
# ═══════════════════════════════════════════════════════════

class TestIdiotCannotVoteMayor:
    """Un idiot gracié (can_vote=False) ne peut pas voter pour le maire."""

    def test_pardoned_idiot_mayor_vote_rejected(self):
        """cast_mayor_vote_for refuse un joueur avec can_vote=False."""
        game = make_game(
            ("Idiot", "i1", RoleType.IDIOT),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            phase=GamePhase.VOTE,
        )
        idiot = game.players["i1"]
        idiot.can_vote = False  # Simule un idiot gracié

        result = game.vote_manager.cast_mayor_vote_for(idiot, game.players["a1"])
        assert not result["success"]
        assert "droit de vote" in result["message"]

    def test_alive_player_can_vote_mayor(self):
        """Un joueur vivant normal peut voter pour le maire."""
        game = make_game(
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Diane", "d1", RoleType.VILLAGEOIS),
            phase=GamePhase.VOTE,
        )
        result = game.vote_manager.cast_mayor_vote_for(
            game.players["a1"], game.players["b1"]
        )
        assert result["success"]

    def test_dead_player_cannot_vote_mayor(self):
        """Un joueur mort ne peut pas voter pour le maire."""
        game = make_game(
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Diane", "d1", RoleType.VILLAGEOIS),
            phase=GamePhase.VOTE,
        )
        game.players["a1"].is_alive = False
        result = game.vote_manager.cast_mayor_vote_for(
            game.players["a1"], game.players["b1"]
        )
        assert not result["success"]


# ═══════════════════════════════════════════════════════════
#  4. Corbeau ne peut pas se maudire
# ═══════════════════════════════════════════════════════════

class TestCorbeauCannotSelfCurse:
    """Le Corbeau ne peut pas cibler lui-même."""

    def test_corbeau_self_curse_fails(self):
        """perform_action(ADD_VOTES, self) doit échouer."""
        game = make_game(
            ("Corbeau", "c1", RoleType.CORBEAU),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        corbeau = game.players["c1"]
        initial_votes = corbeau.votes_against

        result = corbeau.role.perform_action(game, ActionType.ADD_VOTES, target=corbeau)
        assert not result["success"]
        assert "vous-même" in result["message"].lower()
        assert corbeau.votes_against == initial_votes  # Pas de votes ajoutés

    def test_corbeau_can_curse_others(self):
        """Le Corbeau peut toujours cibler d'autres joueurs."""
        game = make_game(
            ("Corbeau", "c1", RoleType.CORBEAU),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        alice = game.players["a1"]
        initial_votes = alice.votes_against

        result = game.players["c1"].role.perform_action(
            game, ActionType.ADD_VOTES, target=alice
        )
        assert result["success"]
        assert alice.votes_against == initial_votes + 2

    def test_corbeau_self_curse_does_not_consume_power(self):
        """Tenter de se maudire ne consomme pas le pouvoir de la nuit."""
        game = make_game(
            ("Corbeau", "c1", RoleType.CORBEAU),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        corbeau = game.players["c1"]

        # Tentative de self-curse
        result = corbeau.role.perform_action(game, ActionType.ADD_VOTES, target=corbeau)
        assert not result["success"]

        # Le pouvoir n'est pas consommé — le Corbeau peut encore agir
        assert not corbeau.role.has_used_power_tonight
        assert corbeau.role.can_perform_action(ActionType.ADD_VOTES)


# ═══════════════════════════════════════════════════════════
#  5. _start_day pending kills avec killed_during_day=True
# ═══════════════════════════════════════════════════════════

class TestStartDayPendingKills:
    """Les morts différées dans _start_day sont marquées killed_during_day=True."""

    def test_pending_kills_use_killed_during_day_true(self):
        """kill_player dans _start_day est appelé avec killed_during_day=True."""
        game = make_game(
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Diane", "d1", RoleType.VILLAGEOIS),
        )
        game.day_count = 1

        # Simuler un rôle qui ajoute un kill différé sur on_day_start
        original_on_day_start = game.players["a1"].role.on_day_start

        def fake_on_day_start(g):
            g._pending_kills.append(game.players["b1"])

        game.players["a1"].role.on_day_start = fake_on_day_start

        # Patch kill_player pour capturer les arguments
        calls = []
        original_kill = game.kill_player

        def tracking_kill(player, **kwargs):
            calls.append((player, kwargs))
            return original_kill(player, **kwargs)

        game.kill_player = tracking_kill

        game._start_day()

        # Vérifier que kill_player a été appelé avec killed_during_day=True
        assert len(calls) >= 1
        kill_call = [c for c in calls if c[0] is game.players["b1"]]
        assert len(kill_call) == 1
        assert kill_call[0][1].get("killed_during_day") is True

    def test_pending_kills_dead_player_skipped(self):
        """Un joueur déjà mort dans _pending_kills est ignoré."""
        game = make_game(
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
            ("Diane", "d1", RoleType.VILLAGEOIS),
        )
        game.day_count = 1

        # Bob déjà mort
        game.players["b1"].is_alive = False

        def fake_on_day_start(g):
            g._pending_kills.append(game.players["b1"])

        game.players["a1"].role.on_day_start = fake_on_day_start

        calls = []
        original_kill = game.kill_player

        def tracking_kill(player, **kwargs):
            calls.append(player)
            return original_kill(player, **kwargs)

        game.kill_player = tracking_kill

        game._start_day()

        # kill_player ne doit pas être appelé pour Bob (déjà mort)
        assert game.players["b1"] not in calls


# ═══════════════════════════════════════════════════════════
#  6. Intégration : Garde protège correctement sur plusieurs nuits
# ═══════════════════════════════════════════════════════════

class TestGardeMultiNightIntegration:
    """Test d'intégration du Garde sur plusieurs nuits."""

    def test_garde_protect_cycle(self):
        """Le garde alterne les protections sur plusieurs nuits."""
        game = make_game(
            ("Garde", "g1", RoleType.GARDE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        garde = game.players["g1"].role

        # Nuit 1 : protège Alice
        r1 = garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        assert r1["success"]

        # Nuit 1 : impossible de protéger Bob (déjà utilisé)
        r1b = garde.perform_action(game, ActionType.PROTECT, game.players["b1"])
        assert not r1b["success"]

        # Nuit 2
        garde.on_night_start(game)
        # Impossible de re-protéger Alice
        r2a = garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        assert not r2a["success"]
        # Protège Bob
        r2b = garde.perform_action(game, ActionType.PROTECT, game.players["b1"])
        assert r2b["success"]

        # Nuit 3
        garde.on_night_start(game)
        # Peut re-protéger Alice (last_protected = Bob)
        r3a = garde.perform_action(game, ActionType.PROTECT, game.players["a1"])
        assert r3a["success"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

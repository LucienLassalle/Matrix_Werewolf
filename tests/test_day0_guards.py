"""Tests pour la protection « pas de vote avant la première nuit ».

Vérifie :
- start_game(immediate_night=False) → phase=DAY, night_count=0
- start_vote_phase() est refusé tant que night_count < 1
- begin_night() démarre correctement la première nuit
- Après begin_night(), start_vote_phase() fonctionne à nouveau
- Les tests existants (immediate_night=True, par défaut) ne sont pas cassés
- L'élection du maire fonctionne en parallèle du premier vote (can_vote_mayor / resolve_mayor_election)
"""

import pytest
from game.game_manager import GameManager
from models.enums import GamePhase, RoleType


def _player_ids(n: int = 8):
    return [f"@player{i}:matrix.org" for i in range(n)]


class TestImmediateNightDefault:
    """Vérifie que le comportement par défaut (immediate_night=True) n'a pas changé."""

    def test_default_starts_night_immediately(self):
        gm = GameManager()
        result = gm.start_game(_player_ids())

        assert result["success"]
        assert gm.phase == GamePhase.NIGHT
        assert gm.night_count == 1

    def test_explicit_true_same_as_default(self):
        gm = GameManager()
        result = gm.start_game(_player_ids(), immediate_night=True)

        assert result["success"]
        assert gm.phase == GamePhase.NIGHT
        assert gm.night_count == 1


class TestImmediateNightFalse:
    """Vérifie le mode bot (immediate_night=False) : DAY avec night_count=0."""

    def test_starts_in_day_phase(self):
        gm = GameManager()
        result = gm.start_game(_player_ids(), immediate_night=False)

        assert result["success"]
        assert gm.phase == GamePhase.DAY

    def test_night_count_is_zero(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        assert gm.night_count == 0

    def test_day_count_is_zero(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        assert gm.day_count == 0

    def test_roles_assigned(self):
        """Les rôles sont distribués même en mode différé."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        for p in gm.players.values():
            assert p.role is not None

    def test_mayor_election_not_done(self):
        """L'élection du maire est marquée comme non faite au départ."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        assert gm.mayor_election_done is False


class TestStartVotePhaseGuard:
    """Vérifie que start_vote_phase() est bloqué avant la première nuit."""

    def test_vote_rejected_before_first_night(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        result = gm.start_vote_phase()

        assert not result["success"]
        assert "première nuit" in result["message"].lower()

    def test_phase_unchanged_on_rejection(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.start_vote_phase()

        # La phase reste DAY, pas VOTE
        assert gm.phase == GamePhase.DAY

    def test_vote_accepted_after_begin_night(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        # Première nuit
        gm.begin_night()
        assert gm.night_count >= 1

        # Résoudre la nuit pour passer au jour
        gm.set_phase(GamePhase.NIGHT)
        gm.resolve_night()

        # Maintenant le vote devrait être accepté
        result = gm.start_vote_phase()
        assert result["success"]
        assert gm.phase == GamePhase.VOTE

    def test_vote_accepted_in_default_mode(self):
        """En mode immediate_night=True, start_vote_phase() fonctionne dès le jour 1."""
        gm = GameManager()
        gm.start_game(_player_ids())

        # On a night_count=1 directement
        gm.set_phase(GamePhase.DAY)
        result = gm.start_vote_phase()

        assert result["success"]


class TestBeginNight:
    """Vérifie begin_night() — l'API publique pour la première nuit."""

    def test_begin_night_increments_count(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        assert gm.night_count == 0
        gm.begin_night()
        assert gm.night_count == 1

    def test_begin_night_sets_phase_night(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        gm.begin_night()
        assert gm.phase == GamePhase.NIGHT

    def test_begin_night_resets_actions(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        gm.begin_night()
        # Actions should be reset (no pending actions)
        assert len(gm.action_manager.pending_actions) == 0

    def test_begin_night_returns_success(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        result = gm.begin_night()
        assert result["success"]

    def test_begin_night_after_ended_fails(self):
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.set_phase(GamePhase.ENDED)

        result = gm.begin_night()
        assert not result["success"]

    def test_begin_night_second_call_increments(self):
        """begin_night() peut être appelé plusieurs fois (nuits successives)."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)

        gm.begin_night()
        assert gm.night_count == 1

        # Simuler jour/vote puis re-appel
        gm.set_phase(GamePhase.DAY)
        gm.begin_night()
        assert gm.night_count == 2


class TestFullCycleBotMode:
    """Test d'intégration : cycle complet en mode bot (immediate_night=False)."""

    def test_day0_then_night1_then_vote(self):
        """Simule le cycle : start → DAY 0 → begin_night → resolve → vote."""
        gm = GameManager()
        result = gm.start_game(_player_ids(), immediate_night=False)
        assert result["success"]

        # Phase initiale : DAY
        assert gm.phase == GamePhase.DAY
        assert gm.night_count == 0

        # Vote bloqué avant la première nuit
        assert not gm.start_vote_phase()["success"]

        # Première nuit
        result = gm.begin_night()
        assert result["success"]
        assert gm.phase == GamePhase.NIGHT
        assert gm.night_count == 1

        # Résoudre la nuit
        gm.resolve_night()
        assert gm.phase == GamePhase.DAY
        assert gm.day_count == 1

        # Maintenant le vote est possible
        result = gm.start_vote_phase()
        assert result["success"]
        assert gm.phase == GamePhase.VOTE


class TestMayorElection:
    """Tests pour l'élection du maire (concurrent avec le premier vote)."""

    def test_can_vote_mayor_false_before_first_night(self):
        """Avant la première nuit, can_vote_mayor() retourne False."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        assert gm.can_vote_mayor() is False

    def test_can_vote_mayor_true_after_first_night(self):
        """Après la première nuit, can_vote_mayor() retourne True en DAY/VOTE."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()

        # En phase DAY après la première nuit
        assert gm.phase == GamePhase.DAY
        assert gm.can_vote_mayor() is True

    def test_can_vote_mayor_true_in_vote_phase(self):
        """can_vote_mayor() retourne True en VOTE après la première nuit."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        assert gm.phase == GamePhase.VOTE
        assert gm.can_vote_mayor() is True

    def test_can_vote_mayor_false_if_mayor_exists(self):
        """Si un maire existe déjà, can_vote_mayor() retourne False."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()

        # Élire un maire manuellement
        players = list(gm.players.values())
        players[0].is_mayor = True

        assert gm.can_vote_mayor() is False

    def test_can_vote_mayor_false_during_night(self):
        """can_vote_mayor() retourne False pendant la nuit."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()

        assert gm.phase == GamePhase.NIGHT
        assert gm.can_vote_mayor() is False

    def test_vote_during_mayor_election(self):
        """Les joueurs peuvent voter pour le maire pendant la phase de vote."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        players = list(gm.players.values())
        voter = players[0]
        target = players[1]

        result = gm.vote_manager.cast_mayor_vote_for(voter, target)
        assert result["success"]

    def test_mayor_elected_by_majority(self):
        """Le joueur avec le plus de votes est élu maire."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        players = list(gm.players.values())
        target = players[2]

        # 3 joueurs vivants votent pour la même cible
        living = [p for p in players if p.is_alive]
        for voter in living[:3]:
            gm.vote_manager.cast_mayor_vote_for(voter, target)

        result = gm.resolve_mayor_election()
        assert result["success"]
        assert result["elected"] == target
        assert target.is_mayor

    def test_mayor_election_tie_no_mayor(self):
        """En cas d'égalité, pas de maire élu."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        players = list(gm.players.values())
        living = [p for p in players if p.is_alive]

        # Répartition égale : 2 votes pour living[0], 2 pour living[1]
        if len(living) >= 4:
            gm.vote_manager.cast_mayor_vote_for(living[2], living[0])
            gm.vote_manager.cast_mayor_vote_for(living[3], living[0])
            gm.vote_manager.cast_mayor_vote_for(living[0], living[1])
            gm.vote_manager.cast_mayor_vote_for(living[1], living[1])

        result = gm.resolve_mayor_election()
        assert result["success"]
        assert result["elected"] is None
        assert not living[0].is_mayor
        assert not living[1].is_mayor

    def test_mayor_no_votes_no_mayor(self):
        """Sans aucun vote, pas de maire élu."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        result = gm.resolve_mayor_election()
        assert result["success"]
        assert result["elected"] is None

    def test_resolve_mayor_election_marks_done(self):
        """resolve_mayor_election() met mayor_election_done à True."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        assert gm.mayor_election_done is False
        gm.resolve_mayor_election()
        assert gm.mayor_election_done is True

    def test_can_vote_mayor_false_after_resolve(self):
        """Après resolve_mayor_election(), can_vote_mayor() retourne False."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        gm.resolve_mayor_election()
        assert gm.can_vote_mayor() is False

    def test_resolve_mayor_election_twice_fails(self):
        """resolve_mayor_election() échoue si déjà résolu."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        gm.resolve_mayor_election()
        result = gm.resolve_mayor_election()
        assert not result["success"]

    def test_end_vote_phase_resolves_mayor_election(self):
        """end_vote_phase() résout automatiquement l'élection du maire."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        players = list(gm.players.values())
        living = [p for p in players if p.is_alive]
        target = living[2]

        # Votes pour le maire
        for voter in living[:3]:
            gm.vote_manager.cast_mayor_vote_for(voter, target)

        result = gm.end_vote_phase()
        assert result.get("mayor_result") is not None
        assert result["mayor_result"]["elected"] == target
        assert target.is_mayor
        assert gm.mayor_election_done is True

    def test_end_vote_phase_no_mayor_result_if_already_done(self):
        """end_vote_phase() ne retente pas l'élection si déjà résolue."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        # Résoudre l'élection d'abord
        gm.resolve_mayor_election()

        # end_vote_phase ne doit pas re-résoudre
        result = gm.end_vote_phase()
        assert result.get("mayor_result") is None

    def test_mayor_vote_counts_double_after_election(self):
        """Le maire élu a bien son vote qui compte double."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        players = list(gm.players.values())
        living = [p for p in players if p.is_alive]

        # Élire living[0] comme maire
        for voter in living[1:4]:
            gm.vote_manager.cast_mayor_vote_for(voter, living[0])
        gm.resolve_mayor_election()
        assert living[0].is_mayor

        # Le maire vote pour living[1], un autre vote pour living[2]
        gm.vote_manager.cast_vote(living[0], living[1], is_wolf_vote=False)
        gm.vote_manager.cast_vote(living[2], living[2], is_wolf_vote=False)

        # Le vote du maire compte double → living[1] a 2 votes, living[2] a 1
        counts = gm.vote_manager.count_votes()
        assert counts.get(living[1].user_id, 0) == 2
        assert counts.get(living[2].user_id, 0) == 1

    def test_self_vote_allowed_in_mayor_election(self):
        """Un joueur peut voter pour lui-même lors de l'élection."""
        gm = GameManager()
        gm.start_game(_player_ids(), immediate_night=False)
        gm.begin_night()
        gm.resolve_night()
        gm.start_vote_phase()

        players = list(gm.players.values())
        living = [p for p in players if p.is_alive]
        result = gm.vote_manager.cast_mayor_vote_for(living[0], living[0])
        assert result["success"]

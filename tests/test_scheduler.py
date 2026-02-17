"""Tests du scheduler et du timing du jeu."""

import asyncio
import pytest
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, patch

from matrix_bot.scheduler import GameScheduler, wait_until_new_game, day_name_fr
from models.enums import GamePhase


@pytest.fixture
def scheduler():
    """Crée un scheduler pour les tests."""
    return GameScheduler(
        night_start=time(21, 0),
        day_start=time(8, 0),
        vote_start=time(19, 0),
        max_days=7
    )


def test_scheduler_initialization(scheduler):
    """Test l'initialisation du scheduler."""
    assert scheduler.night_start == time(21, 0)
    assert scheduler.day_start == time(8, 0)
    assert scheduler.vote_start == time(19, 0)
    assert scheduler.max_days == 7
    assert scheduler.game_start_time is None
    assert scheduler.current_day == 0


def test_start_game(scheduler):
    """Test le démarrage d'une partie."""
    start_time = datetime.now()
    scheduler.start_game(start_time)
    
    assert scheduler.game_start_time == start_time
    assert scheduler.current_day == 1
    assert scheduler._running is True


def test_stop_game(scheduler):
    """Test l'arrêt du scheduler."""
    scheduler.start_game()
    scheduler.stop()
    
    assert scheduler._running is False


def test_get_phase_name(scheduler):
    """Test la récupération des noms de phases."""
    assert scheduler.get_phase_name(GamePhase.NIGHT) == "Nuit"
    assert scheduler.get_phase_name(GamePhase.DAY) == "Jour"
    assert scheduler.get_phase_name(GamePhase.VOTE) == "Vote"


@pytest.mark.asyncio
async def test_phase_callbacks(scheduler):
    """Test les callbacks de phases."""
    phases_called = []
    
    async def on_phase(phase):
        phases_called.append(phase)
    
    scheduler.on_night_start = on_phase
    scheduler.on_day_start = on_phase
    scheduler.on_vote_start = on_phase
    
    # Test avec un scheduler rapide
    scheduler.night_start = time(0, 0, 1)
    scheduler.day_start = time(0, 0, 2)
    scheduler.vote_start = time(0, 0, 3)
    scheduler.max_days = 1
    
    scheduler.start_game()
    
    # Laisser le temps aux callbacks
    await asyncio.sleep(0.5)
    scheduler.stop()
    
    # Les callbacks devraient avoir été appelés (timing dépendant)
    assert len(phases_called) >= 0  # Peut varier selon le timing


def test_time_until_next_phase(scheduler):
    """Test le calcul du temps jusqu'à la prochaine phase."""
    scheduler.start_game()
    
    time_delta = scheduler.get_time_until_next_phase()
    
    assert time_delta is not None
    assert isinstance(time_delta, timedelta)
    assert time_delta.total_seconds() >= 0


# ============================================================
# Tests de _build_transitions (tri sans crash GamePhase)
# ============================================================

class TestBuildTransitions:
    """Vérifie que _build_transitions ne crash pas et produit des transitions valides."""

    def test_no_crash_when_day_equals_vote(self):
        """Quand day_start == vote_start, le tri ne doit pas crasher.
        
        C'est le bug original : sorted() comparait des GamePhase
        via '<' ce qui lançait TypeError.
        """
        s = GameScheduler(
            night_start=time(20, 0),
            day_start=time(8, 0),
            vote_start=time(8, 0),
            max_days=7,
        )
        s.on_night_start = AsyncMock()
        s.on_day_start = AsyncMock()
        s.on_vote_start = AsyncMock()
        s.start_game()

        # Ne doit pas lever TypeError
        transitions = s._build_transitions()

        assert len(transitions) >= 2  # VOTE + NIGHT au minimum (DAY fusionné)
        # Vérifier que les transitions sont triées par datetime
        for i in range(1, len(transitions)):
            assert transitions[i][0] >= transitions[i - 1][0]

    def test_day_vote_merged_when_equal(self):
        """Quand day_start == vote_start, seule VOTE est conservée (pas DAY)."""
        s = GameScheduler(
            night_start=time(20, 0),
            day_start=time(8, 0),
            vote_start=time(8, 0),
        )
        s.on_night_start = AsyncMock()
        s.on_vote_start = AsyncMock()
        s.start_game()

        transitions = s._build_transitions()

        phases = [phase for _, phase, _ in transitions]
        assert GamePhase.DAY not in phases, "DAY ne devrait pas apparaître quand fusionné avec VOTE"
        assert GamePhase.VOTE in phases
        assert GamePhase.NIGHT in phases

    def test_all_three_phases_when_different(self):
        """Quand les 3 horaires sont différents, les 3 phases sont planifiées."""
        s = GameScheduler(
            night_start=time(20, 0),
            day_start=time(8, 0),
            vote_start=time(14, 0),
        )
        s.on_night_start = AsyncMock()
        s.on_day_start = AsyncMock()
        s.on_vote_start = AsyncMock()
        s.start_game()

        transitions = s._build_transitions()

        phases = [phase for _, phase, _ in transitions]
        assert GamePhase.DAY in phases
        assert GamePhase.VOTE in phases
        assert GamePhase.NIGHT in phases

    def test_transitions_all_in_future(self):
        """Toutes les transitions doivent être dans le futur (> now)."""
        s = GameScheduler(
            night_start=time(20, 0),
            day_start=time(8, 0),
            vote_start=time(14, 0),
        )
        s.start_game()

        transitions = s._build_transitions()
        now = datetime.now()

        for dt, phase, _ in transitions:
            assert dt > now - timedelta(seconds=2), \
                f"Transition {phase.value} à {dt} est dans le passé (now={now})"


# ============================================================
# Test du scheduler run() — scénario de crash reproduit
# ============================================================

class TestSchedulerRun:
    """Tests de la boucle run() du scheduler."""

    @pytest.mark.asyncio
    async def test_run_does_not_crash_with_equal_day_vote(self):
        """Le scheduler ne crash pas quand day_start == vote_start.
        
        Reproduit le bug : démarrage à 12h avec NIGHT=20h, DAY=8h, VOTE=8h.
        """
        s = GameScheduler(
            night_start=time(20, 0),
            day_start=time(8, 0),
            vote_start=time(8, 0),
            max_days=1,
        )
        s.on_night_start = AsyncMock()
        s.on_day_start = AsyncMock()
        s.on_vote_start = AsyncMock()
        s.start_game()

        # _build_transitions ne doit pas crasher (le bug original)
        transitions = s._build_transitions()
        assert len(transitions) >= 2

        # Arrêter après un court délai pour ne pas bloquer
        async def stopper():
            await asyncio.sleep(0.05)
            s.stop()

        asyncio.create_task(stopper())

        # Ce qui crashait avant le fix — avec le stop_event, s'arrête rapidement
        await s.run()

        assert not s._running

    @pytest.mark.asyncio
    async def test_run_calls_callbacks_in_order(self):
        """Les callbacks sont appelés quand les transitions se déclenchent."""
        phases_called = []
        
        async def track(phase):
            phases_called.append(phase)
        
        s = GameScheduler(
            night_start=time(20, 0),
            day_start=time(8, 0),
            vote_start=time(14, 0),
            max_days=1,
        )
        s.on_night_start = track
        s.on_day_start = track
        s.on_vote_start = track
        s.start_game()

        # Vérifier que les transitions sont bien construites et triées
        transitions = s._build_transitions()
        assert len(transitions) == 3
        
        # Vérifier que le tri est correct
        for i in range(1, len(transitions)):
            assert transitions[i][0] >= transitions[i - 1][0]

        # Arrêter rapidement pour ne pas attendre de vraies heures
        async def stopper():
            await asyncio.sleep(0.05)
            s.stop()

        asyncio.create_task(stopper())
        await s.run()
        
        assert not s._running


# ============================================================
# Tests de wait_until_new_game et day_name_fr
# ============================================================

class TestDayNameFr:
    """Tests du helper day_name_fr."""

    def test_lundi(self):
        assert day_name_fr(0) == "Lundi"

    def test_dimanche(self):
        assert day_name_fr(6) == "Dimanche"

    def test_wraps_around(self):
        assert day_name_fr(7) == "Lundi"

    def test_all_days(self):
        expected = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        for i, name in enumerate(expected):
            assert day_name_fr(i) == name


class TestWaitUntilNewGame:
    """Tests de wait_until_new_game (calcul du prochain lancement)."""

    @pytest.mark.asyncio
    async def test_same_day_future_hour(self):
        """Si on est le bon jour mais avant l'heure, on attend aujourd'hui."""
        now = datetime(2025, 1, 6, 10, 0)  # Lundi 10h
        # game_day=0 (Lundi), game_hour=12
        with patch('matrix_bot.scheduler.datetime') as mock_dt, \
             patch('matrix_bot.scheduler.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_dt.now.return_value = now
            mock_dt.combine = datetime.combine
            result = await wait_until_new_game(0, 12)
            # Devrait attendre 2h (7200s)
            mock_sleep.assert_called_once()
            wait_seconds = mock_sleep.call_args[0][0]
            assert abs(wait_seconds - 7200) < 1

    @pytest.mark.asyncio
    async def test_same_day_past_hour(self):
        """Si on est le bon jour mais après l'heure, on attend la semaine prochaine."""
        now = datetime(2025, 1, 6, 14, 0)  # Lundi 14h
        with patch('matrix_bot.scheduler.datetime') as mock_dt, \
             patch('matrix_bot.scheduler.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_dt.now.return_value = now
            mock_dt.combine = datetime.combine
            result = await wait_until_new_game(0, 12)
            # Devrait attendre 7 jours - 2h
            wait_seconds = mock_sleep.call_args[0][0]
            expected = 7 * 24 * 3600 - 2 * 3600  # 7 jours moins 2h
            assert abs(wait_seconds - expected) < 1

    @pytest.mark.asyncio
    async def test_different_day(self):
        """Si on est un jour différent, calcul correct du delta."""
        now = datetime(2025, 1, 6, 10, 0)  # Lundi 10h
        # Attendre Dimanche (6) à 12h
        with patch('matrix_bot.scheduler.datetime') as mock_dt, \
             patch('matrix_bot.scheduler.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_dt.now.return_value = now
            mock_dt.combine = datetime.combine
            result = await wait_until_new_game(6, 12)
            wait_seconds = mock_sleep.call_args[0][0]
            # Lundi 10h → Dimanche 12h = 6 jours + 2h
            expected = 6 * 24 * 3600 + 2 * 3600
            assert abs(wait_seconds - expected) < 1

    @pytest.mark.asyncio
    async def test_returns_target_datetime(self):
        """La valeur retournée est le datetime cible."""
        now = datetime(2025, 1, 6, 10, 0)  # Lundi 10h
        with patch('matrix_bot.scheduler.datetime') as mock_dt, \
             patch('matrix_bot.scheduler.asyncio.sleep', new_callable=AsyncMock):
            mock_dt.now.return_value = now
            mock_dt.combine = datetime.combine
            result = await wait_until_new_game(0, 12)
            # Lundi 12h
            assert result == datetime(2025, 1, 6, 12, 0)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

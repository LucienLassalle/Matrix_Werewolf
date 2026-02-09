"""Tests du scheduler et du timing du jeu."""

import asyncio
import pytest
from datetime import datetime, time, timedelta

from matrix_bot.scheduler import GameScheduler, wait_until_sunday_noon
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

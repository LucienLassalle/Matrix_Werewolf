"""Gestion du planning et des phases temporelles du jeu."""

import asyncio
from datetime import datetime, time, timedelta
from typing import Callable, Optional
import logging

from models.enums import GamePhase

logger = logging.getLogger(__name__)


class GameScheduler:
    """Planificateur pour gérer le timing du jeu en temps réel."""
    
    def __init__(
        self,
        night_start: time = time(21, 0),  # 21h00
        day_start: time = time(8, 0),     # 08h00
        vote_start: time = time(19, 0),   # 19h00
        max_days: int = 7
    ):
        self.night_start = night_start
        self.day_start = day_start
        self.vote_start = vote_start
        self.max_days = max_days
        
        self.game_start_time: Optional[datetime] = None
        self.current_day: int = 0
        self._tasks: list[asyncio.Task] = []
        self._running = False
        
        # Callbacks
        self.on_night_start: Optional[Callable] = None
        self.on_day_start: Optional[Callable] = None
        self.on_vote_start: Optional[Callable] = None
        self.on_game_end: Optional[Callable] = None
    
    def start_game(self, start_time: Optional[datetime] = None):
        """Démarre le planning du jeu."""
        self.game_start_time = start_time or datetime.now()
        self.current_day = 1
        self._running = True
        logger.info(f"Partie démarrée à {self.game_start_time}")
    
    async def run(self):
        """Boucle principale du planificateur."""
        if not self.game_start_time:
            raise ValueError("Le jeu n'a pas été démarré")
        
        logger.info("Démarrage du scheduler...")
        
        try:
            while self._running and self.current_day <= self.max_days:
                # Planifier les transitions de phase pour la journée
                await self._schedule_day_transitions()
                self.current_day += 1
        except asyncio.CancelledError:
            logger.info("Scheduler arrêté")
        except Exception as e:
            logger.error(f"Erreur dans le scheduler: {e}")
    
    async def _schedule_day_transitions(self):
        """Planifie les transitions pour une journée."""
        now = datetime.now()
        current_date = now.date()
        
        # Calculer les timestamps des transitions
        night_time = datetime.combine(current_date, self.night_start)
        day_time = datetime.combine(current_date, self.day_start)
        vote_time = datetime.combine(current_date, self.vote_start)
        
        # Si on a dépassé l'heure, passer au lendemain
        if now > night_time:
            night_time += timedelta(days=1)
        if now > day_time:
            day_time += timedelta(days=1)
        if now > vote_time:
            vote_time += timedelta(days=1)
        
        # Planifier dans l'ordre chronologique
        transitions = sorted([
            (day_time, GamePhase.DAY, self.on_day_start),
            (vote_time, GamePhase.VOTE, self.on_vote_start),
            (night_time, GamePhase.NIGHT, self.on_night_start)
        ])
        
        for transition_time, phase, callback in transitions:
            if not self._running:
                break
            
            # Attendre jusqu'à l'heure de transition
            wait_seconds = (transition_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                logger.info(f"Attente de {wait_seconds:.0f}s pour passer à {phase.value}")
                await asyncio.sleep(wait_seconds)
            
            # Exécuter le callback
            if callback and self._running:
                logger.info(f"Transition vers {phase.value}")
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(phase)
                    else:
                        callback(phase)
                except Exception as e:
                    logger.error(f"Erreur lors de la transition vers {phase.value}: {e}")
    
    def stop(self):
        """Arrête le planificateur."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        logger.info("Scheduler arrêté")
    
    def get_time_until_next_phase(self) -> Optional[timedelta]:
        """Retourne le temps restant avant la prochaine phase."""
        if not self.game_start_time or not self._running:
            return None
        
        now = datetime.now()
        current_date = now.date()
        
        # Prochaines transitions possibles
        next_times = []
        
        night_time = datetime.combine(current_date, self.night_start)
        if night_time > now:
            next_times.append(night_time)
        else:
            next_times.append(night_time + timedelta(days=1))
        
        day_time = datetime.combine(current_date, self.day_start)
        if day_time > now:
            next_times.append(day_time)
        else:
            next_times.append(day_time + timedelta(days=1))
        
        vote_time = datetime.combine(current_date, self.vote_start)
        if vote_time > now:
            next_times.append(vote_time)
        else:
            next_times.append(vote_time + timedelta(days=1))
        
        # Retourner le temps jusqu'à la prochaine
        next_time = min(next_times)
        return next_time - now
    
    def get_phase_name(self, phase: GamePhase) -> str:
        """Retourne le nom lisible de la phase."""
        names = {
            GamePhase.SETUP: "Configuration",
            GamePhase.NIGHT: "Nuit",
            GamePhase.DAY: "Jour",
            GamePhase.VOTE: "Vote",
            GamePhase.ENDED: "Terminée"
        }
        return names.get(phase, phase.value)


async def wait_until_sunday_noon() -> datetime:
    """Attend jusqu'au prochain Dimanche midi."""
    now = datetime.now()
    
    # Calculer le prochain Dimanche
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0:
        # On est Dimanche
        noon_today = datetime.combine(now.date(), time(12, 0))
        if now < noon_today:
            # Avant midi aujourd'hui
            next_sunday = noon_today
        else:
            # Après midi, prochain Dimanche
            next_sunday = noon_today + timedelta(days=7)
    else:
        # Pas Dimanche, calculer le prochain
        next_sunday_date = now.date() + timedelta(days=days_until_sunday)
        next_sunday = datetime.combine(next_sunday_date, time(12, 0))
    
    wait_time = (next_sunday - now).total_seconds()
    logger.info(f"Attente jusqu'au {next_sunday.strftime('%d/%m/%Y à %Hh%M')} "
                f"({wait_time / 3600:.1f} heures)")
    
    # Attendre (on pourrait ajouter des logs intermédiaires)
    await asyncio.sleep(wait_time)
    
    return next_sunday

"""Gestion du planning et des phases temporelles du jeu."""

import asyncio
import os
from datetime import datetime, time, timedelta
from typing import Callable, Optional
import logging

from models.enums import GamePhase

logger = logging.getLogger(__name__)


# Ordre canonique des phases pour le tri en cas d'égalité horaire.
# NIGHT doit passer en premier si elle tombe en même temps que DAY/VOTE
# (cas improbable), et DAY doit passer avant VOTE.
_PHASE_ORDER = {
    GamePhase.DAY: 0,
    GamePhase.VOTE: 1,
    GamePhase.NIGHT: 2,
}


class GameScheduler:
    """Planificateur pour gérer le timing du jeu en temps réel.
    
    Cycle attendu : NIGHT → DAY → VOTE → NIGHT → …
    
    Le vote commence à ``vote_start`` et se termine au début de la nuit
    (``night_start``).  La propriété :pyattr:`vote_end` reflète ce lien.
    
    Horaires lus depuis les variables d’environnement (avec possibilité
    de surcharge via les paramètres du constructeur) :
    - NIGHT_START_HOUR  → night_start
    - DAY_START_HOUR    → day_start
    - VOTE_START_HOUR   → vote_start
    - GAME_MAX_DURATION_DAYS → max_days
    """
    
    def __init__(
        self,
        night_start: time | None = None,
        day_start: time | None = None,
        vote_start: time | None = None,
        max_days: int | None = None,
    ):
        self.night_start = night_start or time(int(os.getenv('NIGHT_START_HOUR', '21')), 0)
        self.day_start   = day_start   or time(int(os.getenv('DAY_START_HOUR',   '8')),  0)
        self.vote_start  = vote_start  or time(int(os.getenv('VOTE_START_HOUR',  '19')), 0)
        self.max_days    = max_days     if max_days is not None else int(os.getenv('GAME_MAX_DURATION_DAYS', '7'))
        
        self.game_start_time: Optional[datetime] = None
        self.current_day: int = 0
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._stop_event: Optional[asyncio.Event] = None
        
        # Callbacks
        self.on_night_start: Optional[Callable] = None
        self.on_day_start: Optional[Callable] = None
        self.on_vote_start: Optional[Callable] = None
        self.on_game_end: Optional[Callable] = None

    @property
    def vote_end(self) -> time:
        """Heure de fin du vote = début de la nuit.

        Le vote se termine automatiquement quand la nuit commence.
        """
        return self.night_start
    
    def start_game(self, start_time: Optional[datetime] = None):
        """Démarre le planning du jeu."""
        self.game_start_time = start_time or datetime.now()
        self.current_day = 1
        self._running = True
        # Créer l'event dans le contexte de la boucle asyncio courante
        try:
            self._stop_event = asyncio.Event()
        except RuntimeError:
            # Pas de boucle asyncio active (tests synchrones)
            self._stop_event = None
        logger.info(f"Partie démarrée à {self.game_start_time}")
    
    async def run(self):
        """Boucle principale du planificateur."""
        if not self.game_start_time:
            raise ValueError("Le jeu n'a pas été démarré")
        
        logger.info("Démarrage du scheduler...")
        logger.info(
            f"Horaires configurés — Nuit: {self.night_start.strftime('%Hh%M')}, "
            f"Jour: {self.day_start.strftime('%Hh%M')}, "
            f"Vote: {self.vote_start.strftime('%Hh%M')}→{self.vote_end.strftime('%Hh%M')}, "
            f"Max jours: {self.max_days}"
        )
        
        try:
            while self._running and self.current_day <= self.max_days:
                logger.info(f"Scheduler — début du cycle jour {self.current_day}/{self.max_days}")
                await self._schedule_day_transitions()
                self.current_day += 1
        except asyncio.CancelledError:
            logger.info("Scheduler arrêté (CancelledError)")
        except Exception as e:
            logger.error(f"Erreur dans le scheduler: {e}", exc_info=True)
    
    def _build_transitions(self) -> list[tuple[datetime, GamePhase, Optional[Callable]]]:
        """Construit la liste des transitions futures, triées chronologiquement.
        
        Pour chaque phase (DAY, VOTE, NIGHT), calcule la prochaine occurrence
        strictement dans le futur (> now). Gère le cas où day_start == vote_start
        en dé-dupliquant : seule VOTE est conservée si les deux tombent en même
        temps (car DAY est alors implicitement le même moment).
        
        Returns:
            Liste de (datetime, GamePhase, callback) triée par datetime puis par
            ordre canonique des phases.
        """
        now = datetime.now()
        current_date = now.date()
        
        def next_occurrence(t: time) -> datetime:
            """Retourne la prochaine occurrence de l'heure `t` strictement > now."""
            dt = datetime.combine(current_date, t)
            if dt <= now:
                dt += timedelta(days=1)
            return dt
        
        day_time = next_occurrence(self.day_start)
        vote_time = next_occurrence(self.vote_start)
        night_time = next_occurrence(self.night_start)
        
        transitions: list[tuple[datetime, GamePhase, Optional[Callable]]] = []
        
        # Si day_start == vote_start, ne garder que VOTE 
        # (la phase DAY serait de durée 0, ça n'a pas de sens)
        if self.day_start == self.vote_start:
            logger.debug(
                "day_start == vote_start (%s) — la phase DAY est fusionnée avec VOTE",
                self.day_start.strftime('%Hh%M'),
            )
            transitions.append((vote_time, GamePhase.VOTE, self.on_vote_start))
        else:
            transitions.append((day_time, GamePhase.DAY, self.on_day_start))
            transitions.append((vote_time, GamePhase.VOTE, self.on_vote_start))
        
        transitions.append((night_time, GamePhase.NIGHT, self.on_night_start))
        
        # Tri stable : par datetime, puis par _PHASE_ORDER en cas d'égalité.
        # Cela évite le crash « '<' not supported between instances of 'GamePhase' ».
        transitions.sort(key=lambda t: (t[0], _PHASE_ORDER.get(t[1], 99)))
        
        return transitions
    
    async def _interruptible_sleep(self, seconds: float):
        """Sleep interruptible par stop(). Retourne True si interrompu."""
        if seconds <= 0:
            return False
        if self._stop_event:
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
                return True  # L'event a été set → interruption
            except asyncio.TimeoutError:
                return False  # Timeout normal → le sleep est fini
        else:
            await asyncio.sleep(seconds)
            return False

    async def _schedule_day_transitions(self):
        """Planifie les transitions pour un cycle (journée de jeu).
        
        Construit la liste des prochaines transitions et les exécute
        séquentiellement en attendant l'heure de chacune.
        """
        transitions = self._build_transitions()
        
        logger.info(
            "Transitions planifiées : %s",
            " → ".join(
                f"{phase.value}@{dt.strftime('%d/%m %Hh%M')}"
                for dt, phase, _ in transitions
            ),
        )
        
        for transition_time, phase, callback in transitions:
            if not self._running:
                logger.info("Scheduler arrêté — interruption des transitions")
                break
            
            # Attendre jusqu'à l'heure de transition
            wait_seconds = (transition_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                logger.info(
                    f"⏳ Attente de {wait_seconds:.0f}s "
                    f"({wait_seconds / 3600:.1f}h) pour passer à {phase.value} "
                    f"(prévu à {transition_time.strftime('%Hh%M')})"
                )
                interrupted = await self._interruptible_sleep(wait_seconds)
                if interrupted:
                    logger.info("Scheduler interrompu pendant l'attente")
                    break
            else:
                logger.debug(
                    f"Transition {phase.value} déjà passée "
                    f"(retard de {-wait_seconds:.0f}s) — exécution immédiate"
                )
            
            # Exécuter le callback
            if callback and self._running:
                logger.info(f"🔄 Transition vers {phase.value}")
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(phase)
                    else:
                        callback(phase)
                except Exception as e:
                    logger.error(
                        f"Erreur lors de la transition vers {phase.value}: {e}",
                        exc_info=True,
                    )
            elif not callback:
                logger.warning(f"Pas de callback pour la transition {phase.value}")
    
    def stop(self):
        """Arrête le planificateur."""
        self._running = False
        if self._stop_event:
            self._stop_event.set()
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


_JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def day_name_fr(day: int) -> str:
    """Retourne le nom français du jour (0=Lundi … 6=Dimanche)."""
    return _JOURS_FR[day % 7]


async def wait_until_new_game(game_day: int, game_hour: int) -> datetime:
    """Attend jusqu'à la prochaine occurrence de ``game_day`` à ``game_hour``h.

    Args:
        game_day:  Jour de la semaine (0=Lundi … 6=Dimanche).
        game_hour: Heure de lancement (0-23).

    Returns:
        Le datetime exact auquel le sleep s'est terminé.
    """
    now = datetime.now()

    # Calculer le nombre de jours d'attente
    days_until = (game_day - now.weekday()) % 7
    target_time = time(game_hour, 0)

    if days_until == 0:
        # Même jour — vérifier si l'heure est passée
        candidate = datetime.combine(now.date(), target_time)
        if now >= candidate:
            # Heure déjà passée → même jour semaine prochaine
            candidate += timedelta(days=7)
    else:
        candidate = datetime.combine(
            now.date() + timedelta(days=days_until), target_time
        )

    wait_time = (candidate - now).total_seconds()
    jour = day_name_fr(game_day)
    logger.info(
        f"Attente jusqu'au {candidate.strftime('%d/%m/%Y à %Hh%M')} "
        f"({jour} {game_hour}h — {wait_time / 3600:.1f} heures)"
    )

    await asyncio.sleep(wait_time)

    return candidate

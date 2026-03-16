"""Agrégateur des mixins de phases."""

from matrix_bot.phase_handlers_night import PhaseNightHandlersMixin
from matrix_bot.phase_handlers_day import PhaseDayHandlersMixin
from matrix_bot.phase_handlers_vote import PhaseVoteHandlersMixin
from matrix_bot.phase_handlers_endgame import PhaseEndgameHandlersMixin


class PhaseHandlersMixin(
    PhaseNightHandlersMixin,
    PhaseDayHandlersMixin,
    PhaseVoteHandlersMixin,
    PhaseEndgameHandlersMixin,
):
    """Regroupe les mixins de gestion de phases."""

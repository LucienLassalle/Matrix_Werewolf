"""Tests du BotController : commandes /statut, /joueurs, annonces de victoire, rappels de vote.

Couvre :
- /statut : phases SETUP, ENDED, en cours, avec maire
- /joueurs : sans partie, inscriptions, en jeu, morts, couronne maire
- Signature _handle_command accepte event_id
- Statistiques de fin de partie (chronologie, survivants, couple, maire)
- Rappels de vote (DM aux non-votants)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, time as dt_time, timedelta

from game.game_manager import GameManager
from game.vote_manager import VoteManager
from models.player import Player
from models.enums import GamePhase, Team, RoleType


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def _make_bot():
    """Crée un WerewolfBot mocké pour tester les méthodes."""
    from matrix_bot.bot_controller import WerewolfBot

    bot = object.__new__(WerewolfBot)
    bot.game_manager = GameManager()
    bot.registered_players = {}
    bot._night_hour = 21
    bot._day_hour = 8
    bot._vote_hour = 19
    bot._game_events = []
    bot._cupidon_wins_with_couple = True

    bot.scheduler = MagicMock()
    bot.scheduler.night_start = dt_time(21, 0)
    bot.scheduler.day_start = dt_time(8, 0)
    bot.scheduler.vote_start = dt_time(19, 0)

    return bot


# ═══════════════════════════════════════════════════════════
#  /statut
# ═══════════════════════════════════════════════════════════

class TestStatutCommand:
    """Tests de la construction du message /statut."""

    def test_statut_setup_phase(self):
        bot = _make_bot()
        bot.registered_players = {"@a:m": "Alice", "@b:m": "Bob"}

        msg = bot._build_statut_message()
        assert "2" in msg
        assert "inscrit" in msg

    def test_statut_ended_phase(self):
        bot = _make_bot()
        bot.game_manager.phase = GamePhase.ENDED

        msg = bot._build_statut_message()
        assert "Aucune partie" in msg

    def test_statut_during_game(self):
        bot = _make_bot()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])
        bot.game_manager.set_phase(GamePhase.VOTE)
        bot.game_manager.day_count = 2

        msg = bot._build_statut_message()
        assert "Vote" in msg or "🗳️" in msg
        assert "Jour" in msg
        assert "Vivants" in msg

    def test_statut_with_mayor(self):
        bot = _make_bot()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])

        mayor = list(bot.game_manager.players.values())[0]
        mayor.is_mayor = True

        msg = bot._build_statut_message()
        assert "Maire" in msg
        assert mayor.display_name in msg


# ═══════════════════════════════════════════════════════════
#  /joueurs
# ═══════════════════════════════════════════════════════════

class TestJoueursCommand:
    """Tests de la construction du message /joueurs."""

    def test_joueurs_no_game(self):
        bot = _make_bot()

        msg = bot._build_joueurs_message()
        assert "Aucun joueur" in msg

    def test_joueurs_with_registered(self):
        bot = _make_bot()
        bot.registered_players = {"@a:m": "Alice", "@b:m": "Bob"}

        msg = bot._build_joueurs_message()
        assert "Alice" in msg
        assert "Bob" in msg

    def test_joueurs_during_game(self):
        bot = _make_bot()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])

        msg = bot._build_joueurs_message()
        assert "Vivants" in msg
        assert "Player0" in msg

    def test_joueurs_with_dead(self):
        bot = _make_bot()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])

        victim = list(bot.game_manager.players.values())[0]
        victim.kill()

        msg = bot._build_joueurs_message()
        assert "Morts" in msg
        assert victim.role.name in msg

    def test_joueurs_shows_mayor_crown(self):
        bot = _make_bot()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])

        mayor = list(bot.game_manager.players.values())[0]
        mayor.is_mayor = True

        msg = bot._build_joueurs_message()
        assert "👑" in msg


# ═══════════════════════════════════════════════════════════
#  _handle_command signature
# ═══════════════════════════════════════════════════════════

class TestBotControllerCommandSignature:
    """Vérifie que _handle_command accepte event_id."""

    def test_handle_command_accepts_event_id(self):
        from matrix_bot.bot_controller import WerewolfBot
        import inspect

        sig = inspect.signature(WerewolfBot._handle_command)
        assert 'event_id' in sig.parameters

        param = sig.parameters['event_id']
        assert param.default is None


# ═══════════════════════════════════════════════════════════
#  Annonce de victoire (statistiques)
# ═══════════════════════════════════════════════════════════

class TestEndGameStats:
    """Tests des statistiques de fin de partie."""

    def _make_bot_with_room(self):
        bot = _make_bot()
        bot.room_manager = MagicMock()
        bot.room_manager.send_to_village = AsyncMock()
        return bot

    @pytest.mark.asyncio
    async def test_victory_announcement_includes_stats(self):
        bot = self._make_bot_with_room()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])
        bot.game_manager.day_count = 3
        bot.game_manager.night_count = 3

        await bot._announce_victory(Team.GENTIL)

        message = bot.room_manager.send_to_village.call_args[0][0]
        assert "Statistiques" in message or "📊" in message
        assert "3 jour" in message
        assert "Survivants" in message

    @pytest.mark.asyncio
    async def test_victory_announcement_includes_events(self):
        bot = self._make_bot_with_room()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])

        bot._game_events.append("Nuit 1 — 💀 **Player0** tué durant la nuit (Villageois)")
        bot._game_events.append("Jour 1 — 🗳️ **Player1** éliminé par le vote (Loup-Garou)")

        await bot._announce_victory(Team.GENTIL)

        message = bot.room_manager.send_to_village.call_args[0][0]
        assert "Chronologie" in message or "📜" in message
        assert "Player0" in message
        assert "Player1" in message

    @pytest.mark.asyncio
    async def test_victory_announcement_shows_mayor_and_couple(self):
        bot = self._make_bot_with_room()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])

        players = list(bot.game_manager.players.values())
        players[0].is_mayor = True
        players[1].lover = players[2]
        players[2].lover = players[1]

        await bot._announce_victory(Team.GENTIL)

        message = bot.room_manager.send_to_village.call_args[0][0]
        assert "👑" in message
        assert "💕" in message

    @pytest.mark.asyncio
    async def test_victory_announcement_no_events(self):
        bot = self._make_bot_with_room()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])
        bot._game_events = []

        await bot._announce_victory(Team.GENTIL)

        message = bot.room_manager.send_to_village.call_args[0][0]
        assert "📜" not in message


# ═══════════════════════════════════════════════════════════
#  Rappels de vote
# ═══════════════════════════════════════════════════════════

class TestVoteReminders:
    """Tests des rappels de vote."""

    def _make_bot_with_client(self):
        bot = _make_bot()
        bot._last_vote_snapshot = {}
        bot.room_manager = MagicMock()
        bot.room_manager.send_to_village = AsyncMock()
        bot.client = MagicMock()
        bot.client.send_dm = AsyncMock()
        return bot

    @pytest.mark.asyncio
    async def test_send_vote_reminder(self):
        bot = self._make_bot_with_client()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])

        await bot._send_vote_reminder("⏰ Test reminder")

        bot.room_manager.send_to_village.assert_called_once()
        message = bot.room_manager.send_to_village.call_args[0][0]
        assert "⏰ Test reminder" in message

    @pytest.mark.asyncio
    async def test_remind_non_voters(self):
        bot = self._make_bot_with_client()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])
        bot.game_manager.set_phase(GamePhase.VOTE)

        p0 = bot.game_manager.players["@p0:m"]
        p1 = bot.game_manager.players["@p1:m"]
        bot.game_manager.vote_manager.add_vote(p0, p1)

        await bot._remind_non_voters()

        dm_calls = bot.client.send_dm.call_args_list
        dm_recipients = [call[0][0] for call in dm_calls]

        assert "@p0:m" not in dm_recipients
        assert len(dm_recipients) >= 1

    @pytest.mark.asyncio
    async def test_remind_non_voters_skips_voters(self):
        bot = self._make_bot_with_client()

        for i in range(6):
            bot.game_manager.add_player(f"Player{i}", f"@p{i}:m")
        bot.game_manager.start_game([f"@p{i}:m" for i in range(6)])
        bot.game_manager.set_phase(GamePhase.VOTE)

        players = list(bot.game_manager.players.values())
        for p in players:
            bot.game_manager.vote_manager.add_vote(p, players[0])

        await bot._remind_non_voters()

        bot.client.send_dm.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

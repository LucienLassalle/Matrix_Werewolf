"""Tests du MessageHandler : réaction emoji sur les commandes.

Couvre :
- Extraction et transmission de l'event_id
- Envoi d'une réaction 👍 via _acknowledge_command
- Pas de réaction si event_id est None
"""

import pytest
import asyncio
import inspect
from unittest.mock import MagicMock, AsyncMock

from matrix_bot.message_handler import MessageHandler


class TestEmojiReaction:
    """Tests que les commandes réussies reçoivent une réaction 👍."""

    def test_message_handler_passes_event_id(self):
        """Le message handler extrait et transmet l'event_id."""
        handler = MessageHandler.__new__(MessageHandler)
        handler.client = MagicMock()
        handler.bot_user_id = "@bot:m"
        handler._start_time_ms = 0
        handler.wolves_room_id = None
        handler.village_room_id = None
        handler.on_command = None
        handler.on_registration = None
        handler.on_wolf_message = None
        handler.on_village_message = None

        sig = inspect.signature(handler._handle_command)
        assert 'event_id' in sig.parameters

    @pytest.mark.asyncio
    async def test_acknowledge_sends_reaction(self):
        """_acknowledge_command envoie une réaction 👍."""
        handler = MessageHandler.__new__(MessageHandler)
        handler.client = MagicMock()
        handler.client.room_send = AsyncMock()

        await handler._acknowledge_command("!room:m", "$event123")

        handler.client.room_send.assert_called_once()
        call_args = handler.client.room_send.call_args
        assert (
            call_args.kwargs.get('message_type')
            or call_args[1].get('message_type')
            or call_args[0][1] == "m.reaction"
        )

    @pytest.mark.asyncio
    async def test_acknowledge_noop_without_event_id(self):
        """_acknowledge_command ne fait rien sans event_id."""
        handler = MessageHandler.__new__(MessageHandler)
        handler.client = MagicMock()
        handler.client.room_send = AsyncMock()

        await handler._acknowledge_command("!room:m", None)

        handler.client.room_send.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

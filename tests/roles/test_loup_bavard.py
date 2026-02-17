"""Tests du rôle Loup-Bavard.

Couvre :
- Attribution d'un mot au début de la nuit
- Détection du mot avec frontières (\b)
- Non-détection d'un sous-mot (faux positif)
- Mort si le mot n'a pas été dit
- Reset du mot chaque nuit
"""

import pytest
from unittest.mock import patch
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


def make_game(*specs) -> GameManager:
    game = GameManager(db_path=":memory:")
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestLoupBavard:
    """Tests du Loup-Bavard."""

    def test_word_assigned_on_night_start(self):
        """Un mot est assigné au début de la nuit."""
        game = make_game(
            ("Bavard", "lb1", RoleType.LOUP_BAVARD),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        bavard = game.players["lb1"]
        assert bavard.role.word_to_say is None

        bavard.role.on_night_start(game)
        assert bavard.role.word_to_say is not None
        assert isinstance(bavard.role.word_to_say, str)

    def test_word_detection_exact(self):
        """Le mot est détecté dans un message."""
        game = make_game(
            ("Bavard", "lb1", RoleType.LOUP_BAVARD),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        bavard = game.players["lb1"]
        bavard.role.word_to_say = "mystère"

        result = bavard.role.check_message_for_word("Je pense que c'est un mystère total")
        assert result is True
        assert bavard.role.has_said_word

    def test_word_detection_case_insensitive(self):
        """La détection est insensible à la casse."""
        game = make_game(
            ("Bavard", "lb1", RoleType.LOUP_BAVARD),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        bavard = game.players["lb1"]
        bavard.role.word_to_say = "village"

        assert bavard.role.check_message_for_word("Le VILLAGE est grand")

    def test_no_false_positive_substring(self):
        """Le mot 'chat' ne doit pas matcher dans 'achat'."""
        game = make_game(
            ("Bavard", "lb1", RoleType.LOUP_BAVARD),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        bavard = game.players["lb1"]
        bavard.role.word_to_say = "chat"

        assert not bavard.role.check_message_for_word("J'ai fait un achat")
        assert not bavard.role.has_said_word

    def test_word_at_boundaries(self):
        """Le mot est détecté en début et fin de message."""
        game = make_game(
            ("Bavard", "lb1", RoleType.LOUP_BAVARD),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        bavard = game.players["lb1"]
        bavard.role.word_to_say = "chat"

        assert bavard.role.check_message_for_word("chat")
        bavard.role.has_said_word = False  # Reset

        assert bavard.role.check_message_for_word("mon chat est gentil")
        bavard.role.has_said_word = False

        assert bavard.role.check_message_for_word("j'aime le chat")

    def test_death_if_word_not_said(self):
        """Le Loup-Bavard meurt si le mot n'a pas été dit avant la nuit suivante."""
        game = make_game(
            ("Bavard", "lb1", RoleType.LOUP_BAVARD),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        bavard = game.players["lb1"]
        # Première nuit : initialise le mot
        bavard.role.on_night_start(game)
        assert bavard.role.word_to_say is not None
        # Le mot n'est PAS dit (has_said_word reste False)

        # Deuxième nuit : vérification → mort
        bavard.role.on_night_start(game)
        # Le joueur devrait être marqué pour tuer
        assert bavard in game._pending_kills

    def test_no_death_if_word_said(self):
        """Le Loup-Bavard survit si le mot a été dit."""
        game = make_game(
            ("Bavard", "lb1", RoleType.LOUP_BAVARD),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        bavard = game.players["lb1"]
        bavard.role.on_night_start(game)

        # Dire le mot
        bavard.role.check_message_for_word(f"Je dis {bavard.role.word_to_say} dans ma phrase")

        # Nuit suivante : pas de mort
        bavard.role.on_night_start(game)
        assert bavard not in game._pending_kills

    def test_new_word_each_night(self):
        """Un nouveau mot est assigné chaque nuit."""
        game = make_game(
            ("Bavard", "lb1", RoleType.LOUP_BAVARD),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        bavard = game.players["lb1"]
        words = set()
        # On fait plusieurs nuits pour vérifier que le mot change (probabilistique)
        for _ in range(10):
            bavard.role.has_said_word = True  # Avoid death
            bavard.role.on_night_start(game)
            words.add(bavard.role.word_to_say)
        # Avec 10 itérations, on devrait avoir plus d'un mot unique
        assert len(words) >= 2

    def test_team(self):
        role = RoleFactory.create_role(RoleType.LOUP_BAVARD)
        assert role.team == Team.MECHANT

    def test_can_vote_with_wolves(self):
        role = RoleFactory.create_role(RoleType.LOUP_BAVARD)
        assert role.can_vote_with_wolves()

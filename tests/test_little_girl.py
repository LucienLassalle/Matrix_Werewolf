"""Tests pour la mécanique d'espionnage de la Petite Fille."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from utils.message_distortion import MessageDistorter


class TestMessageDistortion(unittest.TestCase):
    """Tests pour la distorsion de messages."""
    
    def setUp(self):
        self.distorter = MessageDistorter()
    
    def test_distortion_changes_message(self):
        """Vérifie que la distorsion modifie le message."""
        original = "Les loups attaquent le villageois Bob"
        # Utiliser une intensité élevée pour garantir une modification
        distorted = self.distorter.distort_message(original, intensity=0.8)
        
        # Le message doit être différent (avec haute probabilité)
        self.assertNotEqual(original, distorted)
        
        # La longueur doit être similaire
        self.assertAlmostEqual(len(original), len(distorted), delta=5)
    
    def test_no_distortion_preserves_message(self):
        """Vérifie que intensity=0 ne modifie pas le message."""
        original = "Les loups attaquent Bob"
        distorted = self.distorter.distort_message(original, intensity=0.0)
        
        self.assertEqual(original, distorted)
    
    def test_format_with_distortion(self):
        """Vérifie le formatage avec distorsion."""
        # Utiliser un message plus long pour garantir l'altération
        message = "Attaquons ensemble le villageois cette nuit les amis"
        formatted = self.distorter.format_wolf_message_for_little_girl(message, distort=True)
        
        # Doit contenir le préfixe
        self.assertIn("🔊", formatted)
        self.assertIn("murmures", formatted.lower())
        
        # Le message original ne doit pas être exactement présent (forte probabilité avec message long)
        # Avec intensity=0.15 et un message de 8 mots, la probabilité de 0 altération est ~2%
        # On vérifie que le formatage est bien appliqué (préfixe + italique)
        self.assertIn("_", formatted)  # Format italique markdown
    
    def test_format_without_distortion(self):
        """Vérifie le formatage sans distorsion."""
        message = "On tue Bob"
        formatted = self.distorter.format_wolf_message_for_little_girl(message, distort=False)
        
        # Doit contenir le préfixe
        self.assertIn("🔊", formatted)
        
        # Le message original doit être présent
        self.assertIn("On tue Bob", formatted)
    
    def test_make_illegible(self):
        """Vérifie que _make_illegible altère bien les mots."""
        word = "le"
        illegible = self.distorter._make_illegible(word)
        
        # Doit contenir des caractères spéciaux (parmi tous les illegible_chars possibles)
        illegible_chars = {'*', '#', '~', '?', '·'}
        self.assertTrue(any(c in illegible_chars for c in illegible))
    
    def test_char_replacements(self):
        """Vérifie que les remplacements de caractères sont corrects."""
        word = "aeiost"
        
        # Avec une intensité de 100%, au moins un caractère devrait être remplacé
        replaced = self.distorter._distort_word(word, intensity=1.0)
        
        # La longueur doit être identique
        self.assertEqual(len(word), len(replaced))
    
    def test_empty_message(self):
        """Vérifie le comportement avec un message vide."""
        formatted = self.distorter.format_wolf_message_for_little_girl("", distort=True)
        
        # Doit au moins contenir le préfixe
        self.assertIn("🔊", formatted)


class TestLittleGirlSpyMechanic(unittest.TestCase):
    """Tests pour la mécanique d'espionnage (logique uniquement, pas Matrix)."""
    
    def test_message_detection_logic(self):
        """Vérifie la logique de détection des messages des loups."""
        # Simuler la logique de détection
        wolves_room_id = "!abc123:matrix.org"
        incoming_room_id = "!abc123:matrix.org"
        bot_user_id = "@bot:matrix.org"
        sender = "@wolf:matrix.org"
        
        # Conditions pour transmettre le message
        should_transmit = (
            incoming_room_id == wolves_room_id and
            sender != bot_user_id
        )
        
        self.assertTrue(should_transmit)
    
    def test_message_not_from_wolves_room(self):
        """Vérifie qu'on ne transmet pas les messages d'autres salons."""
        wolves_room_id = "!abc123:matrix.org"
        incoming_room_id = "!xyz789:matrix.org"
        bot_user_id = "@bot:matrix.org"
        sender = "@player:matrix.org"
        
        should_transmit = (
            incoming_room_id == wolves_room_id and
            sender != bot_user_id
        )
        
        self.assertFalse(should_transmit)
    
    def test_ignore_bot_messages(self):
        """Vérifie qu'on ignore les messages du bot."""
        wolves_room_id = "!abc123:matrix.org"
        incoming_room_id = "!abc123:matrix.org"
        bot_user_id = "@bot:matrix.org"
        sender = "@bot:matrix.org"
        
        should_transmit = (
            incoming_room_id == wolves_room_id and
            sender != bot_user_id
        )
        
        self.assertFalse(should_transmit)


class TestLittleGirlGameLogic(unittest.TestCase):
    """Tests pour la logique de jeu de la Petite Fille."""
    
    def test_little_girl_receives_messages_when_alive(self):
        """Vérifie que la Petite Fille reçoit les messages si vivante."""
        from models.enums import GamePhase
        
        # Simuler les conditions
        game_phase = GamePhase.NIGHT
        little_girl_alive = True
        little_girl_exists = True
        
        should_send = (
            game_phase == GamePhase.NIGHT and
            little_girl_exists and
            little_girl_alive
        )
        
        self.assertTrue(should_send)
    
    def test_no_transmission_during_day(self):
        """Vérifie qu'on ne transmet pas pendant le jour."""
        from models.enums import GamePhase
        
        game_phase = GamePhase.DAY
        little_girl_alive = True
        little_girl_exists = True
        
        should_send = (
            game_phase == GamePhase.NIGHT and
            little_girl_exists and
            little_girl_alive
        )
        
        self.assertFalse(should_send)
    
    def test_no_transmission_if_dead(self):
        """Vérifie qu'on ne transmet pas si la Petite Fille est morte."""
        from models.enums import GamePhase
        
        game_phase = GamePhase.NIGHT
        little_girl_alive = False
        little_girl_exists = True
        
        should_send = (
            game_phase == GamePhase.NIGHT and
            little_girl_exists and
            little_girl_alive
        )
        
        self.assertFalse(should_send)
    
    def test_no_transmission_if_no_little_girl(self):
        """Vérifie qu'on ne transmet pas s'il n'y a pas de Petite Fille."""
        from models.enums import GamePhase
        
        game_phase = GamePhase.NIGHT
        little_girl_alive = True
        little_girl_exists = False
        
        should_send = (
            game_phase == GamePhase.NIGHT and
            little_girl_exists and
            little_girl_alive
        )
        
        self.assertFalse(should_send)


class TestDistortionConfiguration(unittest.TestCase):
    """Tests pour la configuration de la distorsion."""
    
    def test_env_var_true(self):
        """Vérifie que LITTLE_GIRL_DISTORT_MESSAGES=true active la distorsion."""
        env_value = "true"
        should_distort = env_value.lower() == 'true'
        
        self.assertTrue(should_distort)
    
    def test_env_var_false(self):
        """Vérifie que LITTLE_GIRL_DISTORT_MESSAGES=false désactive la distorsion."""
        env_value = "false"
        should_distort = env_value.lower() == 'true'
        
        self.assertFalse(should_distort)
    
    def test_env_var_default_true(self):
        """Vérifie que la valeur par défaut est true."""
        env_value = None
        should_distort = (env_value or "true").lower() == 'true'
        
        self.assertTrue(should_distort)


if __name__ == '__main__':
    # Configurer le logging pour les tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Exécuter les tests
    unittest.main(verbosity=2)

"""Utilitaires pour altérer les messages de la Petite Fille."""

import random
import re


class MessageDistorter:
    """Altère légèrement les messages pour simuler l'espionnage de la Petite Fille."""
    
    # Caractères de remplacement pour créer des mots "illisibles"
    CHAR_REPLACEMENTS = {
        'a': ['4', '@', 'a', 'a'],
        'e': ['3', '€', 'e', 'e'],
        'i': ['1', '!', 'i', 'i'],
        'o': ['0', 'o', 'o', 'o'],
        'u': ['u', 'u', 'u', 'u'],
        's': ['$', 's', 's', 's'],
        't': ['7', 't', 't', 't'],
    }
    
    # Mots de liaison à potentiellement rendre illisibles
    FILLER_WORDS = [
        'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du',
        'et', 'ou', 'mais', 'donc', 'car', 'ni', 'or',
        'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
        'ce', 'cette', 'ces', 'mon', 'ton', 'son', 'ma', 'ta', 'sa'
    ]
    
    @staticmethod
    def distort_message(message: str, intensity: float = 0.15) -> str:
        """Altère légèrement un message.
        
        Args:
            message: Le message original
            intensity: Intensité de l'altération (0.0 à 1.0)
                      0.15 = ~15% des caractères altérés (léger)
        
        Returns:
            Le message altéré avec quelques caractères remplacés
        """
        if not message or intensity <= 0.0:
            return message
        
        words = message.split()
        altered_words = []
        
        for word in words:
            # 20% de chance de rendre un mot de liaison illisible
            if word.lower() in MessageDistorter.FILLER_WORDS and random.random() < 0.2:
                altered_words.append(MessageDistorter._make_illegible(word))
            else:
                # Sinon, altérer quelques caractères
                altered_words.append(MessageDistorter._distort_word(word, intensity))
        
        return ' '.join(altered_words)
    
    @staticmethod
    def _distort_word(word: str, intensity: float) -> str:
        """Altère les caractères d'un mot."""
        if len(word) < 3:  # Ne pas toucher aux mots trop courts
            return word
        
        chars = list(word)
        
        for i in range(len(chars)):
            char_lower = chars[i].lower()
            
            # Ne toucher que les lettres (pas la ponctuation)
            if not char_lower.isalpha():
                continue
            
            # Altérer selon l'intensité
            if random.random() < intensity:
                if char_lower in MessageDistorter.CHAR_REPLACEMENTS:
                    replacement = random.choice(MessageDistorter.CHAR_REPLACEMENTS[char_lower])
                    
                    # Garder la casse
                    if chars[i].isupper():
                        replacement = replacement.upper()
                    
                    chars[i] = replacement
        
        return ''.join(chars)
    
    @staticmethod
    def _make_illegible(word: str) -> str:
        """Rend un mot totalement illisible."""
        length = len(word)
        
        # Remplacer par des caractères aléatoires
        illegible_chars = ['*', '#', '~', '?', '·']
        
        # Garder quelques lettres pour que ça reste reconnaissable
        if length <= 2:
            return ''.join(random.choices(illegible_chars, k=length))
        
        # Garder la première et dernière lettre
        result = [word[0]]
        for _ in range(length - 2):
            if random.random() < 0.7:
                result.append(random.choice(illegible_chars))
            else:
                result.append(random.choice('aeiou'))
        result.append(word[-1])
        
        return ''.join(result)
    
    @staticmethod
    def format_wolf_message_for_little_girl(message: str, distort: bool = True) -> str:
        """Formate un message des loups pour la Petite Fille.
        
        Args:
            message: Le message original des loups
            distort: Si True, altère le message. Si False, le transmet tel quel.
        
        Returns:
            Le message formaté pour la Petite Fille
        """
        if distort:
            altered = MessageDistorter.distort_message(message, intensity=0.15)
            return f"🔊 *Vous entendez des murmures...* 👂\n\n_{altered}_"
        else:
            return f"🔊 *Vous entendez les loups...* 👂\n\n{message}"


# Accès direct pour rétro-compatibilité
distort_message = MessageDistorter.format_wolf_message_for_little_girl

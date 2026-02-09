"""Rôle Loup-Bavard."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING, List
from pathlib import Path
import random

if TYPE_CHECKING:
    from game.game_manager import GameManager


# Charger le dictionnaire au chargement du module
_DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "mots_francais.txt"

def _load_word_list() -> List[str]:
    """Charge la liste de mots depuis le fichier dictionnaire."""
    try:
        text = _DICT_PATH.read_text(encoding="utf-8")
        words = [w.strip() for w in text.splitlines() if w.strip()]
        if words:
            return words
    except FileNotFoundError:
        pass
    # Fallback si le fichier est absent
    return [
        "village", "mystère", "trahison", "alliance", "enquête",
        "justice", "vengeance", "protection", "chapeau", "fromage",
        "château", "trompette", "montagne", "papillon", "fontaine"
    ]

_WORD_LIST: List[str] = _load_word_list()


class LoupBavard(Role):
    """Loup-Bavard - Doit prononcer un mot imposé durant la journée."""
    
    def __init__(self):
        super().__init__(RoleType.LOUP_BAVARD, Team.MECHANT)
        self.word_to_say: str | None = None
        self.has_said_word = False
    
    def get_description(self) -> str:
        return "Loup-Bavard - Chaque nuit, on vous donne un mot que vous DEVEZ prononcer durant la journée, sinon vous mourrez."
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_vote_with_wolves(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return action_type == ActionType.VOTE and self.player and self.player.is_alive
    
    def on_night_start(self, game: 'GameManager'):
        """Vérifie le mot précédent puis assigne un nouveau mot."""
        # Vérifier si le mot de la journée précédente a été dit
        if self.word_to_say and not self.has_said_word:
            if self.player and self.player.is_alive:
                game.log(f"{self.player.pseudo} n'a pas dit le mot imposé et meurt !")
                # Tuer via le game manager (mute, retrait loups, notifications, amoureux)
                game.kill_player(self.player, killed_during_day=False)
        
        # Assigner un nouveau mot pour la prochaine journée
        self.word_to_say = random.choice(_WORD_LIST)
        self.has_said_word = False
    
    def check_message_for_word(self, message: str) -> bool:
        """Vérifie si le message contient le mot imposé."""
        if self.word_to_say and self.word_to_say.lower() in message.lower():
            self.has_said_word = True
            return True
        return False
    
    def on_day_start(self, game: 'GameManager'):
        """Callback du début de jour."""
        pass

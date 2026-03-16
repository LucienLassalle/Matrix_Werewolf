"""Helpers pour tests de maire et Cupidon."""

from game.game_manager import GameManager
from models.enums import GamePhase
from roles import RoleFactory


def make_game(*specs) -> GameManager:
    """Cree une partie avec les joueurs/roles donnes.

    specs: tuples (pseudo, user_id, RoleType)
    Retourne le GameManager en phase NIGHT.
    """
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game

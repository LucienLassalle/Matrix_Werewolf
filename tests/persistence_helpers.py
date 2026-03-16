"""Helpers pour tests de persistance."""

from game.game_manager import GameManager
from models.enums import RoleType


def make_game(db_path: str, n_players: int = 6, role_config=None) -> GameManager:
    """Cree un GameManager avec une partie demarree."""
    gm = GameManager(db_path=db_path)

    if role_config is None:
        role_config = {
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: max(0, n_players - 4),
        }

    ids = [f"@player{i}:server.com" for i in range(n_players)]
    for uid in ids:
        pseudo = uid.split(":")[0].lstrip("@")
        gm.add_player(pseudo, uid)
        gm.players[uid].display_name = f"Display_{pseudo}"

    gm.set_roles(role_config)
    result = gm.start_game(immediate_night=True)
    assert result["success"], f"Echec start_game: {result.get('message')}"
    return gm


def load_into_new_gm(db_path: str) -> GameManager:
    """Ouvre une nouvelle instance de GameManager et restaure l'etat."""
    gm2 = GameManager(db_path=db_path)
    ok = gm2.load_state()
    assert ok, "load_state() a retourné False"
    return gm2

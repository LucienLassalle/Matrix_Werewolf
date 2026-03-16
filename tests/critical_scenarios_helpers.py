"""Helpers pour scenarios critiques."""

from game.game_manager import GameManager
from models.enums import RoleType
from roles import RoleFactory


def setup_game(n_players=5, roles=None):
    """Cree une partie prete a jouer avec des roles forces."""
    game = GameManager(db_path=":memory:")

    if roles:
        roles = dict(roles)
        mandatory = {RoleType.SORCIERE: 1, RoleType.VOYANTE: 1, RoleType.CHASSEUR: 1}
        for rt, count in mandatory.items():
            if rt not in roles:
                roles[rt] = count
        total_roles = sum(roles.values())
        if total_roles > n_players and RoleType.VILLAGEOIS in roles:
            overflow = total_roles - n_players
            roles[RoleType.VILLAGEOIS] = max(0, roles[RoleType.VILLAGEOIS] - overflow)
        total_roles = sum(roles.values())
        if total_roles > n_players:
            n_players = total_roles

    for i in range(n_players):
        game.add_player(f"P{i}", f"@p{i}:test")

    if roles:
        game.set_roles(roles)

    result = game.start_game()
    assert result["success"], f"Impossible de démarrer : {result.get('message')}"
    return game


def force_roles(game, role_map: dict):
    """Force les roles apres start_game."""
    for uid, rt in role_map.items():
        player = game.get_player(uid)
        assert player, f"Joueur {uid} introuvable"
        role = RoleFactory.create_role(rt)
        role.assign_to_player(player)
        game.vote_manager.register_player(player)

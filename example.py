"""Exemple d'utilisation du backend Loup-Garou."""

from game.game_manager import GameManager
from models.enums import RoleType, Phase
from commands.command_handler import CommandHandler


def main():
    """Exemple de partie simple."""
    print("=== Démonstration du backend Loup-Garou ===\n")
    
    # Créer une partie
    game = GameManager()
    print("✓ Partie créée")
    
    # Ajouter des joueurs
    players_data = [
        ("Alice", "user_1"),
        ("Bob", "user_2"),
        ("Charlie", "user_3"),
        ("Diana", "user_4"),
        ("Eve", "user_5"),
        ("Frank", "user_6"),
    ]
    
    for pseudo, user_id in players_data:
        result = game.add_player(pseudo, user_id)
        print(f"✓ {result['message']}")
    
    print(f"\n{len(game.players)} joueurs dans la partie\n")
    
    # Configurer les rôles
    role_config = {
        RoleType.LOUP_GAROU: 2,
        RoleType.VOYANTE: 1,
        RoleType.CHASSEUR: 1,
        RoleType.SORCIERE: 1,
        RoleType.VILLAGEOIS: 1,
    }
    
    result = game.set_roles(role_config)
    print(f"✓ {result['message']}\n")
    
    # Démarrer la partie
    result = game.start_game()
    print(f"✓ {result['message']}\n")
    
    # Afficher les rôles (normalement cachés)
    print("=== Rôles distribués ===")
    for player in game.players:
        print(f"- {player.pseudo}: {player.role.role_type.value} ({player.get_team().value})")
    print()
    
    # Créer le gestionnaire de commandes
    command_handler = CommandHandler(game)
    
    # Simulation d'une nuit
    print(f"=== Phase: {game.phase.value} ===\n")
    
    # La voyante regarde quelqu'un
    voyante = next((p for p in game.players if p.role.role_type == RoleType.VOYANTE), None)
    if voyante:
        target = game.players[0] if game.players[0] != voyante else game.players[1]
        result = command_handler.execute_command(voyante.user_id, "voyante", [target.pseudo])
        print(f"Voyante ({voyante.pseudo}): {result['message']}")
    
    # Les loups votent
    wolves = game.get_living_wolves()
    if wolves:
        target = next((p for p in game.players if p.get_team().value != "MECHANT"), None)
        if target:
            for wolf in wolves:
                result = command_handler.execute_command(wolf.user_id, "vote", [target.pseudo])
                print(f"Loup ({wolf.pseudo}): {result['message']}")
    
    print("\n=== Fin de la nuit ===")
    result = game.end_night()
    
    if result["results"]["deaths"]:
        for dead in result["results"]["deaths"]:
            print(f"💀 {dead.pseudo} est mort.e cette nuit")
    else:
        print("✓ Personne n'est mort.e cette nuit")
    
    print(f"\n=== Phase: {game.phase.value} ===")
    
    # Démarrer le vote
    result = game.start_vote_phase()
    print(f"✓ {result['message']}\n")
    
    # Les joueurs votent
    living = game.get_living_players()
    if len(living) > 1:
        # Tout le monde vote pour le premier joueur vivant qui n'est pas soi-même
        vote_target = living[0]
        for player in living:
            if player != vote_target:
                result = command_handler.execute_command(player.user_id, "vote", [vote_target.pseudo])
                print(f"{player.pseudo} vote : {result['message']}")
    
    print("\n" + game.vote_manager.get_vote_summary())
    
    # Terminer le vote
    print("\n=== Fin du vote ===")
    result = game.end_vote_phase()
    
    if result.get("eliminated"):
        print(f"💀 {result['eliminated'].pseudo} a été éliminé.e")
    
    # Afficher l'état du jeu
    print("\n=== État de la partie ===")
    state = game.get_game_state()
    print(f"Phase: {state['phase']}")
    print(f"Jour: {state['day']}, Nuit: {state['night']}")
    print(f"Joueurs vivants: {state['living_players']}/{state['total_players']}")
    print(f"Loups vivants: {state['wolves_alive']}")
    
    print("\n=== Joueurs ===")
    for player_info in state['players']:
        status = "Vivant.e" if player_info['is_alive'] else "Mort.e"
        mayor = " 👑" if player_info['is_mayor'] else ""
        print(f"- {player_info['pseudo']}: {player_info['role']} ({status}){mayor}")
    
    # Vérifier condition de victoire
    winner = game.check_win_condition()
    if winner:
        print(f"\n🏆 {winner}")
    else:
        print("\n⏳ La partie continue...")
    
    print("\n=== Log de la partie ===")
    for log in game.game_log[-10:]:
        print(f"  {log}")


if __name__ == "__main__":
    main()

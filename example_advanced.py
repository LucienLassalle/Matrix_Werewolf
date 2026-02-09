"""Exemple avancé avec plus de rôles et de fonctionnalités."""

from game.game_manager import GameManager
from models.enums import RoleType
from commands.command_handler import CommandHandler
from utils.helpers import format_game_summary, format_player_list


def advanced_example():
    """Exemple avec plus de joueurs et de rôles avancés."""
    print("=== Partie Avancée Loup-Garou ===\n")
    
    # Créer la partie
    game = GameManager()
    
    # Ajouter 10 joueurs
    players_data = [
        ("Alice", "user_1"),
        ("Bob", "user_2"),
        ("Charlie", "user_3"),
        ("Diana", "user_4"),
        ("Eve", "user_5"),
        ("Frank", "user_6"),
        ("Grace", "user_7"),
        ("Henry", "user_8"),
        ("Iris", "user_9"),
        ("Jack", "user_10"),
    ]
    
    for pseudo, user_id in players_data:
        game.add_player(pseudo, user_id)
    
    print(f"✓ {len(game.players)} joueurs ajoutés\n")
    
    # Configuration avancée des rôles
    role_config = {
        RoleType.LOUP_GAROU: 2,
        RoleType.LOUP_BLANC: 1,
        RoleType.VOYANTE: 1,
        RoleType.CHASSEUR: 1,
        RoleType.SORCIERE: 1,
        RoleType.CUPIDON: 1,
        RoleType.GARDE: 1,
        RoleType.IDIOT: 1,
        RoleType.VILLAGEOIS: 1,
    }
    
    game.set_roles(role_config)
    print("✓ Rôles configurés:")
    for role, count in role_config.items():
        print(f"  - {role.value}: {count}")
    print()
    
    # Démarrer la partie
    game.start_game()
    print("✓ Partie démarrée!\n")
    
    # Afficher les rôles (normalement secret)
    print("=== RÔLES SECRETS (pour démo) ===")
    print(format_player_list(game.players, show_roles=True))
    print()
    
    command_handler = CommandHandler(game)
    
    # === PREMIÈRE NUIT ===
    print(f"{'='*50}")
    print(f"  NUIT {game.night_count}")
    print(f"{'='*50}\n")
    
    # Cupidon marie deux personnes
    cupidon = next((p for p in game.players if p.role.role_type == RoleType.CUPIDON), None)
    if cupidon:
        # Marie les deux premiers joueurs
        target1, target2 = game.players[0], game.players[1]
        result = command_handler.execute_command(
            cupidon.user_id, 
            "cupidon", 
            [target1.pseudo, target2.pseudo]
        )
        print(f"💕 Cupidon: {result['message']}\n")
    
    # Voyante voit un rôle
    voyante = next((p for p in game.players if p.role.role_type == RoleType.VOYANTE), None)
    if voyante:
        suspect = next((p for p in game.players if p != voyante), None)
        result = command_handler.execute_command(
            voyante.user_id,
            "voyante",
            [suspect.pseudo]
        )
        print(f"🔮 Voyante: {result['message']}\n")
    
    # Garde protège quelqu'un
    garde = next((p for p in game.players if p.role.role_type == RoleType.GARDE), None)
    if garde:
        protected = game.players[0]
        result = command_handler.execute_command(
            garde.user_id,
            "garde",
            [protected.pseudo]
        )
        print(f"🛡️  Garde: {result['message']}\n")
    
    # Les loups votent
    wolves = game.get_living_wolves()
    if wolves:
        # Choisir une cible (premier non-loup)
        target = next((p for p in game.players if p not in wolves), None)
        if target:
            print("🐺 Les loups se réunissent...")
            for wolf in wolves:
                result = command_handler.execute_command(
                    wolf.user_id,
                    "vote",
                    [target.pseudo]
                )
                print(f"   {wolf.pseudo}: {result['message']}")
            print()
    
    # La sorcière agit
    sorciere = next((p for p in game.players if p.role.role_type == RoleType.SORCIERE), None)
    if sorciere:
        # Exemple: sauve la victime
        wolf_target = game.vote_manager.get_most_voted(is_wolf_vote=True)
        if wolf_target:
            result = command_handler.execute_command(
                sorciere.user_id,
                "sorciere-sauve",
                [wolf_target.pseudo]
            )
            print(f"🧪 Sorcière: {result['message']}\n")
    
    # Fin de la nuit
    print("🌅 Fin de la nuit...\n")
    result = game.end_night()
    
    if result["results"]["deaths"]:
        print("💀 Morts cette nuit:")
        for dead in result["results"]["deaths"]:
            print(f"   - {dead.pseudo}")
    else:
        print("✨ Personne n'est mort cette nuit!")
    print()
    
    # === PREMIER JOUR ===
    print(f"{'='*50}")
    print(f"  JOUR {game.day_count}")
    print(f"{'='*50}\n")
    
    print("☀️  Le village se réveille...\n")
    
    # Afficher les joueurs vivants
    print("=== Joueurs vivants ===")
    living = game.get_living_players()
    print(format_player_list(living))
    print(f"\nTotal: {len(living)} joueurs\n")
    
    # Phase de discussion (simulée)
    print("💬 Phase de discussion...\n")
    
    # Démarrer le vote
    game.start_vote_phase()
    print("🗳️  Phase de vote commencée!\n")
    
    # Les joueurs votent
    if len(living) > 1:
        # Simuler des votes répartis
        vote_target = living[0]
        print(f"Les joueurs votent pour {vote_target.pseudo}:\n")
        
        for player in living:
            if player != vote_target and player.can_vote:
                result = command_handler.execute_command(
                    player.user_id,
                    "vote",
                    [vote_target.pseudo]
                )
                if result["success"]:
                    vote_weight = "2 voix 👑" if player.is_mayor else "1 voix"
                    print(f"   {player.pseudo}: {vote_weight}")
    
    print("\n" + game.vote_manager.get_vote_summary())
    
    # Fin du vote
    print("\n📊 Dépouillement des votes...\n")
    result = game.end_vote_phase()
    
    if result.get("eliminated"):
        eliminated = result["eliminated"]
        print(f"💀 {eliminated.pseudo} a été éliminé par le village")
        if eliminated.role:
            print(f"   Rôle: {eliminated.role.role_type.value}")
    else:
        print("🤝 Aucune élimination (égalité)")
    print()
    
    # Afficher le résumé
    print(format_game_summary(game))
    
    # Vérifier condition de victoire
    winner = game.check_win_condition()
    if winner:
        print(f"\n{'='*50}")
        print(f"🏆 {winner}")
        print(f"{'='*50}\n")
    else:
        print("⏳ La partie continue...\n")
    
    # Afficher les 10 dernières entrées du log
    print("=== Dernières actions ===")
    for log_entry in game.game_log[-10:]:
        print(f"  📝 {log_entry}")
    print()
    
    # État final
    print("=== ÉTAT FINAL ===")
    print(format_player_list(game.players, show_roles=True))
    print()


def couple_example():
    """Exemple avec couple d'amoureux d'équipes différentes."""
    print("\n" + "="*60)
    print("  EXEMPLE: VICTOIRE DU COUPLE")
    print("="*60 + "\n")
    
    game = GameManager()
    
    # Ajouter 4 joueurs
    game.add_player("Alice", "user_1")
    game.add_player("Bob", "user_2")
    game.add_player("Charlie", "user_3")
    game.add_player("Diana", "user_4")
    
    # 1 loup, 1 cupidon, 2 villageois
    game.set_roles({
        RoleType.LOUP_GAROU: 1,
        RoleType.CUPIDON: 1,
        RoleType.VILLAGEOIS: 2
    })
    
    game.start_game()
    
    print("=== Configuration ===")
    print(format_player_list(game.players, show_roles=True))
    print()
    
    # Cupidon marie un loup et un villageois
    cupidon = next((p for p in game.players if p.role.role_type == RoleType.CUPIDON), None)
    loup = next((p for p in game.players if p.role.role_type == RoleType.LOUP_GAROU), None)
    villageois = next((p for p in game.players if p.role.role_type == RoleType.VILLAGEOIS), None)
    
    if cupidon and loup and villageois:
        command_handler = CommandHandler(game)
        result = command_handler.execute_command(
            cupidon.user_id,
            "cupidon",
            [loup.pseudo, villageois.pseudo]
        )
        print(f"💕 {result['message']}\n")
        
        # Tuer tous les autres joueurs
        for player in game.players:
            if player not in [loup, villageois]:
                player.kill()
        
        print("=== Résultat ===")
        print(format_player_list(game.players, show_roles=True))
        print()
        
        winner = game.check_win_condition()
        if winner:
            print(f"🏆 {winner}\n")


if __name__ == "__main__":
    # Exemple principal
    advanced_example()
    
    # Exemple du couple
    couple_example()
    
    print("\n✅ Exemples terminés!")
    print("📖 Consultez API.md pour plus d'informations")

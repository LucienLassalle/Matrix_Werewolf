# Werewolf Matrix Backend

Backend complet pour le jeu du Loup-Garou, conçu pour être utilisé avec un bot Matrix.

## 🎯 Fonctionnalités

- ✅ **24 rôles implémentés** (tous les rôles du todo.txt)
- ✅ Gestion complète des phases (Nuit, Jour, Vote)
- ✅ Système de votes et d'actions
- ✅ Conditions de victoire multiples
- ✅ Gestionnaire de commandes
- ✅ Architecture modulaire et extensible
- ✅ Tests unitaires complets

## 📁 Architecture

```
Werewolf-Matrix/
├── models/          # Modèles de données (Player, Role, Enums)
├── roles/           # Implémentation de tous les rôles
├── game/            # Logique du jeu (GameManager, VoteManager, ActionManager)
├── commands/        # Gestionnaire de commandes
├── utils/           # Utilitaires (helpers, formatters)
├── tests/           # Tests unitaires
├── example.py       # Exemple d'utilisation
└── API.md          # Documentation complète de l'API
```

## 🚀 Installation

```bash
# Cloner le repository
git clone <repo_url>
cd Werewolf-Matrix

# Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt
```

## 💻 Utilisation rapide

```python
from game.game_manager import GameManager
from models.enums import RoleType
from commands.command_handler import CommandHandler

# 1. Créer une partie
game = GameManager()

# 2. Ajouter des joueurs
game.add_player("Alice", "user_id_1")
game.add_player("Bob", "user_id_2")
game.add_player("Charlie", "user_id_3")
game.add_player("Diana", "user_id_4")

# 3. Configurer les rôles
game.set_roles({
    RoleType.LOUP_GAROU: 1,
    RoleType.VOYANTE: 1,
    RoleType.VILLAGEOIS: 2
})

# 4. Démarrer la partie
result = game.start_game()
print(result["message"])

# 5. Utiliser les commandes
command_handler = CommandHandler(game)
result = command_handler.execute_command(
    user_id="user_id_1",
    command="vote",
    args=["Bob"]
)
print(result["message"])

# 6. Passer d'une phase à l'autre
game.end_night()
game.start_vote_phase()
game.end_vote_phase()
```

## 🎭 Rôles disponibles

### Rôles de base
- **Villageois** - Simple villageois
- **Loup-Garou** - Vote pour tuer chaque nuit
- **Voyante** - Voit les rôles
- **Chasseur** - Tue quelqu'un en mourant
- **Sorcière** - 2 potions (vie et mort)
- **Cupidon** - Marie 2 personnes
- **Petite Fille** - Observe les loups
- **Voleur** - Échange ou tire des rôles

### Loups avancés
- **Loup-Voyant** - Voit les rôles
- **Loup-Blanc** - Tue seul, gagne seul
- **Loup-Noir** - Convertit en loup
- **Loup-Bavard** - Doit dire un mot imposé

### Villageois avancés
- **Montreur d'Ours** - Son ours grogne près des loups
- **Corbeau** - Ajoute 2 votes
- **Idiot** - Gracié une fois
- **Enfant Sauvage** - Devient loup si mentor meurt
- **Médium** - Parle avec les morts
- **Garde** - Protège quelqu'un
- **Voyante d'Aura** - Voit l'équipe

### Rôles spéciaux
- **Mercenaire** - Doit faire tuer une cible
- **Mentaliste** - Connaît l'issue du vote
- **Dictateur** - Force un vote
- **Maire** - Vote double

## 🎮 Commandes disponibles

| Commande | Utilisation | Description |
|----------|-------------|-------------|
| `/vote {pseudo}` | Loups, Village | Vote pour éliminer |
| `/tuer {pseudo}` | Chasseur, Dictateur, Loup Blanc | Tue quelqu'un |
| `/cupidon {pseudo1} {pseudo2}` | Cupidon | Marie deux personnes |
| `/sorciere-sauve {pseudo}` | Sorcière | Sauve la victime |
| `/sorciere-tue {pseudo}` | Sorcière | Empoisonne |
| `/voleur-echange {pseudo}` | Voleur | Échange de rôle |
| `/voleur-tirer` | Voleur | Tire 2 rôles |
| `/voyante {pseudo}` | Voyante | Voit un rôle |
| `/lg` | Loup Voyant | Devient loup normal |
| `/enfant {pseudo}` | Enfant Sauvage | Choisit mentor |
| `/medium {pseudo}` | Médium | Parle avec un mort |
| `/garde {pseudo}` | Garde | Protège quelqu'un |

## 🧪 Tests

```bash
# Lancer tous les tests
pytest tests/ -v

# Lancer un fichier de test spécifique
pytest tests/test_game.py -v

# Avec coverage
pytest tests/ --cov=. --cov-report=html
```

## 📖 Exemple complet

```bash
# Lancer l'exemple
python example.py
```

Cet exemple montre:
- Création d'une partie
- Configuration des rôles
- Déroulement d'une nuit
- Utilisation des commandes
- Vote et élimination
- Vérification des conditions de victoire

## 🔄 Workflow d'une partie

1. **SETUP** - Ajouter joueurs et configurer rôles
2. **NIGHT** - Actions nocturnes (loups, voyante, etc.)
3. **DAY** - Discussion
4. **VOTE** - Vote pour éliminer
5. Retour à la nuit ou **ENDED** si victoire

## 📚 Documentation

- `API.md` - Documentation complète de l'API
- `todo.txt` - Liste des rôles et fonctionnalités
- Docstrings dans chaque module

## 🏗️ Intégration avec Matrix

Le backend est prêt pour être intégré avec un bot Matrix. Il suffit de:

1. Créer un bot Matrix
2. Mapper les commandes Matrix aux commandes du backend
3. Gérer les salons (salon public, salon loups, MPs)
4. Utiliser `GameManager` et `CommandHandler`

## 🤝 Contribution

Le code suit les bonnes pratiques Python:
- Type hints
- Docstrings
- Architecture modulaire
- Tests unitaires
- Séparation des responsabilités

## 📝 License

À définir

## ✅ Todo pour intégration Matrix

- [ ] Créer le bot Matrix
- [ ] Mapper les commandes
- [ ] Gérer les salons
- [ ] Masquer les pseudos pour la petite fille
- [ ] Interface boutons pour la sorcière
- [ ] Interface boutons pour le voleur
- [ ] Choix convert/manger pour loup noir
- [ ] Vérification mot loup bavard
- [ ] Grognement montreur d'ours
- [ ] Salon médium avec emojis
- [ ] Message mercenaire J1
- [ ] Notification mentaliste

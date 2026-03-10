# Werewolf Matrix

Bot Matrix pour jouer au **Loup-Garou** en temps réel sur un serveur [Matrix](https://matrix.org/).  
Les parties se déroulent en asynchrone : les joueurs s'inscrivent, puis le bot gère automatiquement les phases de nuit, de jour et de vote selon un planning configurable.

---

## Fonctionnalités

- **24 rôles** jouables (Villageois, Loups, Voyante, Sorcière, Cupidon, Chasseur, Voleur, Dictateur, etc.)
- Phases automatisées (Nuit → Jour → Vote) avec horaires configurables
- Salons Matrix dédiés : lobby, village, loups, DMs privés pour les rôles spéciaux
- Persistance complète en SQLite — reprise après redémarrage sans perte de données
- Leaderboard et statistiques par joueur
- Administration via CLI (`admin_cli.py`) ou directement dans Docker
- Chronologie détaillée en fin de partie (journal de toutes les actions secrètes)

---

## Architecture

```
Werewolf-Matrix/
├── main.py              # Point d'entrée du bot
├── admin_cli.py         # CLI d'administration
├── docker-compose.yml   # Déploiement Docker
├── Dockerfile
├── .env                 # Configuration (à créer)
├── models/              # Player, Role, Enums
├── roles/               # Implémentation des 24 rôles
├── game/                # Moteur de jeu (GameManager, VoteManager, ActionManager)
├── commands/            # Dispatch des commandes joueur
├── matrix_bot/          # Intégration Matrix (client, rooms, scheduler, notifications)
├── database/            # Persistance SQLite
├── utils/               # Helpers divers
└── tests/               # Tests unitaires
```

---

## Déploiement avec Docker

### Prérequis

- **Docker** et **Docker Compose** installés
- Un compte bot Matrix avec un **access token**
- Un **Space Matrix** et un **salon lobby** déjà créés

### 1. Cloner le dépôt

```bash
git clone <repo_url>
cd Werewolf-Matrix
```

### 2. Créer le fichier `.env`

```bash
cp .env.example .env   # ou créer manuellement
```

Remplir les variables obligatoires :

```env
# ── Matrix (obligatoire) ──────────────────────────────
MATRIX_HOMESERVER=https://matrix.monserveur.fr
MATRIX_USER_ID=@loup-garou-bot:monserveur.fr
MATRIX_ACCESS_TOKEN=syt_xxxxxxxxxxxxxxxxxxxxxxxx
MATRIX_SPACE_ID=!abcdef:monserveur.fr
MATRIX_LOBBY_ROOM_ID=!ghijkl:monserveur.fr

# ── Matrix (optionnel) ────────────────────────────────
MATRIX_PASSWORD=motdepasse          # Renouvellement auto du token

# ── Préfixe des commandes ─────────────────────────────
COMMAND_PREFIX=!                     # Défaut : !

# ── Horaires de la partie ─────────────────────────────
NIGHT_START_HOUR=21                  # Début de la nuit
DAY_START_HOUR=8                     # Début du jour
VOTE_START_HOUR=19                   # Début du vote
SORCIERE_MIN_HOURS=3                 # Heures min garanties à la Sorcière
GAME_MAX_DURATION_DAYS=7             # Durée max de la partie (jours)
GAME_START_DAY=6                     # Jour de lancement (0=Lundi … 6=Dimanche)
GAME_START_HOUR=12                   # Heure de lancement

# ── Gameplay ──────────────────────────────────────────
CUPIDON_WINS_WITH_COUPLE=true        # Cupidon gagne avec le couple
LITTLE_GIRL_DISTORT_MESSAGES=true    # Messages loups altérés pour la Petite Fille
MENTALISTE_ADVANCE_HOURS=2           # Heures avant fin de vote pour le Mentaliste
```

### 3. Lancer le bot

```bash
docker compose up -d
```

Le bot démarre, se connecte au serveur Matrix et attend les inscriptions dans le salon lobby.

### 4. Vérifier les logs

```bash
docker compose logs -f werewolf-bot
```

### 5. Administration depuis Docker

```bash
# Lister les joueurs inscrits
docker exec werewolf-matrix-bot python admin_cli.py list

# Forcer le lancement immédiat de la partie
docker exec werewolf-matrix-bot python admin_cli.py force-start

# Ajouter un joueur manuellement
docker exec werewolf-matrix-bot python admin_cli.py add "@alice:matrix.org" "Alice"

# Retirer un joueur
docker exec werewolf-matrix-bot python admin_cli.py remove "@alice:matrix.org"

# Tuer un joueur en cours de partie (admin)
docker exec werewolf-matrix-bot python admin_cli.py kill "@alice:matrix.org"
docker exec werewolf-matrix-bot python admin_cli.py kill "@alice:matrix.org" -r "AFK"
```

### Mise à jour

```bash
git pull
docker compose up -d --build
```

---

## Installation locale (développement)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Tests

```bash
pytest tests/ -v
```

---

## Déroulement d'une partie

1. **Inscription** — Les joueurs tapent `!inscription` dans le lobby
2. **Lancement** — Automatique selon `GAME_START_DAY` / `GAME_START_HOUR`, ou forcé par un admin
3. **Nuit** — Les loups votent, les rôles spéciaux agissent en DM privé
   - Deadline des loups : `DAY_START_HOUR - SORCIERE_MIN_HOURS` (par défaut **05h00**)
   - La Sorcière est notifiée à la deadline et dispose d'au moins **3h** pour agir
4. **Jour** — Discussion libre dans le salon du village
5. **Vote** — Les joueurs votent pour éliminer quelqu'un
6. Retour à la nuit, ou **fin de partie** si une équipe a gagné

---

## Rôles

### Village
| Rôle | Description |
|------|-------------|
| Villageois | Rôle de base, vote le jour |
| Voleur | La première nuit, échange son rôle ou tire parmi des cartes non utilisées |
| Voyante | Découvre le rôle d'un joueur chaque nuit |
| Voyante d'Aura | Découvre l'équipe d'un joueur (Gentil/Méchant) |
| Chasseur | Tire sur un joueur en mourant |
| Sorcière | Possède une potion de vie et une potion de mort |
| Cupidon | Lie deux joueurs amoureux (meurent ensemble) |
| Garde | Protège un joueur de l'attaque des loups |
| Médium | Communique avec un mort chaque nuit |
| Petite Fille | Espionne les discussions des loups |
| Montreur d'Ours | Son ours grogne si un loup est voisin |
| Corbeau | Maudit un joueur (+2 votes contre lui) |
| Idiot | Gracié la première fois qu'il est éliminé au vote |
| Enfant Sauvage | Devient loup si son mentor meurt |
| Mercenaire | Doit faire éliminer une cible pour gagner |
| Mentaliste | Sait si le vote majoritaire vise un loup ou un villageois |
| Dictateur | Peut forcer l'élimination d'un joueur (usage unique) |

### Loups
| Rôle | Description |
|------|-------------|
| Loup-Garou | Vote chaque nuit pour tuer un villageois |
| Loup-Voyant | Loup pouvant voir le rôle d'un joueur, puis rejoint la meute |
| Loup-Blanc | Loup solitaire, doit être le dernier survivant |
| Loup-Noir | Peut convertir la victime en loup au lieu de la tuer |
| Loup-Bavard | Loup devant placer un mot imposé dans la discussion de jour |

### Spécial
| Rôle | Description |
|------|-------------|
| Maire | Élu par le village, son vote compte double |

---

## Commandes

Le préfixe est configurable via `COMMAND_PREFIX` (défaut : `!`).  
Les clients Matrix mobiles réservent `/` — utilisez `!` ou un autre préfixe.

| Commande | Rôle | Description |
|----------|------|-------------|
| `!inscription` | Tous | S'inscrire à la prochaine partie |
| `!vote {pseudo}` | Loups / Village | Voter pour éliminer un joueur |
| `!tuer {pseudo}` | Chasseur, Dictateur, Loup Blanc | Tuer un joueur |
| `!cupidon {p1} {p2}` | Cupidon | Lier deux joueurs |
| `!sorciere-sauve {pseudo}` | Sorcière | Utiliser la potion de vie |
| `!sorciere-tue {pseudo}` | Sorcière | Utiliser la potion de mort |
| `!voyante {pseudo}` | Voyante / Voyante d'Aura | Observer un joueur |
| `!garde {pseudo}` | Garde | Protéger un joueur |
| `!medium {pseudo}` | Médium | Consulter un mort |
| `!enfant {pseudo}` | Enfant Sauvage | Choisir un mentor |
| `!corbeau {pseudo}` | Corbeau | Maudire un joueur |
| `!voleur-echange {pseudo}` | Voleur | Échanger son rôle |
| `!voleur-tirer` | Voleur | Tirer 2 cartes |
| `!voleur-choisir {1\|2}` | Voleur | Choisir une carte tirée |
| `!lg` | Loup Voyant | Rejoindre la meute |
| `!convertir` | Loup Noir | Convertir la victime |
| `!dictateur {pseudo}` | Dictateur | Forcer une élimination |
| `!maire {pseudo}` | Maire (mourant) | Désigner un successeur |

---

## Configuration des horaires

| Variable | Défaut | Description |
|----------|--------|-------------|
| `NIGHT_START_HOUR` | `21` | Début de la nuit |
| `DAY_START_HOUR` | `8` | Début du jour |
| `VOTE_START_HOUR` | `19` | Début du vote |
| `SORCIERE_MIN_HOURS` | `3` | Heures min garanties à la Sorcière |
| `GAME_MAX_DURATION_DAYS` | `7` | Durée max de la partie |
| `GAME_START_DAY` | `6` | Jour de lancement (0=Lun … 6=Dim) |
| `GAME_START_HOUR` | `12` | Heure de lancement |

**Deadline des loups** = `DAY_START_HOUR - SORCIERE_MIN_HOURS`  
Valeurs par défaut : 08h − 3h = **05h00**. Les loups votent de 21h à 05h, la Sorcière agit de 05h à 08h.

---

## 📝 License

GPLv3
#!/usr/bin/env python3
"""CLI d'administration serveur pour le bot Loup-Garou.

Permet de gérer les inscriptions et de forcer le lancement de la partie
directement depuis le serveur (ou via ``docker exec``).

Exemples d'utilisation :
    # Ajouter un joueur
    python admin_cli.py add "@alice:matrix.org" "Alice"

    # Retirer un joueur
    python admin_cli.py remove "@alice:matrix.org"

    # Lister les inscrits
    python admin_cli.py list

    # Forcer le lancement immédiat de la partie
    python admin_cli.py force-start

    # Via Docker :
    docker exec werewolf-bot python admin_cli.py list
    docker exec werewolf-bot python admin_cli.py force-start
"""

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Chemin par défaut de la BDD (même que dans game_manager.py)
DEFAULT_DB = os.getenv("WEREWOLF_DB_PATH", "werewolf_game.db")

# Fichier sentinelle pour signaler un lancement immédiat au bot
FORCE_START_SIGNAL = os.getenv("FORCE_START_SIGNAL", "force_start.signal")


# ── Helpers ───────────────────────────────────────────────────────────

def _get_db(db_path: str) -> sqlite3.Connection:
    """Ouvre (ou crée) la base SQLite et s'assure que la table existe."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            registered_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _print_table(rows: list[dict]):
    """Affiche un mini tableau lisible dans le terminal."""
    if not rows:
        print("  (aucune inscription)")
        return
    # Largeurs
    w_id = max(len(r["user_id"]) for r in rows)
    w_name = max(len(r["display_name"]) for r in rows)
    fmt = f"  {{:<{w_id}}}  {{:<{w_name}}}  {{}}"
    print(fmt.format("USER_ID", "DISPLAY_NAME", "INSCRIT LE"))
    print(f"  {'─' * w_id}  {'─' * w_name}  {'─' * 19}")
    for r in rows:
        print(fmt.format(r["user_id"], r["display_name"], r["registered_at"][:19]))


# ── Commandes ─────────────────────────────────────────────────────────

def _extract_username(matrix_id: str) -> str:
    """Extrait le nom d'utilisateur d'un Matrix ID (@user:server → user).

    Même logique que MessageHandler.extract_user_id côté bot.
    """
    match = re.match(r'@([^:]+):', matrix_id)
    return match.group(1) if match else matrix_id


def cmd_add(args):
    """Ajoute un joueur aux inscriptions."""
    conn = _get_db(args.db)
    user_id = args.user_id
    display_name = args.display_name or _extract_username(user_id)

    # Vérifie doublon
    row = conn.execute(
        "SELECT 1 FROM registrations WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row:
        print(f"⚠  {user_id} est déjà inscrit.")
        conn.close()
        return

    conn.execute(
        "INSERT INTO registrations (user_id, display_name, registered_at) VALUES (?, ?, ?)",
        (user_id, display_name, datetime.now().isoformat()),
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    conn.close()
    print(f"✅ {display_name} ({user_id}) ajouté. Total : {count} joueur(s).")


def cmd_remove(args):
    """Retire un joueur des inscriptions."""
    conn = _get_db(args.db)
    user_id = args.user_id

    cur = conn.execute(
        "DELETE FROM registrations WHERE user_id = ?", (user_id,)
    )
    conn.commit()
    if cur.rowcount == 0:
        print(f"⚠  {user_id} n'est pas inscrit.")
    else:
        count = conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
        print(f"🗑  {user_id} retiré. Restant : {count} joueur(s).")
    conn.close()


def cmd_list(args):
    """Affiche les joueurs inscrits."""
    conn = _get_db(args.db)
    rows = conn.execute(
        "SELECT user_id, display_name, registered_at FROM registrations ORDER BY registered_at"
    ).fetchall()
    count = len(rows)
    print(f"📋 {count} joueur(s) inscrit(s) :\n")
    _print_table([dict(r) for r in rows])
    conn.close()


def cmd_force_start(args):
    """Crée le fichier sentinelle pour forcer le lancement de la partie."""
    signal_path = Path(args.signal)
    signal_path.write_text(datetime.now().isoformat())
    print(f"🚀 Signal envoyé ({signal_path.resolve()}).")
    print("   Le bot lancera la partie au prochain cycle de vérification (≤ 30 s).")


def cmd_cancel_force(args):
    """Supprime le fichier sentinelle si on change d'avis."""
    signal_path = Path(args.signal)
    if signal_path.exists():
        signal_path.unlink()
        print("❌ Signal annulé.")
    else:
        print("ℹ  Aucun signal en attente.")


# ── Argument parser ───────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Administration serveur du bot Loup-Garou Matrix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            '  python admin_cli.py add "@alice:matrix.org"          # pseudo = alice\n'
            '  python admin_cli.py add "@alice:matrix.org" "Alice D"  # pseudo = Alice D\n'
            '  python admin_cli.py remove "@alice:matrix.org"\n'
            "  python admin_cli.py list\n"
            "  python admin_cli.py force-start\n"
            "  python admin_cli.py cancel-force\n"
        ),
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB,
        help=f"Chemin vers la BDD SQLite (défaut : {DEFAULT_DB})",
    )
    parser.add_argument(
        "--signal", default=FORCE_START_SIGNAL,
        help=f"Chemin du fichier sentinelle force-start (défaut : {FORCE_START_SIGNAL})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Inscrire un joueur")
    p_add.add_argument("user_id", help='Matrix ID (ex: "@alice:matrix.org")')
    p_add.add_argument("display_name", nargs="?", default=None,
                       help='Nom affiché (optionnel, déduit du Matrix ID sinon)')
    p_add.set_defaults(func=cmd_add)

    # remove
    p_rm = sub.add_parser("remove", help="Désinscrire un joueur")
    p_rm.add_argument("user_id", help='Matrix ID (ex: "@alice:matrix.org")')
    p_rm.set_defaults(func=cmd_remove)

    # list
    p_ls = sub.add_parser("list", help="Lister les inscrits")
    p_ls.set_defaults(func=cmd_list)

    # force-start
    p_fs = sub.add_parser("force-start", help="Forcer le lancement immédiat")
    p_fs.set_defaults(func=cmd_force_start)

    # cancel-force
    p_cf = sub.add_parser("cancel-force", help="Annuler un force-start en attente")
    p_cf.set_defaults(func=cmd_cancel_force)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

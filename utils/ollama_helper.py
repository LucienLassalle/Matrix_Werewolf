"""Helpers pour l'intégration Ollama : capacités modèle, découpe messages, fusion, formatage."""

import logging

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_LENGTH = 2048
# Fenêtre maximale pour éviter les OOM sur serveurs contraints (2vCPU / 4Go RAM)
MAX_CONTEXT_CAP = 4096


def estimate_tokens(text: str) -> int:
    """Estimation grossière du nombre de tokens (4 caractères ≈ 1 token)."""
    return max(1, len(text) // 4)


async def get_model_info(session, ollama_host: str, model_name: str) -> dict:
    """Interroge /api/show d'Ollama pour obtenir les métadonnées du modèle.

    Retourne un dict avec au minimum la clé 'context_length'.
    Ne lève jamais d'exception : retourne les valeurs par défaut en cas d'erreur.
    """
    try:
        response = await session.post(
            f"{ollama_host}/api/show",
            json={"model": model_name},
            timeout=10,
        )
        if response.status != 200:
            return {"context_length": DEFAULT_CONTEXT_LENGTH, "model_name": model_name}

        data = await response.json()
        context_length = DEFAULT_CONTEXT_LENGTH

        # Tenter d'extraire depuis model_info (ex: "llama.context_length", "qwen2.context_length")
        model_info = data.get("model_info", {})
        for key, val in model_info.items():
            if "context_length" in key and isinstance(val, (int, float)) and val > 0:
                context_length = int(val)
                break

        # Fallback : lire num_ctx dans la chaîne "parameters"
        if context_length == DEFAULT_CONTEXT_LENGTH:
            for line in data.get("parameters", "").splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] == "num_ctx":
                    try:
                        context_length = int(parts[1])
                    except ValueError:
                        pass
                    break

        return {
            "context_length": context_length,
            "model_name": data.get("name", model_name),
        }
    except Exception as e:
        logger.warning("Impossible de récupérer les infos du modèle %s : %s", model_name, e)
        return {"context_length": DEFAULT_CONTEXT_LENGTH, "model_name": model_name}


def chunk_messages(messages: list, max_tokens: int) -> list:
    """Découpe une liste de messages en chunks ne dépassant pas max_tokens chacun.

    Garantit qu'aucun message isolé n'est perdu, même s'il dépasse max_tokens.
    """
    if not messages:
        return []

    chunks: list = []
    current_chunk: list = []
    current_tokens = 0

    for msg in messages:
        msg_tokens = estimate_tokens(f"{msg.get('sender', '')}: {msg.get('message', '')}")
        if current_tokens + msg_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [msg]
            current_tokens = msg_tokens
        else:
            current_chunk.append(msg)
            current_tokens += msg_tokens

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def merge_summaries(summaries: list) -> dict:
    """Fusionne plusieurs résumés partiels en un seul, en dédupliquant les entrées."""
    if not summaries:
        return {"accusations": [], "citations": [], "synthese": ""}
    if len(summaries) == 1:
        return summaries[0]

    merged_accusations: list = []
    merged_citations: list = []
    seen_acc: set = set()
    seen_cit: set = set()
    syntheses: list = []

    for s in summaries:
        for acc in s.get("accusations", []):
            key = (acc.get("accuser", ""), acc.get("accused", ""))
            if key not in seen_acc:
                seen_acc.add(key)
                merged_accusations.append(acc)
        for cit in s.get("citations", []):
            key = (cit.get("author", ""), cit.get("text", "")[:50])
            if key not in seen_cit:
                seen_cit.add(key)
                merged_citations.append(cit)
        if s.get("synthese"):
            syntheses.append(s["synthese"])

    return {
        "accusations": merged_accusations,
        "citations": merged_citations,
        "synthese": " | ".join(syntheses),
    }


def format_summary_message(parsed: dict) -> str:
    """Formate un résumé parsé en message lisible pour Matrix."""
    lines = ["📋 **Résumé généré** des débats du village\n"]

    accusations = parsed.get("accusations", [])
    if accusations:
        lines.append("⚔️ **Accusations :**")
        for acc in accusations:
            accuser = acc.get("accuser", "?")
            accused = acc.get("accused", "?")
            quote = acc.get("quote", "")
            line = f"  • **{accuser}** → **{accused}**"
            if quote:
                line += f' : *"{quote}"*'
            lines.append(line)
        lines.append("")

    citations = parsed.get("citations", [])
    if citations:
        lines.append("💬 **Citations notables :**")
        for cit in citations:
            author = cit.get("author", "?")
            text = cit.get("text", "")
            if text:
                lines.append(f'  • **{author}** : *"{text}"*')
        lines.append("")

    synthese = parsed.get("synthese", "")
    if synthese:
        lines.append("📝 **Synthèse :**")
        lines.append(f"  {synthese}")

    return "\n".join(lines)

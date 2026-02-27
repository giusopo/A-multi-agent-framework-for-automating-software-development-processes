import json
import re
import requests
from typing import Any, List

LM_API_URL = "http://127.0.0.1:1234/v1/completions"
MODEL_NAME = "qwen2.5-coder-1.5b-instruct"


def _normalize_feedback(text: Any) -> str:
    """Rende sempre stringa l'input, anche se arriva list/dict."""
    if text is None:
        return ""
    if isinstance(text, str):
        return text.strip()
    try:
        return json.dumps(text, ensure_ascii=False).strip()
    except Exception:
        return str(text).strip()


def _extract_json_object(raw: str) -> str:
    """
    Estrae il primo blocco JSON { ... } dal testo, se presente.
    Utile quando il modello aggiunge testo extra.
    """
    if not raw:
        return ""
    match = re.search(r"\{[\s\S]*\}", raw)
    return match.group(0).strip() if match else ""


def _fallback_rules(diagram_type: str, feedback: str) -> List[str]:
    """
    Fallback deterministico: se il modello non risponde bene,
    facciamo mapping semplice -> regole.
    """
    f = feedback.lower()

    rules = []

    # Sequence: user actor
    if diagram_type == "sequence_diagram":
        if ("missing" in f or "add" in f) and "actor" in f and "user" in f:
            rules.append("require_user_actor")

        if "left to right" in f or "left-to-right" in f:
            rules.append("enforce_left_to_right_alignment")

        if "duplicate" in f and ("participant" in f or "lifeline" in f):
            rules.append("avoid_duplicate_participants")

    return rules


def extract_rules_from_feedback(diagram_type: str, vision_text: Any) -> List[str]:
    """
    Usa un LLM deterministico per estrarre regole strutturate dal feedback.
    Se LLM fallisce/parsing fallisce -> fallback rule-based.
    Restituisce una lista di rule names (stringhe).
    """
    feedback = _normalize_feedback(vision_text)
    if not feedback:
        return []

    prompt = f"""
You are a strict rule extractor for UML diagram improvements.

Return ONLY valid JSON.
No explanations. No markdown.

Allowed rule names (use only these):
- require_user_actor
- enforce_left_to_right_alignment
- avoid_duplicate_participants

Output format:
{{
  "rules": ["rule_name"]
}}

Diagram type: {diagram_type}

Feedback:
{feedback}
""".strip()

    # 1) Prova LLM
    try:
        response = requests.post(
            LM_API_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "temperature": 0,
                "max_tokens": 120,
            },
            timeout=25,
        )

        data = response.json()
        if "choices" not in data or not data["choices"]:
            # fallback
            return _fallback_rules(diagram_type, feedback)

        raw_text = (data["choices"][0].get("text") or "").strip()

        # 2) Parsing robusto
        json_text = _extract_json_object(raw_text)
        if not json_text:
            return _fallback_rules(diagram_type, feedback)

        parsed = json.loads(json_text)
        rules = parsed.get("rules", [])

        # 3) Normalizza output
        if not isinstance(rules, list):
            return _fallback_rules(diagram_type, feedback)

        cleaned = []
        for r in rules:
            if isinstance(r, str) and r.strip():
                cleaned.append(r.strip())

        # Se LLM ha sparato regole fuori whitelist -> fallback
        whitelist = {
            "require_user_actor",
            "enforce_left_to_right_alignment",
            "avoid_duplicate_participants",
        }
        cleaned = [r for r in cleaned if r in whitelist]

        return cleaned if cleaned else _fallback_rules(diagram_type, feedback)

    except Exception:
        # fallback sicuro
        return _fallback_rules(diagram_type, feedback)
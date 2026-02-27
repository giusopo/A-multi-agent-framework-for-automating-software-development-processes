import requests
import json
import re

LM_API_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5-coder-1.5b-instruct"


def generate_diagram_description(model, view: str) -> str:
    """
    Generates a professional architectural description using an LLM.
    Output:
    - Formal technical English
    - 220–260 words
    - No markdown formatting
    - Continuous academic paragraphs
    """

    # -----------------------------
    # Extract structural info
    # -----------------------------
    try:
        components = model.get_logical_components()
        component_names = [getattr(c, "id", str(c)) for c in components]
    except Exception:
        component_names = []

    try:
        connectors = model.get_logical_connectors()
        relationships = [
            {
                "source": getattr(conn, "source", ""),
                "target": getattr(conn, "target", ""),
                "type": getattr(conn, "type", "")
            }
            for conn in connectors
        ]
    except Exception:
        relationships = []

    architecture_context = {
        "system_name": model.id,
        "view": view,
        "components": component_names,
        "relationships": relationships[:12]
    }

    view_focus = {
        "context_view": "Explain the system boundary and external interactions.",
        "logical_view": "Explain modular decomposition and service responsibilities.",
        "deployment_view": "Explain infrastructure distribution and scalability implications.",
        "runtime_view": "Explain dynamic interaction flow and coordination logic.",
        "security_view": "Explain trust boundaries and security design mechanisms."
    }

    focus_instruction = view_focus.get(
        view,
        "Explain the architectural meaning of this diagram."
    )

    prompt = f"""
You are a senior software architect.

Write a formal architectural description in professional technical English.

STRICT RULES:
- No headings
- No bullet points
- No numbered lists
- No markdown formatting
- No bold or special characters
- Only continuous paragraphs
- Between 220 and 260 words
- Do not describe visual layout
- Explain architectural implications and design rationale

System name: {model.id}
Diagram type: {view}

Architectural structure:
{json.dumps(architecture_context, indent=2)}

Focus:
{focus_instruction}
"""

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 380
    }

    try:
        response = requests.post(
            LM_API_URL,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            return ""

        data = response.json()

        if "choices" not in data or not data["choices"]:
            return ""

        raw_text = data["choices"][0]["message"]["content"].strip()

        # -----------------------------
        # Safety cleaning
        # -----------------------------
        cleaned = raw_text

        # Remove markdown headings
        cleaned = re.sub(r"#{1,6}\s*", "", cleaned)

        # Remove bullet markers
        cleaned = re.sub(r"^\s*[-*•]\s+", "", cleaned, flags=re.MULTILINE)

        # Remove numbered lists
        cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)

        # Remove bold markers
        cleaned = cleaned.replace("**", "")

        # Normalize spacing
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned.strip()

    except Exception:
        # Never break the document if LLM fails
        return ""
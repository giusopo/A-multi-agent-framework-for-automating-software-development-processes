import json
from pathlib import Path


class KnowledgeBase:
    """
    Static + Learned Knowledge Base for documentation rules.
    """

    def __init__(self, kb_data: dict, path: Path):
        self.path = path
        self.raw_data = kb_data

        self.view_to_diagram_mapping = kb_data.get("view_to_diagram_mapping", {})
        self.layout_rules = kb_data.get("layout_rules", {})
        self.learned_rules = kb_data.get("learned_rules", {})

    def save(self):
        """Persist KB su disco."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.raw_data, f, indent=4)
        print("[KB SAVED] Persisted to disk.")


def load_knowledge_base(path: Path) -> KnowledgeBase:
    if not path.exists():
        raise FileNotFoundError(f"KB file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Sezione learned_rules inizializzata se mancante
    if "learned_rules" not in data:
        data["learned_rules"] = {}

    return KnowledgeBase(data, path)
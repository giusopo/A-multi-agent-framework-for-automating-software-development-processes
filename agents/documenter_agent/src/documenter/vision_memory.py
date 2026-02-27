import json
from pathlib import Path
from datetime import datetime


def save_vision_feedback(base_dir: Path,
                         diagram_type: str,
                         architecture_id: str,
                         feedback_text: str):
    """
    Salva lo storico dei feedback Vision in:
    data/vision_feedback/history.json

    Struttura:
    [
      {
        timestamp,
        architecture_id,
        diagram_type,
        feedback
      }
    ]
    """

    history_dir = base_dir / "data" / "vision_feedback"
    history_dir.mkdir(parents=True, exist_ok=True)

    history_file = history_dir / "history.json"

    # Carica storico esistente
    if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []

    history.append({
        "timestamp": datetime.utcnow().isoformat(),
        "architecture_id": architecture_id,
        "diagram_type": diagram_type,
        "feedback": feedback_text
    })

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
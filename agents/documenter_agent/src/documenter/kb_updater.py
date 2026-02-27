def update_kb_from_feedback(kb_path, diagram_type, new_rules):
    """
    Aggiorna la Knowledge Base persistendo nuove regole strutturali.
    """
    import json

    with open(kb_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "learned_rules" not in data:
        data["learned_rules"] = {}

    updated = False

    for rule in new_rules:
        if rule not in data["learned_rules"]:
            data["learned_rules"][rule] = {
                "diagram_type": diagram_type,
                "active": True
            }
            updated = True

    if updated:
        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print("[KB UPDATED] Persisted new structural rules.")
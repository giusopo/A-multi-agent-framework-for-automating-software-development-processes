from pathlib import Path
import json

from src.documenter.kb_loader import load_knowledge_base
from src.documenter.planner import create_documentation_plan
from src.documenter.models import ArchitectureModel

from src.documenter.uml_generator import (
    generate_security_diagram,
    generate_sequence_diagram,
    generate_context_diagram,
    generate_deployment_diagram,
    generate_component_diagram,
    regenerate_sequence_with_feedback,
    compile_plantuml,
)

from src.documenter.structural_analyzer import analyze_sequence_structural
from src.documenter.vision_rule_extractor import extract_rules_from_feedback
from src.documenter.kb_updater import update_kb_from_feedback
from src.documenter.document_builder import build_document_bundle


def load_architecture(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_architecture(data: dict, architecture_id: str) -> dict:
    for arch in data.get("architectural_views", []):
        if arch.get("architecture_id") == architecture_id:
            return arch
    raise ValueError(f"Architecture '{architecture_id}' not found.")


def safe_compile(puml_path: Path) -> bool:
    try:
        compile_plantuml(puml_path)
        return puml_path.with_suffix(".png").exists()
    except Exception as e:
        print(f"[WARNING] Compile failed for {puml_path.name}: {e}")
        return False


if __name__ == "__main__":

    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    # =============================
    # 1️⃣ Knowledge Base
    # =============================

    kb_path = BASE_DIR / "data" / "kb" / "documentation_rules.json"
    kb = load_knowledge_base(kb_path)

    print("\nKnowledge Base loaded.")
    for view, diagram in kb.view_to_diagram_mapping.items():
        print(f"- {view} -> {diagram}")

    # =============================
    # 2️⃣ Architecture
    # =============================

    input_path = BASE_DIR / "data" / "input" / "finalArchitecture.json"
    architecture_data = load_architecture(input_path)

    selected_id = "Microservices Architecture"
    selected_architecture = select_architecture(architecture_data, selected_id)
    selected_model = ArchitectureModel(selected_architecture)

    print(f"\nSelected architecture: {selected_model.id}")

    # =============================
    # 3️⃣ Documentation Plan
    # =============================

    plan = create_documentation_plan(selected_model)
    print("\nDocumentation Plan:")
    for view in plan.views:
        print(f"- {view}")

    # =============================
    # 4️⃣ Layout check
    # =============================

    max_components = kb.layout_rules.get("max_components_per_view", 10)
    components = selected_model.get_logical_components()

    if len(components) > max_components:
        print("\n[LAYOUT WARNING] Logical view exceeds max components per view.")
    else:
        print("\nLayout check passed.")

    # =============================
    # Output dirs
    # =============================

    diagrams_dir = BASE_DIR / "docs" / "generated" / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    generated_files = []

    # =============================
    # 5️⃣ Generate diagrams
    # =============================

    for view in plan.views:
        print("PLAN VIEWS", plan.views)
        diagram_type = kb.view_to_diagram_mapping.get(view)
        print(f"\n[DEBUG] View: {view}")
        print(f"[DEBUG] Diagram type from KB: {diagram_type}")

        puml_path = diagrams_dir / f"{diagram_type}.puml"

        # -----------------------------
        # STRUCTURAL DIAGRAMS
        # -----------------------------

        if diagram_type == "component_diagram":
            generate_component_diagram(selected_model, puml_path)
            safe_compile(puml_path)

        elif diagram_type == "deployment_diagram":
            generate_deployment_diagram(selected_model, puml_path)
            safe_compile(puml_path)

        elif diagram_type == "context_diagram":
            generate_context_diagram(selected_model, puml_path)
            safe_compile(puml_path)

        elif diagram_type == "security_diagram":
            generate_security_diagram(selected_model, puml_path)
            safe_compile(puml_path)

        # -----------------------------
        # SEQUENCE DIAGRAM (SELF-EVOLVING)
        # -----------------------------

        elif diagram_type == "sequence_diagram":

            # 🔹 Carica regole apprese dalla KB
            sequence_rules = []

            with open(kb_path, "r", encoding="utf-8") as f:
                kb_data = json.load(f)

            learned = kb_data.get("learned_rules", {})

            for rule_name, rule_info in learned.items():
                if (
                    rule_info.get("diagram_type") == "sequence_diagram"
                    and rule_info.get("active", False)
                ):
                    sequence_rules.append(rule_name)

            # 🔹 Generazione base con regole apprese
            print("Loaded learned rules:", learned)
            print("Sequence rules applied:", sequence_rules)

            generate_sequence_diagram(
                selected_model,
                puml_path,
                rules=sequence_rules
            )

            safe_compile(puml_path)

            # 🔹 Analisi strutturale
            try:
                with open(puml_path, "r", encoding="utf-8") as f:
                    uml_code = f.read()

                structural_feedback = analyze_sequence_structural(uml_code)

                print("\n[STRUCTURAL FEEDBACK]:\n", structural_feedback)

                # 🔹 LLM → Estrazione regole strutturate
                new_rules = extract_rules_from_feedback(
                    "sequence_diagram",
                    structural_feedback
                )

                if new_rules:
                    update_kb_from_feedback(
                        kb_path,
                        "sequence_diagram",
                        new_rules
                    )
                    print("[KB UPDATED] Nuove regole salvate:", new_rules)

                    # 🔥 RICARICA KB (QUESTO È IL FIX IMPORTANTE)
                    kb = load_knowledge_base(kb_path)

                    # 🔹 Rigenerazione migliorata
                    regenerate_sequence_with_feedback(
                        selected_model,
                        structural_feedback,
                        puml_path
                    )
                    safe_compile(puml_path)

            except Exception as e:
                print("[STRUCTURAL ANALYSIS ERROR]", e)

        else:
            print(f"[INFO] Diagram type '{diagram_type}' not implemented.")

        generated_files.append(puml_path)

    # =============================
    # 6️⃣ Build document
    # =============================

    build_document_bundle(
        BASE_DIR,
        plan,
        selected_model,
        kb,
        architecture_data  # ← JSON completo passato al builder
    )

    print("\nGenerated artifacts:")
    for f in generated_files:
        print(f"- {f}")
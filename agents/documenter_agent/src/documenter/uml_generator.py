import subprocess
from pathlib import Path
from src.documenter.models import ArchitectureModel


# =========================
# COMPONENT DIAGRAM
# =========================

def generate_component_diagram(model: ArchitectureModel, output_path: Path):
    components = model.get_logical_components()
    connectors = model.get_logical_connectors()

    lines = []
    lines.append("@startuml")
    lines.append("skinparam componentStyle rectangle")
    lines.append("")

    for comp in components:
        safe = comp.id.replace(" ", "")
        lines.append(f'component "{comp.id}" as {safe}')

    lines.append("")

    for conn in connectors:
        if conn.source and conn.target:
            source = conn.source.replace(" ", "")
            target = conn.target.replace(" ", "")
            lines.append(f"{source} --> {target} : {conn.type}")

    lines.append("@enduml")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# =========================
# DEPLOYMENT DIAGRAM
# =========================

def generate_deployment_diagram(model: ArchitectureModel, output_path: Path):
    deployment_view = model.get_view("deployment_view")

    nodes = deployment_view.get("nodes", [])
    component_mapping = deployment_view.get("component_mapping", {})

    lines = []
    lines.append("@startuml")
    lines.append("skinparam nodeStyle rectangle")
    lines.append("")

    for node in nodes:
        if isinstance(node, dict):
            node_name = node.get("name")
            safe_node = node_name.replace(" ", "")
            lines.append(f'node "{node_name}" as {safe_node} {{')
            for comp in node.get("components", []):
                safe_comp = comp.replace(" ", "")
                lines.append(f'  component "{comp}" as {safe_comp}')
            lines.append("}")
        else:
            safe_node = node.replace(" ", "")
            lines.append(f'node "{node}" as {safe_node}')

    lines.append("")

    for comp, node in component_mapping.items():
        safe_comp = comp.replace(" ", "")
        safe_node = node.replace(" ", "")
        lines.append(f"{safe_comp} --> {safe_node}")

    lines.append("@enduml")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# =========================
# CONTEXT DIAGRAM
# =========================

def generate_context_diagram(model: ArchitectureModel, output_path: Path):
    """
    Genera un diagramma di contesto (C4 - Level 1).
    Mostra il sistema come black-box e gli attori esterni.
    """

    system_name = model.id

    lines = []
    lines.append("@startuml")
    lines.append("left to right direction")
    lines.append("skinparam rectangleStyle rounded")
    lines.append("skinparam shadowing false")
    lines.append("")

    # Attori esterni
    lines.append('actor "User" as User')
    lines.append('rectangle "Payment Provider" as Payment')
    lines.append('rectangle "Shipping Provider" as Shipping')
    lines.append("")

    # Sistema come black-box
    lines.append(f'rectangle "{system_name}" as System #LightBlue')
    lines.append("")

    # Relazioni
    lines.append("User --> System : Uses platform")
    lines.append("System --> Payment : Processes payments")
    lines.append("System --> Shipping : Handles shipments")

    lines.append("@enduml")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# =========================
# SEQUENCE DIAGRAM
# =========================

def generate_sequence_diagram(model, output_file, rules=None):
    """
    Genera un diagramma di sequenza.
    Applica eventuali regole apprese dalla KB.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    components = model.get_logical_components()
    connectors = model.get_logical_connectors()

    rules = rules or []

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("@startuml\n\n")

        # ✅ Applica regola self-evolving: se presente, inserisci User
        if "require_user_actor" in rules:
            f.write('actor "User" as User\n\n')

        # Participant ordinati e unici
        written = set()
        for comp in components:
            alias = comp.id.replace(" ", "")
            if alias not in written:
                f.write(f'participant "{comp.id}" as {alias}\n')
                written.add(alias)

        f.write("\n")

        # Messaggi
        for conn in connectors:
            source = conn.source.replace(" ", "")
            target = conn.target.replace(" ", "")
            f.write(f"{source} -> {target} : {conn.type}\n")

        f.write("\n@enduml\n")


# =========================
# SEQUENCE REGENERATION (VISION)
# =========================

def regenerate_sequence_with_feedback(model, feedback: str, output_path):
    """
    Rigenera il diagramma di sequenza tenendo conto del feedback
    ricevuto dal Vision LLM.
    Garantisce la presenza dell'attore User.
    """

    components = model.get_logical_components()
    connectors = model.get_logical_connectors()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("@startuml\n\n")

        # 👇 1️⃣ USER SEMPRE PRESENTE
        f.write("actor User\n\n")

        # 👇 2️⃣ Participant ordinati e unici
        written = set()
        for comp in components:
            alias = comp.id.replace(" ", "")
            if alias not in written:
                f.write(f'participant "{comp.id}" as {alias}\n')
                written.add(alias)

        f.write("\n")

        # 👇 3️⃣ Messaggi sequenziali coerenti
        for conn in connectors:
            source = conn.source.replace(" ", "")
            target = conn.target.replace(" ", "")
            f.write(f"{source} -> {target} : {conn.type}\n")

        # 👇 4️⃣ Piccolo miglioramento layout automatico
        if feedback and "spacing" in feedback.lower():
            f.write("\n' Vision suggested spacing improvement\n")

        f.write("\n@enduml\n")

# =========================
# SECURITY DIAGRAM
# =========================

def generate_security_diagram(model: ArchitectureModel, output_path: Path):
    lines = []
    lines.append("@startuml")
    lines.append("actor User")
    lines.append('rectangle "Web Server" as WebServer')
    lines.append('rectangle "Application Server" as AppServer')
    lines.append('database "Database Server" as DBServer')
    lines.append("")

    lines.append("User -> WebServer : HTTPS Request")
    lines.append("WebServer -> AppServer : Forward")
    lines.append("AppServer -> DBServer : Query")
    lines.append("AppServer -> WebServer : Response")
    lines.append("WebServer -> User : HTTPS Response")
    lines.append("")
    lines.append("note right of WebServer")
    lines.append("TLS Encryption")
    lines.append("end note")
    lines.append("@enduml")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# =========================
# PLANTUML COMPILER
# =========================

def compile_plantuml(puml_path: Path):
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    plantuml_jar = BASE_DIR / "tools" / "plantuml.jar"

    if not plantuml_jar.exists():
        raise FileNotFoundError(f"PlantUML jar not found at {plantuml_jar}")

    subprocess.run(
        ["java", "-jar", str(plantuml_jar), str(puml_path)],
        check=True
    )

from typing import Callable, Optional

def vision_refine_diagram(
    diagram_type: str,
    puml_path: Path,
    generate_fn: Callable[[], None],
    analyze_fn: Callable[[str, str], dict],
    regenerate_fn: Optional[Callable[[str], None]] = None,
    compile_after_regen: bool = True,
) -> dict:
    """
    Loop:
    1) generate_fn() produce puml_path
    2) compile -> png
    3) analyze_fn(png_path, diagram_type) -> feedback json
    4) regenerate_fn(vision_text) aggiorna il .puml (opzionale)
    5) ricompila -> png (opzionale)
    """
    # 1) generate
    generate_fn()

    # 2) compile
    compile_plantuml(puml_path)
    png_path = puml_path.with_suffix(".png")

    # 3) analyze
    feedback = analyze_fn(str(png_path), diagram_type=diagram_type)

    # 🔒 Controllo sicurezza
    if not isinstance(feedback, dict) or "choices" not in feedback:
        return feedback  # ritorna direttamente (timeout o errore)

    vision_text = feedback["choices"][0]["message"]["content"]

    # 4) regenerate (se disponibile)
    if regenerate_fn is not None:
        regenerate_fn(vision_text)

        # 5) compile again
        if compile_after_regen:
            compile_plantuml(puml_path)

    return feedback
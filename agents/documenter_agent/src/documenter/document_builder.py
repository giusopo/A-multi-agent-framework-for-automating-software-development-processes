from pathlib import Path
import subprocess

from src.documenter.lm_integration import generate_diagram_description
from src.documenter.uml_generator import compile_plantuml


def build_document_bundle(base_dir: Path, plan, model, kb, full_input):

    docs_dir = base_dir / "docs" / "generated"
    diagrams_dir = docs_dir / "diagrams"

    docs_dir.mkdir(parents=True, exist_ok=True)
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    output_md = docs_dir / "documentation.md"
    output_pdf = docs_dir / "documentation.pdf"

    # ----------------------------------------------------------
    # Ensure PNG exists
    # ----------------------------------------------------------
    def ensure_png(diagram_type: str) -> bool:
        puml = diagrams_dir / f"{diagram_type}.puml"
        png = diagrams_dir / f"{diagram_type}.png"

        if png.exists():
            return True

        if puml.exists():
            try:
                compile_plantuml(puml)
                return png.exists()
            except Exception:
                return False

        return False

    diagram_titles = {
        "context_view": "Context Diagram",
        "logical_view": "Component Diagram",
        "deployment_view": "Deployment Diagram",
        "runtime_view": "Sequence Diagram",
        "security_view": "Security Diagram",
    }

    # Fixed order (avoids layout confusion)
    FIXED_VIEW_ORDER = [
        "context_view",
        "logical_view",
        "deployment_view",
        "runtime_view",
        "security_view"
    ]

    ordered_views = [v for v in FIXED_VIEW_ORDER if v in plan.views]

    lines = []
    lines.append("# Architectural Documentation\n")
    lines.append("---\n")

    # ==========================================================
    # 1. Introduction
    # ==========================================================
    lines.append("## 1. Introduction\n")
    lines.append(
        f"This document presents the architectural description of **{model.id}**. "
        "The objective of this documentation is to provide a structured and comprehensive "
        "overview of the system’s architectural drivers, quality requirements, constraints, "
        "design trade-offs, and structural views.\n"
    )
    lines.append(
        "The documentation follows common architectural documentation practices "
        "(inspired by IEEE 1016), aiming to support both technical understanding "
        "and design evaluation.\n"
    )
    lines.append(
        "The following sections describe the key architectural drivers, quality attribute "
        "scenarios, constraints, stakeholder concerns, and the evaluation of the selected "
        "architecture. Finally, UML views are presented to visually represent the system.\n"
    )

    lines.append("\n---\n")

    # ==========================================================
    # 2. Architectural Drivers
    # ==========================================================
    lines.append("## 2. Architectural Drivers\n")

    drivers = full_input.get("architectural_drivers", [])

    if not drivers:
        lines.append("_No architectural drivers available._\n")
    else:
        for d in drivers:
            lines.append(
                f"### {d.get('id')} (Priority: {d.get('priority')})\n"
            )
            lines.append(f"**Description:** {d.get('description')}\n\n")
            lines.append(f"**Rationale:** {d.get('rationale')}\n\n")

    lines.append("\n---\n")

    # ==========================================================
    # 3. Quality Attribute Scenarios
    # ==========================================================
    lines.append("## 3. Quality Attribute Scenarios\n")

    scenarios = full_input.get("quality_attribute_scenarios", [])

    if not scenarios:
        lines.append("_No quality attribute scenarios defined._\n")
    else:
        for s in scenarios:
            lines.append(
                f"### {s.get('attribute')} (Priority: {s.get('priority')})\n"
            )
            lines.append(f"- **Stimulus:** {s.get('stimulus')}\n")
            lines.append(f"- **Environment:** {s.get('environment')}\n")
            lines.append(f"- **Response:** {s.get('response')}\n")
            lines.append(f"- **Measure:** {s.get('measure')}\n\n")

    lines.append("\n---\n")

    # ==========================================================
    # 4. Constraints and Stakeholders
    # ==========================================================
    lines.append("## 4. Constraints and Stakeholders\n")

    lines.append("### 4.1 Constraints\n")
    constraints = full_input.get("constraints", [])
    if not constraints:
        lines.append("_No constraints specified._\n")
    else:
        for c in constraints:
            lines.append(f"- {c}\n")

    lines.append("\n### 4.2 Stakeholders\n")
    stakeholders = full_input.get("stakeholders", [])
    if not stakeholders:
        lines.append("_No stakeholders specified._\n")
    else:
        for st in stakeholders:
            lines.append(f"- {st}\n")

    lines.append("\n---\n")

    # ==========================================================
    # 5. Architecture Evaluation
    # ==========================================================
    lines.append("## 5. Architecture Evaluation\n")

    evaluations = full_input.get("architecture_evaluation", [])
    selected_eval = None

    for e in evaluations:
        if e.get("architecture_id") == model.id:
            selected_eval = e
            break

    if not selected_eval:
        lines.append("_No evaluation data available for the selected architecture._\n")
    else:
        lines.append("### 5.1 Driver Coverage\n")
        for cov in selected_eval.get("driver_coverage", []):
            lines.append(
                f"- **{cov.get('driver_id')}**: {cov.get('satisfied')}\n"
            )

        lines.append("\n### 5.2 Quality Attribute Trade-offs\n")
        for t in selected_eval.get("quality_attribute_tradeoffs", []):
            attrs = ", ".join(t.get("attributes_involved", []))
            lines.append(f"- **{attrs}**: {t.get('tradeoff_description')}\n")

        lines.append("\n### 5.3 Risks and Limitations\n")
        for r in selected_eval.get("risks_and_limitations", []):
            lines.append(
                f"- (**{r.get('severity')}**) {r.get('description')}\n"
            )

        lines.append("\n### 5.4 Recommended Improvements\n")
        for ref in selected_eval.get("recommended_refinements", []):
            lines.append(f"- {ref.get('description')}\n")

    lines.append("\n---\n")

        # ==========================================================
    # 6. Architectural Style Rationale
    # ==========================================================
    lines.append("## 6. Architectural Style Rationale\n")
    lines.append(
        "The selected Microservices Architecture was chosen to address key drivers "
        "such as scalability, availability, and independent deployment. "
        "By decomposing the system into autonomous services, each component can evolve, "
        "scale, and be maintained independently, reducing coupling and improving resilience.\n\n"
        "This architectural style supports horizontal scalability, fault isolation, "
        "and technology heterogeneity, which are critical in high-load and cloud-native environments."
    )

    lines.append("\n---\n")

    # ==========================================================
    # 7. Key Architectural Decisions
    # ==========================================================
    lines.append("## 7. Key Architectural Decisions\n")
    lines.append(
        "- Adoption of microservices to isolate business capabilities and reduce coupling.\n"
        "- Independent deployment of services to improve maintainability and evolvability.\n"
        "- Cloud-native infrastructure to enable elasticity and high availability.\n"
        "- Clear separation between application logic, infrastructure, and external integrations.\n"
    )

    lines.append("\n---\n")

    # ==========================================================
    # 8. Architectural Views
    # ==========================================================
    lines.append("## 8. Architectural Views\n")

    view_section_number = 8
    subsection_counter = 1

    for view in ordered_views:
        diagram_type = kb.view_to_diagram_mapping.get(view)
        title = diagram_titles.get(view, view)

        lines.append(f"\n### 8.{subsection_counter} {title}\n")

        if diagram_type and ensure_png(diagram_type):
            lines.append(f"![{title}](diagrams/{diagram_type}.png)\n")
        else:
            lines.append("_Diagram not available_\n")

        try:
            desc = generate_diagram_description(model, view)
            if desc.strip():
                lines.append(desc + "\n")
        except Exception:
            pass

        subsection_counter += 1


    # ==========================================================
    # 9. Limitations and Future Work
    # ==========================================================
    lines.append("\n## 9. Limitations and Future Work\n")
    lines.append(
        "The current architectural evaluation is primarily qualitative and based on design reasoning. "
        "No empirical performance benchmarking or resilience testing has yet been performed. "
        "Future work should include quantitative validation through load testing, failure injection experiments, "
        "and distributed consistency verification.\n\n"
        "Further refinement may involve improving observability mechanisms, introducing automated resilience "
        "validation pipelines, and refining data management strategies under peak demand scenarios."
    )


    # ==========================================================
    # 10. Conclusion
    # ==========================================================
    lines.append("\n## 10. Conclusion\n")
    lines.append(
        f"The **{model.id}** architecture provides a structured and scalable solution aligned with the identified "
        "architectural drivers. By adopting a microservices-based decomposition, the system enables modular growth, "
        "independent deployment, and fault isolation.\n\n"
        "The evaluation highlights a deliberate balance between scalability, availability, maintainability, and "
        "operational complexity. While the architecture satisfies high-priority requirements, further empirical "
        "validation and resilience refinement are recommended.\n\n"
        "Overall, the proposed architectural design establishes a robust foundation for long-term evolution "
        "in cloud-native, high-demand environments."
    )

    # ==========================================================
    # Write Markdown
    # ==========================================================
    output_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[DOCUMENT BUILT] {output_md}")

    # ==========================================================
    # Generate PDF
    # ==========================================================
    try:
        subprocess.run(
            [
                "pandoc",
                str(output_md),
                "-o",
                str(output_pdf),
                "--pdf-engine=xelatex",
                "--resource-path",
                str(docs_dir),
            ],
            check=True,
        )
        print(f"[PDF GENERATED] {output_pdf}")
    except Exception as e:
        print("[WARNING] PDF generation failed:", e)
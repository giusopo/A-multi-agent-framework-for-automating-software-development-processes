# utils.py
from langchain_community.vectorstores import Chroma
import yaml

def clean_raw_json(raw_text: str) -> str:
    """
    Rimuove testo prima/dopo un JSON valido.
    Supporta sia {} che [].
    """
    raw_text = raw_text.strip()

    first_curly = raw_text.find("{")
    last_curly = raw_text.rfind("}")

    first_square = raw_text.find("[")
    last_square = raw_text.rfind("]")

    candidates = []

    if first_curly != -1 and last_curly != -1:
        candidates.append((first_curly, last_curly))

    if first_square != -1 and last_square != -1:
        candidates.append((first_square, last_square))

    if not candidates:
        return raw_text

    start, end = min(candidates, key=lambda x: x[0])
    return raw_text[start:end + 1]


def load_knowledge(
    embedding_function,
    chroma_path: str,
    query: str,
    k: int
) -> tuple[str, list[str]]:
    """
    Retrieves context and sources from a Chroma vector store.
    """
    db = Chroma(
        persist_directory=chroma_path,
        embedding_function=embedding_function
    )

    results = db.similarity_search_with_score(query, k=k)

    if not results:
        raise RuntimeError("❌ No relevant knowledge found in Chroma")

    context = "\n\n---\n\n".join(doc.page_content for doc, _ in results)

    sources = [
        f"{doc.metadata.get('source', 'Unknown')} - page {doc.metadata.get('page', '?')}"
        for doc, _ in results
    ]

    print("\nSources:")
    for s in sources:
        print(f"- {s}")

    return context, sources


def extract_driver_keywords(drivers: dict) -> str:
    """
    Extracts keywords from architectural drivers for RAG queries.
    """
    keywords = []

    for qa in drivers.get("quality_attribute_scenarios", []):
        keywords.extend([
            qa.get("attribute", ""),
            qa.get("stimulus", ""),
            qa.get("response", "")
        ])

    for fd in drivers.get("functional_drivers", []):
        keywords.append(fd.get("description", ""))

    return " ".join(k for k in keywords if k)



def generate_architecture_yaml(data: dict) -> dict:
    """
    Generates a YAML-ready architecture description from the architecture_result JSON.

    Conforms to ISO/IEC/IEEE 42010 views and ADD-produced artifacts.
    """

    output = {"architectures": []}

    # Iterate over candidate architectures
    for arch in data.get("candidate_architectures", []):
        arch_name = arch.get("name")
        arch_style = arch.get("style")

        # Component decomposition for this architecture
        comp_decomp = next(
            (cd for cd in data.get("component_decompositions", [])
             if cd.get("name") == arch_name),
            {}
        )

        views_decomp = comp_decomp.get("views", {})

        # Components
        components = []
        for c in views_decomp.get("component_view", {}).get("components", []):
            components.append({
                "id": c.get("id"),
                "type": c.get("type"),
                "responsibilities": c.get("responsibilities", []),
                "interfaces": {
                    "provided": [
                        {
                            "name": i.get("name"),
                            "protocol": i.get("protocol")
                        } for i in c.get("interfaces", {}).get("provided", [])
                    ],
                    "required": [
                        {
                            "name": i.get("name"),
                            "protocol": i.get("protocol")
                        } for i in c.get("interfaces", {}).get("required", [])
                    ]
                }
            })

        # Connectors
        connectors = []
        for conn in views_decomp.get("component_view", {}).get("connectors", []):
            connectors.append({
                "from": conn.get("source") or conn.get("from"),
                "to": conn.get("target") or conn.get("to"),
                "interaction": {
                    "style": conn.get("style", "synchronous"),
                    "connector_type": conn.get("type") or conn.get("connector_type", "assembly"),
                    "protocol": conn.get("protocol", "HTTP"),
                    "semantics": conn.get("semantics", "request-response")
                }
            })

        # Architectural views
        arch_views = next(
            (v for v in data.get("architectural_views", [])
             if v.get("architecture_id") == arch_name),
            {}
        )

        views = arch_views.get("views", {})

        # Deployment view
        dep_view = views.get("deployment_view", {})
        nodes = dep_view.get("nodes", [])
        component_mapping = dep_view.get("component_mapping", {})

        # Communication paths derived from connectors
        communication_paths = []
        for conn in connectors:
            from_node = component_mapping.get(conn["from"])
            to_node = component_mapping.get(conn["to"])

            if from_node and to_node and from_node != to_node:
                communication_paths.append({
                    "from_node": from_node,
                    "to_node": to_node,
                    "connector_type": conn["interaction"]["connector_type"],
                    "protocol": conn["interaction"]["protocol"],
                    "semantics": conn["interaction"]["semantics"]
                })

        output["architectures"].append({
            "architecture_id": arch_name.replace(" ", "_")[:8].upper(),
            "name": arch_name,
            "style": arch_style if isinstance(arch_style, list) else [arch_style],
            "supported_quality_attributes": arch.get("supported_quality_attributes", []),
            "main_risks": arch.get("main_risks", []),
            "rationale": arch.get("rationale", ""),
            "uml_standard": comp_decomp.get("uml_standard", "OMG UML 2.5.1"),
            "views": {
                "component_view": {
                    "components": components,
                    "connectors": connectors
                },
                "deployment_view": {
                    "nodes": nodes,
                    "communication_paths": communication_paths
                },
                "context_view": views.get("context_view", {}),
                "logical_view": views.get("logical_view", {}),
                "runtime_view": views.get("runtime_view", {}),
                "security_view": views.get("security_view", {})
            }
        })

    return output

from typing import Any, List, Tuple, Dict
import matplotlib.pyplot as plt
import networkx as nx
import yaml, re
from pathlib import Path
from copy import deepcopy

def build_context_with_sources(docs: List[Any]) -> Tuple[str, str]:
    context_parts = []
    sources = []

    for doc in docs:
        context_parts.append(doc.page_content)
        file_name = doc.metadata.get("source", "sconosciuto")
        page = doc.metadata.get("page", "N/A")
        sources.append(f"{file_name} (pagina {page})")

    context_text = "\n\n".join(context_parts)
    sources_text = "\n".join(sources)
    return context_text, sources_text

def clean_agent_output(text: str) -> str:
    """
    Rimuove fence markdown ```yaml / ``` e spazi inutili.
    """
    text = text.strip()

    # rimuove apertura ``` o ```yaml (con spazi/newline)
    text = re.sub(r"^```(?:yaml)?\s*", "", text, flags=re.IGNORECASE)

    # rimuove chiusura ```
    text = re.sub(r"\s*```$", "", text)

    return text.strip()

def return_result_save_yaml(response, output_file):
    raw_content = response.messages[-1].content
    cleaned_content = clean_agent_output(raw_content)

    try:
        qa_drivers = yaml.safe_load(cleaned_content)
    except Exception as e:
        print(f"Errore parsing YAML: {e}")
        qa_drivers = []

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(qa_drivers, f, allow_unicode=True, sort_keys=False)

    return qa_drivers

# ============================================================
# Inizio utils per Step 1
# ============================================================

class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True
    
def build_component_graph(arch):
    """
    Costruisce un grafo NetworkX dai componenti e connector dell'architettura.
    """
    G = nx.DiGraph()
    components = arch['views']['component_view']['components']
    
    # Aggiungi nodi
    for comp in components:
        G.add_node(comp['id'], **{
            'type': comp['type'],
            'responsibilities': comp['responsibilities'],
            'interfaces': comp['interfaces']
        })
    
    # Aggiungi archi dai connector
    for conn in arch['views']['component_view'].get('connectors', []):
        G.add_edge(
            conn['from'],
            conn['to'],
            **conn['interaction']
        )
    return G

def show_graph(normalized_output):
    for arch in normalized_output['normalized_architectures']:
        G = arch['component_graph']
        plt.figure(figsize=(8,6))
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color='skyblue', node_size=1500, arrows=True)
        edge_labels = {(u, v): d['protocol'] for u, v, d in G.edges(data=True)}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
        plt.title(f"Architecture {arch['architecture_id']} Component Graph")
        plt.show()

def save_normalized_input(
    normalized_input,
    filename="ST1_normalized_input.yaml",
    folder="agent_outputs"
):
    """
    Salva l'input normalizzato in un file YAML strutturato.
    """

    Path(folder).mkdir(parents=True, exist_ok=True)
    filepath = Path(folder) / filename

    # Deep copy per sicurezza
    output_to_save = deepcopy(normalized_input)

    # Serializzazione esplicita del grafo
    for arch in output_to_save['normalized_architectures']:
        G = arch.pop('component_graph', None)
        if G is not None:
            arch['component_graph_nodes'] = [
                {"id": n, **d} for n, d in G.nodes(data=True)
            ]
            arch['component_graph_edges'] = [
                {"from": u, "to": v, **d} for u, v, d in G.edges(data=True)
            ]

    # Scrittura YAML SENZA alias
    with open(filepath, "w") as f:
        yaml.dump(
            output_to_save,
            f,
            sort_keys=False,
            Dumper=NoAliasDumper
        )

    print(f"Normalized input salvato in {filepath}")

def extract_other_info(input_yaml):
    """
    Estrae le sezioni contestuali dal file di input architetturale
    secondo ISO/IEC/IEEE 42010 e ATAM Phase 1.

    Argomenti:
    - input_yaml: stringa YAML o dict già caricato

    Ritorna:
    - context
    - stakeholders
    - functional_requirements
    - non_functional_requirements
    - constraints
    """

    # Parsing input
    if isinstance(input_yaml, str):
        input_data = yaml.safe_load(input_yaml)
    else:
        input_data = deepcopy(input_yaml)

    # Estrazione esplicita delle sezioni
    context = input_data.get("context", {})
    stakeholders = input_data.get("stakeholders", [])
    functional_requirements = input_data.get("functional_requirements", [])
    non_functional_requirements = input_data.get("non_functional_requirements", {})
    constraints = input_data.get("constraints", {})

    return (
        context,
        stakeholders,
        functional_requirements,
        non_functional_requirements,
        constraints
    )

# ============================================================
# Fine utils per Step 1
# ============================================================


# ============================================================
# Inizio utils per Step 4
# ============================================================

def extract_drivers_info(QA_drivers, QA_candidates):
    """
    Restituisce un dizionario con le informazioni dei driver QA

    Argomenti:
    - QA_drivers: lista di driver QA (step 3)
    - QA_candidates: lista di candidati QA (step 2)

    Ritorna:
    - Dizionario con informazioni sui driver
    """
    drivers_info = {}

    for driver in QA_drivers:
        driver_name = driver.get("quality_attribute")
        if not driver_name:
            continue
        
        # Trova il candidato corrispondente
        candidate = next(
            (c for c in QA_candidates if c.get("name") == driver_name), 
            None
        )

        if candidate:
            drivers_info[driver_name] = candidate
        
    return drivers_info

# ============================================================
# Fine utils per Step 4
# ============================================================


# ============================================================
# Inizio utils per Step 5
# ============================================================

def calculate_coupling(nodes: List[Dict], edges: List[Dict]):
    """
    Coupling: numero di dipendenze uscenti per componente

    Argomenti:
    - nodes: lista di nodi del grafo (componenti)
    - edges: lista di archi del grafo (dipendenze)

    Ritorna:
    - Dizionario con coupling per componente e metriche aggregate
    """
    
    coupling = {}
    for node in nodes:
        comp_id = node['id']
        # conta gli edge uscenti da questo componente
        coupling[comp_id] = sum(1 for e in edges if e['from'] == comp_id)

    # media delle dipendenze uscenti tra i componenti
    coupling["average_coupling"] = round(sum(coupling.values()) / len(nodes) if nodes else 0, 2)
    # numero massimo di dipendenze uscenti tra i componenti
    coupling["max_coupling"] = max(coupling.values()) if nodes else 0
    # normalizzazione tra 0 e 1
    coupling["normalized_coupling"] = round(coupling["max_coupling"] / (len(nodes) - 1) if len(nodes) > 1 else 0, 2)
    return coupling

def calculate_fan_in(nodes: List[Dict], edges: List[Dict]):
    """
    Fan-in: numero di dipendenze entranti per componente
    Argomenti:
    - nodes: lista di nodi del grafo (componenti)
    - edges: lista di archi del grafo (dipendenze)

    Ritorna:
    - Dizionario con fan-in per componente e metriche aggregate
    """

    fan_in = {}

    for node in nodes:
        comp_id = node['id']
        # conta gli edge entranti verso questo componente
        fan_in[comp_id] = sum(1 for e in edges if e['to'] == comp_id)

    # numero massimo di dipendenze entranti tra i componenti
    max_fan_in = max(fan_in.values()) if nodes else 0
    # quanto è centralizzato il componente più dipendente rispetto al massimo teorico
    fan_in_norm = max_fan_in / (len(nodes) - 1) if len(nodes) > 1 else 0
    # quanto il traffico dipende da un singolo componente [0,1]
    fan_in_concentration = max_fan_in / sum(fan_in.values()) if sum(fan_in.values()) > 0 else 0
    
    fan_in['normalized_fan_in'] = round(fan_in_norm, 2)
    fan_in['fan_in_concentration'] = round(fan_in_concentration, 2)
    fan_in['max_fan_in'] = max_fan_in
    
    return fan_in

def calculate_fan_out(nodes: List[Dict], edges: List[Dict]):
    """
    Fan-out: numero di dipendenze uscenti per componente
    Argomenti:
    - nodes: lista di nodi del grafo (componenti)
    - edges: lista di archi del grafo (dipendenze)
    Ritorna:
    - Dizionario con fan-out per componente e metriche aggregate
    """

    fan_out = {}

    for node in nodes:
        comp_id = node['id']
        # edge uscenti verso altri componenti
        fan_out[comp_id] = sum(1 for e in edges if e['from'] == comp_id)

    # numero massimo di dipendenze uscenti tra i componenti
    max_fan_out = max(fan_out.values()) if nodes else 0
    # quanto è centralizzato il componente più dipendente rispetto al massimo teorico
    fan_out_norm = max_fan_out / (len(nodes) - 1) if len(nodes) > 1 else 0
    # Quanto la complessità dipendenziale è concentrata in un singolo componente [0,1]
    fan_out_concentration = max_fan_out / sum(fan_out.values()) if sum(fan_out.values()) > 0 else 0

    fan_out['normalized_fan_out'] = round(fan_out_norm, 2)
    fan_out['fan_out_concentration'] = round(fan_out_concentration, 2)
    fan_out['max_fan_out'] = max_fan_out

    return fan_out

def calculate_component_count(nodes: List[Dict]) -> int:
    """
    Conta il numero di componenti nel sistema.
    
    Argomenti:
    - nodes: lista di nodi del grafo (componenti)
    Ritorna:
    - Numero di componenti
    """
    return len(nodes)

def calculate_cohesion(nodes: List[Dict]) -> Dict[str, float]:
    """
    Cohesion: misura di coesione interna dei componenti basata sulle responsabilità
    Argomenti:
    - nodes: lista di nodi del grafo (componenti)
    Ritorna:
    - Dizionario con coesione per componente e metriche aggregate
    """

    cohesion = {}
    
    for node in nodes:
        resp = node.get('responsibilities', [])
        # proxy: coesione = 1 se una sola responsabilità, altrimenti rapporto
        if len(resp) <= 1:
            cohesion[node['id']] = 1.0
        else:
            # qui potremmo calcolare similarità tra responsabilità (semantica)
            cohesion[node['id']] = 1.0 / len(resp)

    # media della coesione tra i componenti
    avg_cohesion = sum(cohesion.values()) / len(nodes) if nodes else 0
    # coesione minima
    min_cohesion = min(cohesion.values()) if nodes else 0

    cohesion['average_cohesion'] = round(avg_cohesion, 2)
    cohesion['min_cohesion'] = round(min_cohesion, 2)

    return cohesion

def calculate_complexity(nodes: List[Dict], edges: List[Dict]):
    """
    Complexity: misura complessiva della complessità dell'architettura
    Argomenti:
    - nodes: lista di nodi del grafo (componenti)
    - edges: lista di archi del grafo (dipendenze)
    Ritorna:
    - Dizionario con metriche di complessità
    """

    complexity = {}

    complexity['tot_complexity'] =  len(nodes) + len(edges)
    complexity['norm_complexity'] = round(complexity['tot_complexity'] / (len(nodes)*(len(nodes)-1)) if len(nodes) >1 else 0,2)

    return complexity 

def calculate_redundancy(nodes: List[Dict], deployment_nodes: List[Dict]):
    """
    Redundancy: numero di deployment nodes aggiuntivi in cui è presente ciascun componente
    (esclude il primo nodo come base)
    Argomenti:
    - nodes: lista di componenti
    - deployment_nodes: lista di nodi di deployment con componenti distribuiti

    Ritorna:
    - Dizionario con ridondanza per componente e metriche aggregate
    """
    
    redundancy = {}
    redundancy_values = []

    for node in nodes:
        comp_id = node['id']
        # conta in quanti deployment nodes è presente questo componente
        deployed_count = sum(1 for d in deployment_nodes if comp_id in d.get('deployed_components', []))
        # sottraiamo 1 perché il primo nodo non è ridondanza
        redundant_count = max(deployed_count - 1, 0)
        redundancy[comp_id] = redundant_count
        redundancy_values.append(redundant_count)

    # metriche aggregate
    max_redundancy = max(redundancy_values) if redundancy_values else 0
    avg_redundancy = sum(redundancy_values) / len(nodes) if nodes else 0
    # normalizzazione rispetto al numero massimo teorico di deployment nodes aggiuntivi
    normalized_avg = avg_redundancy / (len(deployment_nodes) - 1) if len(deployment_nodes) > 1 else 0
    normalized_max = max_redundancy / (len(deployment_nodes) - 1) if len(deployment_nodes) > 1 else 0

    redundancy['normalized_avg_redundancy'] = round(normalized_avg, 2)
    redundancy['normalized_max_redundancy'] = round(normalized_max, 2)
    
    return redundancy

# ============================================================
# Fine utils per Step 5
# ============================================================

# ============================================================
# Inizio utils per Step 6
# ============================================================

OBJECTIVES = {
    "normalized_coupling": "min",
    "normalized_fan_out": "min",
    "normalized_fan_in": "min",
    "norm_complexity": "min",
    "average_cohesion": "max",
    "normalized_avg_redundancy": "max",
}

def extract_objectives(architectures: Dict[str, Dict]) -> Dict[str, Dict[str, float]]:
    """
    Estrae solo le metriche rilevanti per la Pareto analysis.

    Argomenti:
    - architectures: dict {arch_id: metrics}

    Ritorna:
    - dict {arch_id: {objective_name: value}}
    """

    extracted = {}

    for arch_id, metrics in architectures.items():
        extracted[arch_id] = {
            "normalized_coupling": metrics["coupling"]["normalized_coupling"],
            "normalized_fan_out": metrics["fan_out"]["normalized_fan_out"],
            "normalized_fan_in": metrics["fan_in"]["normalized_fan_in"],
            "norm_complexity": metrics["complexity"]["norm_complexity"],
            "average_cohesion": metrics["cohesion"]["average_cohesion"],
            "normalized_avg_redundancy": metrics["redundancy"]["normalized_avg_redundancy"],
        }

    return extracted

def dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
    """
    Ritorna True se a domina b secondo Pareto dominance.
    """

    better_in_at_least_one = False

    for metric, direction in OBJECTIVES.items():
        if direction == "min":
            if a[metric] > b[metric]:
                return False
            if a[metric] < b[metric]:
                better_in_at_least_one = True
        else:  # max
            if a[metric] < b[metric]:
                return False
            if a[metric] > b[metric]:
                better_in_at_least_one = True

    return better_in_at_least_one

def compare_objectives(a_obj, b_obj):
    """
    Confronta due vettori di obiettivi tenendo conto
    dell'orientamento (min / max) di ciascuna metrica.
    """
    better = []
    worse = []
    equal = []

    for metric, direction in OBJECTIVES.items():
        a_val = a_obj[metric]
        b_val = b_obj[metric]

        if a_val == b_val:
            equal.append(metric)
            continue

        if direction == "min":
            if a_val < b_val:
                better.append(metric)
            else:
                worse.append(metric)

        elif direction == "max":
            if a_val > b_val:
                better.append(metric)
            else:
                worse.append(metric)

        else:
            raise ValueError(f"Unknown objective direction: {direction}")

    return {
        "better_on": better,
        "worse_on": worse,
        "equal_on": equal
    }

# ============================================================
# Fine utils per Step 6
# ============================================================

# ============================================================
# Inizio utils per Step 7
# ============================================================

METRIC_TO_QA = {
    "normalized_coupling": ["modifiability", "maintainability"],
    "normalized_fan_out": ["modifiability", "testability"],
    "normalized_fan_in": ["availability", "reliability"],
    "norm_complexity": ["maintainability", "testability"],
    "average_cohesion": ["modifiability", "understandability"],
    "normalized_avg_redundancy": ["availability", "reliability"]
}

def filter_evaluations_by_arch_ids(evaluations: dict, arch_ids: list) -> dict:
    """
    Ritorna un sotto-dizionario di evaluations contenente
    solo le architetture con id in arch_ids.
    """
    return {
        arch_id: evaluations[arch_id]
        for arch_id in arch_ids
        if arch_id in evaluations
    }

def get_not_in_pareto_front(multi_objective_comparison, evaluations):
    pareto = set(multi_objective_comparison["pareto_front"])
    return {
        arch_id: evaluations[arch_id]
        for arch_id in evaluations
        if arch_id not in pareto
    }

def metrics_to_quality_attributes(metrics: list):
    qa = set()
    for m in metrics:
        qa.update(METRIC_TO_QA.get(m, []))
    return list(qa)

def comparing_pareto_front(pareto, evaluations):
    """
    Confronta tutte le architetture nel Pareto front
    e ritorna una lista di PRO tra coppie di architetture.
    Argomenti:
    - pareto: architetture nel Pareto front
    - evaluations: dizionario {arch_id: metrics}
    Ritorna:
    - lista di PRO tra coppie di architetture nel Pareto front
    """
    comparison_list = []

    pareto_evaluations = filter_evaluations_by_arch_ids(evaluations, pareto)
    objectives = extract_objectives(pareto_evaluations)

    arch_ids = list(objectives.keys())
    comparison_id = 1

    for i, arch_a in enumerate(arch_ids):
        for arch_b in arch_ids[i + 1:]:

            a_obj = objectives[arch_a]
            b_obj = objectives[arch_b]

            comparison = compare_objectives(a_obj, b_obj)

            comparison_list.append({
                "id": comparison_id,
                "arch_A": arch_a,
                "arch_B": arch_b,
                "PRO_A_attributes": metrics_to_quality_attributes(comparison["better_on"]),
                "PRO_A_metrics": comparison["better_on"],
                "PRO_B_attributes": metrics_to_quality_attributes(comparison["worse_on"]),
                "PRO_B_metrics": comparison["worse_on"],
                "NEUTRAL": metrics_to_quality_attributes(comparison["equal_on"])
            })

            comparison_id += 1

    return comparison_list

def identify_tradeoffs(comparisons, scenario_simulations):
    """
    Arricchisce i tradeoff strutturali con le evidenze sugli scenari.

    Args:
        comparison (list[dict]): output di tradeoff_analysis
        scenario_simulations (dict): simulazione scenari per architettura

    Returns:
        list[dict]: tradeoff arricchiti con scenario_evidence
    """

    enriched_tradeoffs = []

    # shortcut utile
    evaluations = scenario_simulations["scenario_simulation"]["evaluations"]

    for comp in comparisons:
        arch_a = comp["arch_A"]
        arch_b = comp["arch_B"]

        scenario_evidence = {
            arch_a: evaluations.get(arch_a, {}),
            arch_b: evaluations.get(arch_b, {})
        }

        enriched_tradeoffs.append({
            **comp,
            "scenario_evidence": scenario_evidence
        })

    return enriched_tradeoffs

def merge_tradeoff_evidence(tradeoffs, evidence_tradeoffs):

    if len(tradeoffs) != len(evidence_tradeoffs):
        raise ValueError("Le due liste devono avere la stessa lunghezza")
    
    for tradeoff_obj, evidence_obj in zip(tradeoffs, evidence_tradeoffs):
        tradeoff_obj["tradeoff"] = evidence_obj["tradeoff"]
        tradeoff_obj["tradeoff_rationale"] = evidence_obj["rationale"]

    return tradeoffs


# ============================================================
# Fine utils per Step 7
# ============================================================

# ============================================================
# Inizio utils per evoluzione
# ============================================================

def inject_failures(workflow, prompt, err_subject):
    """
    Inserisce nel prompt i feedback relativi ai fallimenti precedenti
    in base all'err_subject, che può essere 'DRIVER', 'TRADEOFF_RATIONALE' o 'SCENARIO'.
    """

    # Mappa tra err_subject e campi nella memoria
    subject_flag_map = {
        "DRIVER": ("is_drivers_problem", "drivers", "driver selection"),
        "TRADEOFF_RATIONALE": ("is_tradeoff_rationale_problem", "tradeoff_rationale", "tradeoff rationale"),
        "SCENARIO": ("is_scenarios_problem", "scenarios", "scenario evidence")
    }

    if err_subject not in subject_flag_map:
        raise ValueError(f"err_subject '{err_subject}' non supportato. Deve essere uno tra DRIVER, TRADEOFF_RATIONALE, SCENARIO.")

    flag_field, explanation_field, human_readable_name = subject_flag_map[err_subject]

    # Controllo se siamo in una iterazione successiva alla prima
    if workflow.get("iteration", 1) > 1:
        # Carica la memoria dell'agente
        with open("agent_memory/memory.yaml", "r", encoding="utf-8") as f:
            memory = yaml.safe_load(f)

        previous_failures = memory.get("previous_failures", [])
        issues_texts = []

        for failure in previous_failures:
            response = failure.get("response", {})
            rationale = response.get("rationale", {})

            # Controlla se la flag corrispondente all'err_subject è YES
            if rationale.get(flag_field, "NO").upper() == "YES":
                tradeoff_id = rationale.get("tradeoff-id", "UNKNOWN")
                explanation_text = rationale.get(explanation_field, "")

                text = (
                    f"Trade-off {tradeoff_id} has issues with {human_readable_name}:\n"
                    f"{explanation_text}\n"
                    f"Please consider this when evaluating new trade-offs."
                )
                issues_texts.append(text)

        if issues_texts:
            feedback_section = "\n\n".join(issues_texts)
            # Concatenazione al prompt
            prompt += "\n\n" + feedback_section

    else:
        print("\n NESSUN FAILURE\n")

    return prompt


# # ============================================================
# Fine utils per evoluzione
# ============================================================

import agents.utils as utils
from autogen_agentchat.agents import AssistantAgent
from copy import deepcopy
import textwrap, yaml
from rag.kb import KnowledgeBase

class TradeOffAgent:
    def __init__(self, model_client):

        self.agent = AssistantAgent(
            name="tradeoff_agent",
            model_client=model_client,
            system_message=("""
You are an agent that supports the analysis of software architectures.
You operate by extracting and structuring information from inputs and authoritative
knowledge sources, without introducing assumptions or making design decisions.
"""
            )
        )

        self.workflow = {
            "continue": True,
            "iteration": 0
        }
    
    def step1_normalize_input(self, input_yaml):
        """
        Argomenti:
        - input_yaml: stringa o dict contenente il file YAML di input
        
        Ritorna:
        - dict con architetture normalizzate e grafo dei componenti
        """
        # Carica YAML se necessario
        if isinstance(input_yaml, str):
            input_data = yaml.safe_load(input_yaml)
        else:
            input_data = deepcopy(input_yaml)
        
        normalized_architectures = []

        for arch in input_data.get('architectures', []):
            # Creazione grafo componenti/connectors
            graph = utils.build_component_graph(arch)

            # Output minimal, senza arricchimento o verifica
            normalized_architectures.append({
                'architecture_id': arch['architecture_id'],
                'name': arch['name'],
                'style': arch['style'],
                'uml_standard': arch['uml_standard'],
                'views': deepcopy(arch['views']),
                'component_graph': graph
            })

        normalized_input = {'normalized_architectures': normalized_architectures}

        utils.save_normalized_input(normalized_input)

        return normalized_input

    async def step2_qa_elicitation(self, non_functional_requirements):
        """
        Argomenti:
        - non_functional_requirements: dict dei requisiti non funzionali

        Ritorna:
        - qa_candidates: lista di QA candidati come dict {name, rationale, ...}
        """

        kb = KnowledgeBase(vector_dir="chroma/step2", k=15)

        # 1. Prepara query testuale per la KB
        query = (
        "- quality attribute and its sub-characteristics, "
        "- typical measurable metrics or acceptance criteria, "
        "- examples derived from real system requirements or architectures, "
        "- any architectural tactics or patterns used to achieve the attribute. "
        )

        # 2. Recupera documenti rilevanti dalla KB
        docs = kb.retrieve(query)

        # 3. Costruisci contesto testuale con fonti
        context_text, sources_text = utils.build_context_with_sources(docs)

        # 4. Prompt per l'agente
        prompt = f"""
Your task is to identify and classify candidate Quality Attributes (QA)
based ONLY on the explicitly stated non-functional requirements.

You are provided with:
- Non-functional requirements expressed by stakeholders
- Contextual excerpts from an authoritative knowledge base
  (ISO/IEC 25010, Software Architecture in Practice)

MANDATORY RULES:

1. One-to-one correspondence:
   - EACH non-functional requirement (NFR) MUST be mapped to EXACTLY ONE Quality Attribute.
   - NO NFR may be omitted.
   - DO NOT merge multiple NFRs under a single QA entry.
   - If multiple NFRs map to the same ISO/IEC 25010 quality attribute name,
     they MUST still be represented as separate QA entries, each with its own NFR_id.

2. Scope limitation:
   - Identify ONLY quality attributes that are EXPLICITLY present in the input NFRs.
   - DO NOT infer, derive, or introduce additional quality attributes.

3. Metrics completeness:
   - ALL metrics, thresholds, constraints, and measurable criteria explicitly stated
     in each NFR MUST be included in the corresponding QA metrics.
   - DO NOT omit or summarize metrics.
   - DO NOT introduce metrics that are not present in the input.

Use the knowledge base context ONLY to:
- correctly name and classify quality attributes according to ISO/IEC 25010
- support terminology and definitions
- provide normative references

DO NOT:
- invent new QA
- merge NFRs
- add interpretations beyond the stated requirements

Context from knowledge base:
{context_text}

Non-functional requirements:
{str(non_functional_requirements)}

Output format: YAML

IMPORTANT:
- Use only double quotes (") for values after ':'.
- Never use single quotes (').
- Output MUST be strictly valid YAML.
- Do NOT include Markdown formatting, headings, explanations, or notes.

Required structure:

quality_attributes:
  - name: "attribute_name_as_per_ISO_IEC_25010"
    priority: "priority_from_input"
    NFR_id: "exact_id_from_input"
    metrics:
      - name: "metric_name"
        measures:
          measure_name: "exact_measure_or_constraint_from_input"
"""

        # 5. Chiamata all'agente
        response = await self.agent.run(task=prompt)
        await self.agent.on_reset(cancellation_token=None)

        # 6. Estrai e salva output YAML
        qa_candidates = utils.return_result_save_yaml(response, "agent_outputs/ST2_qa_candidates.yaml")

        return qa_candidates, sources_text

    async def step3_driver_analysis(self, qa_candidates, constraints, context, stakeholders):
        """
        Argomenti:
        - qa_candidates: lista di QA candidati come dict (output step 2)
        - constraints: vincoli architetturali
        - context: contesto del sistema
        - stakeholders: elenco degli stakeholder

        Ritorna:
        - QA_drivers: lista di driver selezionati come dict {name, rationale, influencing_factors, related_stakeholders, related_constraints}
        """

        kb = KnowledgeBase(vector_dir="chroma/step3", k=15)

        query = (
            "architectural drivers identification sensitivity points "
            "quality attribute trade-off evaluation cost benefit "
            "quantifying architectural decisions impact analysis"
        )

        docs = kb.retrieve(query)

        kb_context, sources_text = utils.build_context_with_sources(docs)

        prompt = f"""
Your task is to propose candidate Quality Attribute Drivers based on the provided inputs.

A Quality Attribute Driver is:
- a quality attribute that has **high architectural significance**
- **critical to business or mission success**
- **difficult to achieve**, or in strong **tension with other quality attributes**
- one that is likely to **shape or constrain major architectural decisions**

IMPORTANT:
Quality Attribute Drivers are a **strict subset** of the provided Quality Attributes.
NOT ALL Quality Attributes are drivers.

You MUST:
- select ONLY those Quality Attributes that plausibly qualify as architectural drivers
- exclude Quality Attributes that have limited architectural impact
- include in the output ONLY the Quality Attributes identified as drivers

You MUST NOT:
- include all Quality Attributes by default
- mention or explain Quality Attributes that are not selected as drivers

Your role is to highlight and justify potential candidates only.

You are provided with:

1. Candidate Quality Attributes:
{qa_candidates}

2. Architectural Constraints:
{constraints}

3. System Context:
{context}

4. Stakeholders and their concerns:
{stakeholders}

5. Context from the Knowledge Base (ATAM, CBAM):
{kb_context}

### How to perform the analysis:

Evaluate the candidate Quality Attributes and identify ONLY those that:
- have **system-wide architectural impact**
- introduce **significant trade-offs or sensitivity points**
- are strongly aligned with **stakeholder concerns**
- are constrained or amplified by architectural or organizational constraints

You MUST propose no fewer than 3 and no more than 7 candidate Quality Attribute Drivers. 
Stay in this range.

Use the knowledge base context ONLY to:
- support ATAM terminology (driver, trade-off, sensitivity point)
- justify why an attribute may be architecturally significant

DO NOT:
- invent new quality attributes
- introduce new requirements
- assume architectural solutions
- rank or select final drivers

### Output format (STRICT YAML ONLY):

The YAML output MUST contain ONLY the Quality Attributes identified as drivers.
Do NOT include entries for non-driver Quality Attributes.

candidate_drivers:
  - quality_attribute: "QA name"
    rationale: "Why this QA is a potential architectural driver (max 80 words)"
    influencing_factors:
      - "factor description (max 30 words)"
      - "factor description (max 30 words)"
    related_stakeholders:
      - "stakeholder role"
    related_constraints:
      - "constraint identifier or description"

IMPORTANT:
- Use only double quotes (") for all string values
- Do not use Markdown
- Do not include explanations outside the YAML
        """

        utils.inject_failures(self.workflow, prompt, "DRIVER")

        print(prompt)
        
        response = await self.agent.run(task=prompt)
        await self.agent.on_reset(cancellation_token=None)

        qa_drivers = utils.return_result_save_yaml(response, "agent_outputs/ST3_qa_drivers.yaml")

        return qa_drivers, sources_text

    # va aggiustato il prompt, gli scenari devono essere neutrali e non descrivere soluzioni
    async def step4_scenario_generation(self, QA_drivers_info, context, stakeholders, constraints):
        """
        Argomenti:
        - qa_drivers: lista di driver selezionati come dict (output step 3)
        - context: contesto del sistema
        - stakeholders: elenco degli stakeholder
        - constraints: vincoli

        Ritorna:
        - scenarios: lista di scenari generati come dict {related_driver, stimulus, environment, response, response_measure}
        """

        kb = KnowledgeBase(vector_dir="chroma/step4", k=20)

        drivers_str = [f"{driver_name}" for driver_name, driver in QA_drivers_info.items()]
        query = (
            "quality attribute scenarios, stimulus, environment, response, response measure, "
            "real system case studies, "
            "software architecture, e-commerce backend, "
            f"{drivers_str}"
        )

        docs = kb.retrieve(query)

        kb_context, sources_text = utils.build_context_with_sources(docs)

        scenarios = {}

        for driver_name, driver in QA_drivers_info.items():

            print(f"""\nSIAMO NEL FOR PER IL DRIVER {driver_name}\n""")
            print(driver)

            prompt = f"""
Your task is to perform a Scenario-Based Analysis for a single Quality Attribute Driver according to ATAM / SAAM principles.

A Quality Attribute Scenario is a structured description composed of:
- stimulus
- environment
- response
- response_measure

Your goal is to generate a small set of representative, architecturally significant quality attribute scenarios that will be used in later ATAM evaluation steps.

You MUST strictly follow ATAM scenario semantics.

You MUST NOT:
- propose architectural solutions, tactics, patterns, or technologies
- mention specific mechanisms, tools, or implementations (e.g., auto-scaling, OAuth, MFA, load balancers, replicas)
- describe the failure itself as the system response
- restate requirements, goals, or quality targets as responses
- introduce new quality attributes
- mix multiple drivers in the same scenario
- assume that the system already satisfies the driver

You are provided with:

1. Quality Attribute Driver:
{driver}

2. System Context:
{context}

3. Stakeholders and their concerns:
{stakeholders}

4. Architectural Constraints:
{constraints}

5. Knowledge Base Context (ATAM / SAAM scenario examples):
{kb_context}

### How to generate scenarios (MANDATORY):

Generate 2–3 quality attribute scenarios for this driver.

Each scenario MUST:
- be explicitly and exclusively tied to the given driver
- represent a realistic situation that could stress or challenge the architecture
- expose uncertainty, risk, trade-offs, or sensitivity points
- be suitable for architectural evaluation (not validation or testing)

Scenarios SHOULD describe situations where:
- the driver is difficult to satisfy
- trade-offs with other drivers may emerge
- architectural decisions will significantly influence the outcome

### STRICT ATAM SEMANTIC RULES (DO NOT VIOLATE):

- Stimulus:
  - Describes an internal or external event that affects the system
  - Must be phrased as a triggering event, not a requirement or goal

- Environment:
  - Describes the operational context at the time of the stimulus
  - May include load conditions, timing, operational mode, or constraints
  - Must NOT describe responses, decisions, or solutions

- Response:
  - Describes the externally observable behavior of the system
  - MUST describe what is observed happening in the system, not an outcome
  - MUST describe behavior under stress, not success or failure
  - MUST NOT describe:
    - architectural tactics or mechanisms
    - control strategies or adaptations
    - technologies or tools
    - numeric thresholds or KPIs

- Response_measure:
  - Describes how the response is measured or observed
  - Must be quantifiable or objectively assessable
  - Must be directly related to the response
  - Must NOT restate the response in different words
  - Must NOT describe implementation details or design choices

### Mental model to follow (MANDATORY):

- The response answers: "What observable behavior does the system exhibit when the stimulus occurs?"
- The response_measure answers: "How do we know this behavior occurred?"

### Examples (FOR CLARITY — DO NOT COPY VERBATIM):

Incorrect scenario fragment (WRONG — DO NOT DO THIS):
- response: "API latency exceeds 500ms and throughput drops below 1,000 req/sec"
- response_measure: "p99 latency > 500ms"

Why this is wrong:
- The response describes a measurement and a failure outcome
- The response and response_measure are semantically overlapping

Correct scenario fragment (RIGHT APPROACH):
- response: "The system exhibits increased request processing delay under concurrent load"
- response_measure: "Observed p99 end-to-end request latency during the peak load window"

### Knowledge base usage:

Use the knowledge base ONLY to:
- follow correct ATAM scenario structure
- ensure proper terminology usage
- ensure scenarios are architecturally meaningful and realistic

### Output format (STRICT YAML ONLY):

scenarios:
  - id: "SC-{driver_name}-N (where N is a sequential number starting from 1)"
    stimulus: "Triggering event affecting the system"
    environment: "Operational context when the stimulus occurs"
    response: "Observable system behavior in response to the stimulus"
    response_measure: "Measurable or observable outcome of the response"

IMPORTANT:
- All list items under 'scenarios:' MUST be indented exactly two spaces.
- Generate ONLY scenarios related to the provided driver.
- Use only double quotes (") for all string values.
- Never use single quotes (').
- Output MUST be strictly valid YAML.
- Do NOT include explanations, comments, headings, or notes outside the YAML.
            """

            utils.inject_failures(self.workflow, prompt, "SCENARIO")

            response = await self.agent.run(task=prompt)
            await self.agent.on_reset(cancellation_token=None)

            scenario = response.messages[-1].content
            cleaned_scenario = utils.clean_agent_output(scenario)

            # per ogni driver, estrai gli scenari generati
            # e salvali in un dict complessivo (scenarios)
            try:
                parsed = yaml.safe_load(cleaned_scenario)
                if parsed and "scenarios" in parsed:
                    scenarios[driver_name] = parsed["scenarios"]
            except Exception as e:
                print(f"Errore parsing YAML per driver {driver_name}: {e}")

            print(f"Scenari generati per driver {driver_name}:\n")
            print(scenarios.get(driver_name, []))

        # salva output completo
        with open("agent_outputs/ST4_scenarios.yaml", "w", encoding="utf-8") as f:
            yaml.dump(scenarios, f, allow_unicode=True, sort_keys=False)

        return scenarios, sources_text

    def step5_metric_based_evaluation(self, architectures):
        """
        Argomenti:
        - architectures: liste di architetture normalizzate (output step 1)

        Ritorna:
        - evaluations: dict contenente vettori di valutazioni su metriche per ogni architettura
        """

        evaluations = {}

        for arch in architectures['normalized_architectures']:
            graph = arch['component_graph']
            nodes = [{'id': n} for n in graph.nodes()]
            edges = [{'from': u, 'to': v} for u, v in graph.edges()]
            deplyoment_nodes = arch['views']['deployment_view']['nodes']

            component_count = utils.calculate_component_count(nodes)
            coupling = utils.calculate_coupling(nodes, edges)
            fan_in = utils.calculate_fan_in(nodes, edges)
            fan_out = utils.calculate_fan_out(nodes, edges)
            cohesion = utils.calculate_cohesion(nodes)
            complexity = utils.calculate_complexity(nodes, edges)
            redundancy = utils.calculate_redundancy(nodes, deplyoment_nodes)

            evaluations[arch['architecture_id']] = {
                'component_count': component_count,
                'coupling': {
                    'per_component': {k: v for k, v in coupling.items() if k not in ['average_coupling', 'normalized_coupling', 'max_coupling']},
                    'average_coupling': coupling['average_coupling'],
                    'normalized_coupling': coupling['normalized_coupling'],
                    'max_coupling': coupling['max_coupling']
                },
                'fan_in': {
                    'per_component': {k: v for k, v in fan_in.items() if k not in ['fan_in_concentration', 'normalized_fan_in', 'max_fan_in']},
                    'normalized_fan_in': fan_in['normalized_fan_in'],
                    'fan_in_concentration': fan_in['fan_in_concentration'],
                    'max_fan_in': fan_in['max_fan_in']
                },
                'fan_out': {
                    'per_component': {k: v for k, v in fan_out.items() if k not in ['fan_out_concentration', 'normalized_fan_out', 'max_fan_out']},
                    'normalized_fan_out': fan_out['normalized_fan_out'],
                    'fan_out_concentration': fan_out['fan_out_concentration'],
                    'max_fan_out': fan_out['max_fan_out']
                },
                'cohesion': {
                    'per_component': {k: v for k, v in cohesion.items() if k not in ['average_cohesion', 'min_cohesion']},
                    'average_cohesion': cohesion['average_cohesion'],
                    'min_cohesion': cohesion['min_cohesion'],
                },
                'complexity': {
                    'tot_complexity': complexity['tot_complexity'],
                    'norm_complexity': complexity['norm_complexity']
                },
                'redundancy': {
                    'per_component': {k: v for k, v in redundancy.items() if k not in ['normalized_avg_redundancy', 'normalized_max_redundancy']},
                    'normalized_avg_redundancy': redundancy['normalized_avg_redundancy'],
                    'normalized_max_redundancy': redundancy['normalized_max_redundancy']
                }
            }

        # salva output
        with open("agent_outputs/ST5_metric_evaluations.yaml", "w", encoding="utf-8") as f:
            yaml.dump(evaluations, f, allow_unicode=True, sort_keys=False)

        return evaluations
        
    def step6_multi_objective_comparison(self, evaluations):
        """
        Calcola il Pareto front dato un insieme di architetture.

        Ritorna:
        - pareto_front: lista di architetture non dominate
        - dominance_info: dettagli di dominanza
        """

        pareto = []
        dominance_info = {}
        objectives = utils.extract_objectives(evaluations)

        for a_id, a_obj in objectives.items():
            dominated = False
            dominance_info[a_id] = {
                "dominates": {},
                "dominated_by": {}
            }

            for b_id, b_obj in objectives.items():
                if a_id == b_id:
                    continue

                if utils.dominates(b_obj, a_obj):
                    dominated = True
                    dominance_info[a_id]["dominated_by"][b_id] = \
                        utils.compare_objectives(a_obj, b_obj)

                elif utils.dominates(a_obj, b_obj):
                    dominance_info[a_id]["dominates"][b_id] = \
                        utils.compare_objectives(a_obj, b_obj)

            if not dominated:
                pareto.append(a_id)

        
        multi_objective_comparison = {
            "pareto_front": pareto,
            "dominance_info": dominance_info
        }

        # salva output
        with open("agent_outputs/ST6_multi_objective_comparison.yaml", "w", encoding="utf-8") as f:
            yaml.dump(multi_objective_comparison, f, allow_unicode=True, sort_keys=False)

        return multi_objective_comparison

    # scenarios non è usato perchè la simulazione delle architetture su scenari è mockata
    async def step7_tradeoff_analysis(self, multi_objective_comparison, scenarios, evaluations):

        pareto_front = multi_objective_comparison["pareto_front"]

        comparasions = utils.comparing_pareto_front(pareto_front, evaluations)

        # simulazione del comportamento delle architetture sugli scenari
        # qui andrebbe integrata una simulazione reale usando scenarios (richiesta a LLM)
        with open("scenario_simulation_results.yaml", "r", encoding="utf-8") as f:
            scenario_simulations = yaml.safe_load(f)

        tradeoffs = utils.identify_tradeoffs(
            comparasions,
            scenario_simulations
        )

        kb = KnowledgeBase(vector_dir="chroma/evolution", k=15)

        query = (            
            "ATAM evaluation criteria for trade-offs, "
            "when architectural trade-offs are insufficient, "
            "quality attribute conflicts and risks, "
            "sensitivity points and architectural decisions, "
            "criteria to iterate architecture trade-off analysis"
        )

        docs = kb.retrieve(query)

        kb_context, sources_text = utils.build_context_with_sources(docs)

        prompt = f"""
You are an architecture evaluation assistant specialized in ATAM-style trade-off analysis.

Your task is to explicitly identify and highlight the main architectural trade-off between two architectures,
using the data provided in the input.

A trade-off is valid ONLY if:
- it involves at least two conflicting Quality Attributes (QA vs QA)
- improving one attribute in one architecture leads to a degradation or limitation of the other in the alternative
- the conflict is supported by scenario evidence, metrics, or qualitative rationale

────────────────────────────────────
Context
────────────────────────────────────
{kb_context}

Use this context only to interpret the data correctly.
Do NOT introduce new trade-offs that are not supported by the input data.

────────────────────────────────────
Input to evaluate
────────────────────────────────────
{tradeoffs}

The input contains:
- the two architectures being compared
- quality attributes classified as PRO_A, PRO_B, or NEUTRAL
- metrics associated with each architecture
- scenario-based evidence with effort, risk, confidence, and rationale

────────────────────────────────────
Instructions:
────────────────────────────────────

1. Analyze the PRO_A, PRO_B, and NEUTRAL quality attributes and metrics.
2. Correlate them with the scenario_evidence for both architectures.
3. Identify the most significant quality attribute conflict that differentiates ARCH_A and ARCH_B.
4. Explicitly express the trade-off in the form "QA vs QA".
5. Provide a concise but clear explanation grounded in the provided evidence (scenarios, rationale, metrics).
6. Do NOT introduce new attributes, assumptions, or external knowledge.
7. If multiple trade-offs exist, select the most architecturally critical one.

────────────────────────────────────
Output format:
────────────────────────────────────

- tradeoff: "<Quality Attribute A> vs <Quality Attribute B>"
  rationale: 
    "<Explain why improving QA A in one architecture negatively impacts QA B in the other,
     referencing concrete scenario evidence, risks, effort, confidence, or architectural characteristics.>"

IMPORTANT RULES:
- Only provide the YAML content itself.
- Do NOT include any markdown, code blocks, headings, or extra text.
- Use only double quotes (") for all string values.
- Output must be strictly valid YAML.
"""

        utils.inject_failures(self.workflow, prompt, "TRADEOFF_RATIONALE")

        response = await self.agent.run(task=prompt)
        await self.agent.on_reset(cancellation_token=None)

        message = utils.clean_agent_output(response.messages[-1].content)

        evidence_tradeoffs = yaml.safe_load(message)

        tradeoffs = utils.merge_tradeoff_evidence(tradeoffs, evidence_tradeoffs)

        # salva output
        with open("agent_outputs/ST7_tradeoff_analysis.yaml", "w", encoding="utf-8") as f:
            yaml.dump(tradeoffs, f, allow_unicode=True, sort_keys=False)

        return tradeoffs

    async def consider_evolution(self, tradeoff_analysis, non_functional_requirements, dev_context, stakeholders, driver_names):
        """
        Decide se ripetere l'analisi dei tradeoff con nuovi driver.
        """

        kb = KnowledgeBase(vector_dir="chroma/evolution", k=15)

        query = (
            "ATAM evaluation criteria for trade-offs, "
            "when architectural trade-offs are insufficient, "
            "quality attribute conflicts and risks, "
            "sensitivity points and architectural decisions, "
            "criteria to iterate architecture trade-off analysis"
        )


        docs = kb.retrieve(query)

        kb_context, sources_text = utils.build_context_with_sources(docs)

        prompt = f"""You are an Architecture Trade-off Evaluation Agent.

Your task is to evaluate whether the provided architectural trade-offs are
SUFFICIENT and SIGNIFICANT, according to established principles from the
Architecture Tradeoff Analysis Method (ATAM) and related architectural evaluation
practices.

You are NOT asked to generate new trade-offs.
You must ONLY evaluate the quality and adequacy of the trade-offs provided.

────────────────────────────────────
DEFINITION OF INSUFFICIENT TRADE-OFF
────────────────────────────────────

A trade-off is considered INSUFFICIENT if one or more of the following hold:
- It does not expose a real conflict between critical quality attributes
- It involves secondary or non-critical quality attributes only
- It does not significantly challenge the architectural decision
- It lacks clear or credible scenario-based evidence
- It does not clearly relate to stakeholder concerns or system context
- It leads to a trivial, obvious, or one-sided architectural choice

If a trade-off is insufficient, the architectural analysis must be iterated.

────────────────────────────────────
KNOWLEDGE BASE CONTEXT (AUTHORITATIVE SOURCES)
────────────────────────────────────

The following excerpts come from authoritative sources (e.g., ATAM, SEI reports)
and define how architectural trade-offs should be evaluated:

{kb_context}

────────────────────────────────────
DEVELOPMENT CONTEXT
────────────────────────────────────

System context, development constraints, and environmental assumptions:

{dev_context}

────────────────────────────────────
STAKEHOLDERS
────────────────────────────────────

Relevant stakeholders and their concerns:

{stakeholders}

────────────────────────────────────
NON-FUNCTIONAL REQUIREMENTS
────────────────────────────────────

The non-functional requirements driving the architectural evaluation:

{non_functional_requirements}

────────────────────────────────────
IDENTIFIED TRADE-OFFS
────────────────────────────────────

Each trade-off compares two architectures and includes scenario-based evidence
linked to specific quality attribute drivers.

{tradeoff_analysis}

────────────────────────────────────
EVALUATION TASK
────────────────────────────────────

Evaluate the trade-offs by assessing their adequacy along THREE independent
dimensions.

You must NOT decide whether the analysis continues or stops.
Your role is limited to diagnosing the quality of the trade-off analysis.

1. DRIVER ADEQUACY
   - Are the selected quality attribute drivers appropriate and critical?
   - Do they reflect stakeholder concerns and system priorities?
   - Do they meaningfully expose architectural risks or weaknesses?

2. TRADEOFF_RATIONALE QUALITY
   - Does the tradeoff_rationale expose a real and non-trivial conflict between
     quality attributes?
   - Does it put the architectural decision under real tension?
   - Would reasonable stakeholders disagree on the preferred architecture?

3. SCENARIO ADEQUACY
   - Are the trade-offs grounded in concrete quality-attribute scenarios?
   - Do scenarios show meaningful differences in effort, risk, or confidence?
   - Is the scenario evidence credible and relevant?

────────────────────────────────────
FAILURE ATTRIBUTION RULE (MANDATORY)
────────────────────────────────────

If the trade-off analysis is INSUFFICIENT, you MUST identify the root cause.

At least ONE of the following MUST be marked as YES if the trade-offs are insufficient:
- is_drivers_problem
- is_tradeoff_rationale_problem
- is_scenarios_problem

Each flag marked as YES indicates that this aspect is responsible for the
weakness or inaccuracy of the trade-off analysis.

For every flag marked as YES, you MUST provide a clear and explicit explanation
justifying why that aspect is problematic.

If the trade-offs are SUFFICIENT and SIGNIFICANT, ALL flags MUST be NO.

────────────────────────────────────
OUTPUT FORMAT (MANDATORY)
────────────────────────────────────

Respond ONLY with a YAML object in the following format:

response:
  rationale:
    tradeoff-id: <tradeoff id being evaluated>
    is_drivers_problem: YES | NO
    is_tradeoff_rationale_problem: YES | NO
    is_scenarios_problem: YES | NO
    drivers: >
      <Explain whether the selected drivers are appropriate or not.
       If is_drivers_problem is YES, explain why the drivers fail to expose
       meaningful architectural tension.>
    tradeoff_rationale: >
      <Explain whether the tradeoff_rationale itself is appropriate or not.
       If is_tradeoff_rationale_problem is YES, explain why the rationale is weak,
       trivial, or not architecturally significant.>
    scenarios: >
      <Explain whether the scenario evidence is appropriate or not.
       If is_scenarios_problem is YES, explain why the scenarios are insufficient,
       unclear, or not convincing.>

Consistency rule (MANDATORY):
You MUST ensure logical consistency between problem flags and explanations.
Any positive evaluation MUST correspond to a NO flag.

        """

        response = await self.agent.run(task=prompt)
        await self.agent.on_reset(cancellation_token=None)

        message = utils.clean_agent_output(response.messages[-1].content)

        evaluation = yaml.safe_load(message)
        evaluation = evaluation["response"]

        rationale = evaluation["rationale"]

        should_continue = any(
            rationale[key] == "YES"
            for key in [
                "is_drivers_problem",
                "is_tradeoff_rationale_problem",
                "is_scenarios_problem",
            ]
        )

        if (should_continue):

            failure = {
                "failure_id" : self.workflow["iteration"],
                "driver_set" : driver_names,
                "rationale" : evaluation.get("rationale")
            }
            
            # l'agente scrive le motivazioni del perchè si continua
            # e salva la memoria aggiornata

            memory = yaml.safe_load(open("agent_memory/memory.yaml", "r", encoding="utf-8"))

            previous_failures = memory.get("previous_failures", [])
            
            if not isinstance(previous_failures, list):
                previous_failures = []
                memory["previous_failures"] = previous_failures

            previous_failures.append(failure)

            with open("agent_memory/memory.yaml", "w", encoding="utf-8") as f:
                yaml.dump(memory, f, allow_unicode=True, sort_keys=False)
        else:
            self.workflow["continue"] = False
            print("\n IL WORKFLOW è TERMINATO \n")


    async def analyze(self, input_yaml):
        
        # step 1:
        normalized_architectures = self.step1_normalize_input(input_yaml)

        # estrai altri dati utili agli step successivi
        (   context,
            stakeholders,
            functional_requirements,
            non_functional_requirements,
            constraints
        ) = utils.extract_other_info(input_yaml)

        # step 2
        # qa_candidates, qa_sources = await self.step2_qa_elicitation(non_functional_requirements)

        # step 2 (mocked per test)
        # prendi l'input
        with open('agent_outputs/ST2_qa_candidates.yaml') as f:
            input_yaml = f.read()
        qa_candidates = yaml.safe_load(input_yaml)

        # processo iterativo identificare driver (da step 3 a step 7)

        
        while self.workflow["continue"]:

            self.workflow["iteration"] += 1

            # step 3
            QA_drivers, QA_drivers_sources = await self.step3_driver_analysis(qa_candidates, constraints, context, stakeholders)

            # step 3 (mocked per test)
            """with open('agent_outputs/ST3_qa_drivers.yaml') as f:
                input_yaml = f.read()  

            QA_drivers = yaml.safe_load(input_yaml)"""

            # recupero le informazioni dei driver per lo step 4
            QA_drivers_info = utils.extract_drivers_info(
                QA_drivers=QA_drivers["candidate_drivers"],
                QA_candidates=qa_candidates["quality_attributes"]
            )

            # step 4
            # scenarios, scenarios_sources = await self.step4_scenario_generation(QA_drivers_info, context, stakeholders, constraints)
            
            # step 4 (mocked per test)
            with open('agent_outputs/ST4_scenarios.yaml') as f:
                input_yaml = f.read()
            
            scenarios = yaml.safe_load(input_yaml)

            # step 5
            evaluations = self.step5_metric_based_evaluation(normalized_architectures)
            
            # step 6
            multi_objective_comparison = self.step6_multi_objective_comparison(evaluations)

            # step 7
            # tradeoff_analysis = await self.step7_tradeoff_analysis(multi_objective_comparison, scenarios, evaluations)

            # mock
            with open('agent_outputs/ST7_tradeoff_analysis.yaml') as f:
                input_yaml = f.read()
            
            tradeoff_analysis = yaml.safe_load(input_yaml)

            driver_names = [d['quality_attribute'] for d in QA_drivers["candidate_drivers"]]

            await self.consider_evolution(tradeoff_analysis, non_functional_requirements, context, stakeholders, driver_names)

        return tradeoff_analysis


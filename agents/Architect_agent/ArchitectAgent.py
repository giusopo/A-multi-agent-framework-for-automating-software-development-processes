import json
import os
import yaml
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from get_embedding_function import get_embedding_function

from utils import (
    clean_raw_json,
    load_knowledge,
    extract_driver_keywords,
    generate_architecture_yaml
)

database_step1 ="chroma/chroma_add"
database_step2 ="chroma/chroma_arch_selection"
database_step3 ="chroma/chroma_component"
database_step4 ="chroma/chroma_component"

save_log = "output"

STEP1_PROMPT_TEMPLATE ="""You are a senior software architect applying Attribute-Driven Design (ADD).

IMPORTANT CONTEXT USAGE RULE:
- The CONTEXT below contains methodological guidance on how to identify and recognize
  architectural drivers (e.g. how to extract functional drivers).
- The CONTEXT is NOT a source of system requirements.
- The RAD is the ONLY source of factual information about the system.

You MUST:
- Use the CONTEXT only to guide your reasoning and extraction criteria
- Use the RAD exclusively to extract requirements, constraints, and stakeholders
- NEVER extract requirements or facts from the CONTEXT

---

CONTEXT (methodological guidance):
{context}

---

TASK:
Using the extraction rules and criteria described in the CONTEXT,
analyze the RAD and identify ONLY the architectural drivers.

DEFINITIONS:
- A Functional Driver is a functional requirement that forces major architectural decisions
  (e.g., decomposition, runtime interaction, integration, scalability, availability).
- Functional drivers are NOT all functional requirements.

EXCLUDE functional requirements that are:
- simple CRUD or UI-level
- standard or commodity features
- derivable from other requirements
- not directly tied to dominant quality attributes or constraints

INCLUDE ONLY:
- Functional Drivers
- Architecturally significant Quality Attribute Scenarios (ISO/IEC 25010)
- Non-negotiable constraints
- Stakeholders that influence architectural decisions

RULES:
1. Assign a priority ("low", "medium", "high") to each Functional Driver and
   Quality Attribute Scenario based on architectural impact.
2. Include an item ONLY if it clearly forces architectural decisions.
3. Formalize Quality Attributes strictly as QAW scenarios:
   source, stimulus, environment, artifact, response, measure.
4. Do NOT propose architectures, patterns, technologies, or solutions.
5. Do NOT infer, assume, or generalize beyond the RAD.
6. If the RAD does not explicitly support an item, DO NOT include it.
7. Use ONLY information contained in the RAD as system data.

OUTPUT REQUIREMENTS:
- Output MUST be valid JSON
- Do NOT include explanations outside the JSON
- IDs must be unique and sequential
- Empty arrays are allowed if no valid items exist

OUTPUT MUST be valid JSON:
{{
  "functional_drivers": [
    {{
      "id": "FD-01",
      "description": "...",
      "priority": "high",
      "rationale": "...",
      "standard": "IEEE 1016, ADD"
    }}
  ],
  "quality_attribute_scenarios": [
    {{
      "attribute": "...",
      "priority": "high",
      "source": "...",
      "stimulus": "...",
      "environment": "...",
      "artifact": "...",
      "response": "...",
      "measure": "...",
      "standard": "QAW (SEI), ISO/IEC 25010"
    }}
  ],
  "constraints_standard": ["ISO/IEC/IEEE 42010"],
  "constraints": ["..."],
  "stakeholders_standard": ["ISO/IEC/IEEE 42010"],
  "stakeholders": ["..."]
}}

---
RAD (system facts):
{rad_text}
"""

STEP2_PROMPT_TEMPLATE = """You are a senior software architect applying Attribute-Driven Design (ADD).

=== ARCHITECTURAL DRIVERS (from RAD) ===
{drivers}

=== KNOWLEDGE BASE (architectural literature) ===
{context}

TASK:
Using ONLY the architectural drivers and the knowledge base above,
generate 2–3 candidate architectures.

Rules:
- Do NOT propose technologies or components
- Reason in terms of architectural styles
- Candidate architectures MUST be standard architectural styles
  explicitly recognized in software architecture literature (SEI, POSA).
- Do NOT combine styles or add qualifiers (e.g., "with X", "enhanced by Y").
- Each architecture MUST be decomposable into logical components
  according to ADD Step 5.
Output format MUST be valid JSON, exactly like this example:

[
  {{
    "architecture_id": "Architecture 1",
    "name": "Architecture 1",
    "style": "...",
    "supported_quality_attributes": ["...", "..."],
    "main_risks": ["...", "..."]
  }},
  {{
    "architecture_id": "Architecture 2",
    "name": "Architecture 2",
    "style": "...",
    "supported_quality_attributes": ["...", "..."],
    "main_risks": ["...", "..."]
  }},
  {{
    "architecture_id": "Architecture 3",
    "name": "Architecture 3",
    "style": "...",
    "supported_quality_attributes": ["...", "..."],
    "main_risks": ["...", "..."]
  }}
]

Do NOT hallucinate fields. Return only the JSON array.
"""

STEP3_PROMPT_TEMPLATE = """You are a senior software architect applying Attribute-Driven Design (ADD).


=== ARCHITECTURAL DRIVERS ===
{drivers}

SELECTED CANDIDATE ARCHITECTURE :{architecture}

=== KNOWLEDGE BASE (ADD, DDD, UML) ===
{context_qta}
{context_arch}
{context_general}


TASK:
Decompose the system into logical components according to ADD Step 5.

RULES:
- Follow Single Responsibility Principle
- Components must be logical (not technical)
- Interfaces are logical contracts, not APIs
- Respect the constraints implied by the architectural style
- Use UML 2.5.1 Component Diagram concepts
- Do NOT include deployment or infrastructure concerns
- Do NOT introduce technologies

IMPORTANT:
- This is the ONLY step where logical components are introduced.
- All subsequent views MUST reuse these components without renaming or adding new ones.
- Define logical connectors between components (e.g., space read/write, event publish..)
IMPORTANT:
- architecture_id MUST be exactly: {architecture_id}
- name MUST be exactly: {architecture_name}


OUTPUT REQUIREMENTS:
- Output MUST be valid JSON
- Output MUST strictly follow the schema below
- Do NOT add extra fields
- Do NOT add explanations

SCHEMA:
{{
  "architecture_id": "Architecture_name",
  "name": "Architecture Name",
  "style": [],
  "uml_standard": "OMG UML 2.5.1",
  "views": {{
    "component_view": {{
      "components": [
        {{
          "id": "ComponentName",
          "type": "component",
          "responsibilities": [],
          "interfaces": {{
            "provided": [
              {{
                "name": "InterfaceName",
                "protocol": "LogicalProtocol"
              }}
            ],
            "required": []
          }}
        }}
      ],
      "connectors": []
    }}
  }}
}}

"""

STEP4_PROMPT_TEMPLATE = """You are a senior software architect applying Attribute-Driven Design (ADD).
=== ARCHITECTURAL DRIVERS ===
{drivers}

=== SELECTED CANDIDATE ARCHITECTURE ===
{architecture}

=== COMPONENT VIEW (FROM ADD STEP 3 – FIXED INPUT) ===
{component_view}

=== KNOWLEDGE BASE (Views, 4+1, C4, ISO/IEC/IEEE 42010) ===
{context}

TASK:
Produce architectural views for the selected architecture by REFINING the existing component decomposition.

MANDATORY CONSISTENCY RULES:
- The component view above is AUTHORITATIVE.
- You MUST NOT introduce, remove, rename, split, or merge components.
- You MUST reuse EXACTLY the component identifiers as provided.
- Logical, runtime, and deployment views MUST reference ONLY these components.
- No new responsibilities may contradict the provided component responsibilities.

VIEWS TO PRODUCE:
- Context view: actors and external systems interacting with the system
- Logical view: same components, refined responsibilities and connectors
- Runtime view: execution scenarios using the same components
- Deployment view: mapping the same components to nodes
- Security view: trust boundaries, threats, and countermeasures

FORBIDDEN:
- Introducing technologies, frameworks, or products
- Introducing implementation details
- Creating new components or aliases

OUTPUT FORMAT:
- Output MUST be valid JSON
- Output MUST strictly follow the schema below
- Do NOT include explanations or commentary

SCHEMA:
{{
  "architecture_id": "Architecture_name",
  "name": "Architecture Name",
  "views": {{
    "context_view": {{
      "actors": [],
      "external_systems": []
    }},
    "logical_view": {{
      "components": [
        {{
          "id": "ComponentID",
          "responsibilities": [],
          "interfaces": {{
            "provided": [],
            "required": []
          }}
        }}
      ],
      "connectors": []
    }},
    "runtime_view": {{
      "scenarios": []
    }},
    "deployment_view": {{
      "nodes": [],
      "component_mapping": {{}}
    }},
    "security_view": {{
      "trust_boundaries": [],
      "threats": [],
      "countermeasures": []
    }}
  }}
}}
"""

STEP5_PROMPT_TEMPLATE = """You are a senior software architect applying Attribute-Driven Design (ADD).

=== ARCHITECTURAL DRIVERS ===
{drivers}

=== ARCHITECTURAL VIEWS ===
{views}

=== KNOWLEDGE BASE (ADD, ISO/IEC/IEEE 42010, QA evaluation) ===
{context}

TASK:
Evaluate the selected architecture against the architectural drivers.

You MUST:
1. Verify that all architectural drivers (functional drivers, quality attributes, constraints) are addressed.
2. Identify any trade-offs between quality attributes.
3. Highlight potential risks and limitations.
4. Suggest refinements or mitigation tactics if drivers are not fully satisfied.

RULES:
- Use ONLY the provided drivers, views, and context.
- Do NOT propose new components or technologies.
- Base reasoning on ADD principles and ISO/IEC/IEEE 42010.
- Output MUST be valid JSON following the schema below.

SCHEMA:
{{
  "architecture_id": "Architecture_name",
  "name": "Architecture Name",
  "driver_coverage": [
    {{
      "driver_id": "FD-01",
      "description": "...",
      "satisfied": "yes | partially | no",
      "rationale": "..."
    }}
  ],
  "quality_attribute_tradeoffs": [
    {{
      "attributes_involved": ["Attribute1", "Attribute2"],
      "tradeoff_description": "...",
      "impact": "high | medium | low"
    }}
  ],
  "risks_and_limitations": [
    {{
      "description": "...",
      "severity": "high | medium | low"
    }}
  ],
  "recommended_refinements": [
    {{
      "description": "...",
      "driver_ids": ["FD-01", "FD-02"]
    }}
  ]
}}
"""

class ArchitectAgent:
    """
    ArchitectAgent implementato come agente AutoGen.
    Ogni step ADD diventa un task asincrono.
    L’agente deve produrre output JSON rigoroso.
    """

    def __init__(self, model_client):
        """
        Inizializza l’agente AutoGen con sistema e modello.
        """
        self.agent = AssistantAgent(
            name="ArchitectAgent",
            system_message="""
            You are a senior software architect applying Attribute-Driven Design (ADD).
            Your task is to generate architectural artifacts according to ADD steps.
            Strictly follow JSON schemas.
            Do NOT hallucinate or add fields not specified.
            """,
            model_client=model_client
        )

        # Memoria interna simile alla versione classica
        self.memory = {
            "architectural_drivers": [],
            "quality_attribute_scenarios": [],
            "constraints": [],
            "stakeholders": [],
            "candidate_architectures": [],
            "component_decompositions": [],
            "architectural_views": [],
            "architecture_evaluation": []
        }

        self.embedding_function = get_embedding_function()


    # ==================================================
    # STEP 1 – identify functional drivers
    # ==================================================
    async def identify_drivers(self, rad_text: str) -> dict:
        """
        Step 1 – Identificazione dei driver architetturali.
        Genera i functional drivers e quality attribute scenarios dal RAD.
        """
        if not rad_text:
            raise ValueError("❌ RAD text is required for Step 1")

        # ---------------------------------------------------------
        # 1️⃣ Recupera conoscenza rilevante dalla KB (RAG)
        # ---------------------------------------------------------
        retrieval_query = """
        Attribute-Driven Design (ADD) step 1 architectural drivers selection criteria.
        Functional requirements that force architectural decisions, quality attributes, constraints.
        Exclude CRUD/UI-level requirements.
        """
        context_text, sources = load_knowledge(self.embedding_function, database_step1, retrieval_query, k=13)

        if not context_text:
            raise RuntimeError("❌ Nessun documento recuperato da Chroma")

        # ---------------------------------------------------------
        # 2️⃣ Costruisci prompt per l’agente AutoGen
        # ---------------------------------------------------------
        prompt_content = STEP1_PROMPT_TEMPLATE.format(
            context=context_text,
            rad_text=rad_text
        )

        prompt = TextMessage(content=prompt_content, source="user")  # <- obbligatorio source

        # ---------------------------------------------------------
        # 3️⃣ Invia il prompt all’agente
        # ---------------------------------------------------------
        response = await self.agent.run(task=prompt)
        await self.agent.on_reset(cancellation_token=None)
        raw_output = response.messages[-1].content

        # Salva log per debug
        import os
        os.makedirs(save_log, exist_ok=True)
        with open(os.path.join(save_log, "step1_prompt.txt"), "w", encoding="utf-8") as f:
            f.write(prompt_content)
        with open(os.path.join(save_log, "step1_output_raw.txt"), "w", encoding="utf-8") as f:
            f.write(raw_output)

        # ---------------------------------------------------------
        # 4️⃣ Parsing JSON robusto
        # ---------------------------------------------------------
        try:
            result_json = json.loads(clean_raw_json(raw_output))
        except json.JSONDecodeError:
            raise ValueError("❌ Output non valido JSON dallo Step 1")

        # Aggiorna memoria interna
        self.memory["architectural_drivers"] = result_json.get("functional_drivers", [])
        self.memory["quality_attribute_scenarios"] = result_json.get("quality_attribute_scenarios", [])
        self.memory["constraints"] = result_json.get("constraints", [])
        self.memory["stakeholders"] = result_json.get("stakeholders", [])

        return result_json
    
    # ==================================================
    # STEP 2 – Candidate Architectures
    # ==================================================
    async def generate_candidate_architectures(self) -> dict:
        if not self.memory["architectural_drivers"]:
            raise ValueError("❌ Step 1 non eseguito")
        
        # --- Estrai driver keywords ---
        driver_keywords = extract_driver_keywords({
            "functional_drivers": self.memory["architectural_drivers"],
            "quality_attribute_scenarios": self.memory["quality_attribute_scenarios"],
            "constraints": self.memory["constraints"],
            "stakeholders": self.memory["stakeholders"]
        })

        # --- Recupera conoscenza da Chroma ---
        retrieval_query = f"""
            Architectural tactics and patterns that address the following concerns:
            {driver_keywords}
            quality attribute tradeoffs
            architectural styles
            risks and limitations
        """
        context_text, sources = load_knowledge(self.embedding_function, database_step2, retrieval_query, k=20)
        print("NUMERO BLOCCHI CONTEXT:", len(sources))

        # --- Costruisci prompt ---
        prompt_content = STEP2_PROMPT_TEMPLATE.format(
            drivers=json.dumps(driver_keywords, indent=2),
            context=context_text
        )

        # --- Invoca AutoGen ---
        prompt_msg = TextMessage(content=prompt_content, source="user")
        response = await self.agent.run(task=prompt_msg)
        # Reset opzionale del contesto AutoGen
        if hasattr(self.agent, "on_reset"):
            await self.agent.on_reset(cancellation_token=None)

        raw_output = response.messages[-1].content  # AutoGen restituisce TaskResult

        # --- Salva prompt/output per debug ---
        os.makedirs(save_log, exist_ok=True)
        with open(os.path.join(save_log, "prompt_final_step2.txt"), "w", encoding="utf-8") as f:
            f.write(prompt_content)
        with open(os.path.join(save_log, "step2_output_raw.txt"), "w", encoding="utf-8") as f:
            f.write(raw_output)

        # Parsing JSON robusto
        try:
            parsed = json.loads(clean_raw_json(raw_output))
        except json.JSONDecodeError:
            raise ValueError("❌ Output non valido JSON dallo Step 2")

        parsed = json.loads(clean_raw_json(raw_output))

        # Assicuriamoci che archs sia sempre una lista di dict
        if isinstance(parsed, dict) and "candidate_architectures" in parsed:
            archs = [a for a in parsed["candidate_architectures"] if isinstance(a, dict)]
        elif isinstance(parsed, list):
            archs = [a for a in parsed if isinstance(a, dict)]
        else:
            archs = []

        print("✅ Candidate Architectures (archs):", json.dumps(archs, indent=2))
        
        self.memory["candidate_architectures"] = archs

        if not archs:
            raise RuntimeError("❌ Step 2 non ha prodotto candidate architectures valide")


    # ==================================================
    # STEP 3 – Component Decomposition
    # ==================================================
    async def decompose_architectures(self) -> list:
        if not self.memory["candidate_architectures"]:
            raise ValueError("❌ Nessuna candidate architecture disponibile (Step 2)")

        decompositions = []

        # Drivers per lo Step 3
        drivers = {
            "functional_drivers": self.memory["architectural_drivers"],
            "quality_attribute_scenarios": self.memory["quality_attribute_scenarios"],
            "constraints": self.memory["constraints"],
            "stakeholders": self.memory["stakeholders"]
        }

        retrieval_query_general = """
            Attribute-Driven Design ADD step 3
            logical component decomposition
            responsibility assignment
            UML component view
            SEI ADD
        """
        context_general, sources = load_knowledge(self.embedding_function, database_step3, retrieval_query_general, k=9)

        # Quality-driven
        qa_keywords = []
        for qa in drivers["quality_attribute_scenarios"]:
            qa_keywords.append(qa.get("attribute", ""))
            qa_keywords.append(qa.get("stimulus", ""))
        qa_query = "Quality attribute scenarios related to: " + ", ".join([kw for kw in qa_keywords if kw])
        context_qta, sources = load_knowledge(self.embedding_function, database_step3, qa_query, k=6)

        for arch in self.memory["candidate_architectures"]:
            # --- Se arch è stringa, prova a convertire in dict ---
            if isinstance(arch, str):
                try:
                    arch = json.loads(arch)
                except json.JSONDecodeError:
                    print(f"⚠️ Ignorato elemento non valido: {arch}")
                    continue

            style = arch.get("style", "")
            qas = " ".join(arch.get("supported_quality_attributes", []))

            # Preparazione query Chroma
            retrieval_query_arch = f"""
                {style} architecture
                component decomposition
                responsibility allocation
                quality attributes {qas}
            """
            context_arch, sources = load_knowledge(self.embedding_function, database_step3, retrieval_query_arch, k=6)

            # Prompt compatto
            arch_text = json.dumps(arch)
            prompt = STEP3_PROMPT_TEMPLATE.format(
                drivers=json.dumps(drivers, indent=2),
                context_qta=context_qta,
                architecture_id=arch["architecture_id"],
                architecture_name=arch["name"],
                architecture=arch_text,
                context_arch=context_arch,
                context_general=context_general
            )

            os.makedirs(save_log, exist_ok=True)

            # Invoca LLM
            prompt_msg = TextMessage(content=prompt, source="user")
            response = await self.agent.run(task=prompt_msg)
            if hasattr(self.agent, "on_reset"):
                await self.agent.on_reset(cancellation_token=None)
            raw_output = response.messages[-1].content

            # Salva per debug
            with open(os.path.join(save_log, "step3_prompt.txt"), "w", encoding="utf-8") as f:
                f.write(prompt)
            with open(os.path.join(save_log, "step3_output_raw.txt"), "w", encoding="utf-8") as f:
                f.write(raw_output)

            # Parsing JSON robusto
            try:
                parsed = json.loads(clean_raw_json(raw_output))
            except json.JSONDecodeError:
                print(f"⚠️ Output non valido JSON dallo Step 3 per {arch.get('name', 'unknown')}")
                continue

            decompositions.append(parsed)

        self.memory["component_decompositions"] = decompositions
        
        return decompositions

    # ==================================================
    # STEP 4 – Architectural Views (self-refining)
    # ==================================================
    async def define_views(self) -> list:
        if not self.memory["candidate_architectures"]:
            raise ValueError("❌ Nessuna candidate architecture disponibile (Step 2)")

        views_list = []

        drivers = {
            "functional_drivers": self.memory["architectural_drivers"],
            "quality_attribute_scenarios": self.memory["quality_attribute_scenarios"],
            "constraints": self.memory["constraints"],
            "stakeholders": self.memory["stakeholders"]
        }

        # Recupera knowledge generale
        retrieval_query = """
            Architectural views definition for software systems, including Context, Logical, Runtime,
            Deployment, and Security views.
            4+1 View Model by Kruchten, C4 Model by Simon Brown, ISO/IEC/IEEE 42010 Clause 5.
        """
        context_text, _ = load_knowledge(self.embedding_function, database_step4, retrieval_query, k=15)

        for arch in self.memory["candidate_architectures"]:
            component_decomposition = next(
                (
                    cd for cd in self.memory["component_decompositions"]
                    if cd.get("architecture_id") == arch.get("architecture_id")
                    or cd.get("name") == arch.get("name")
                ),
                None
            )

            if not component_decomposition:
                raise ValueError(f"❌ Nessuna component decomposition trovata per {arch.get('name')}")

            max_attempts = 2
            attempt = 0
            last_error = ""

            while attempt <= max_attempts:
                feedback = f"\nREFINEMENT FEEDBACK:\n{last_error}\n" if last_error else ""

                prompt_content = STEP4_PROMPT_TEMPLATE.format(
                    drivers=json.dumps(drivers, indent=2),
                    architecture=json.dumps(arch, indent=2),
                    component_view=json.dumps(component_decomposition["views"]["component_view"], indent=2),
                    context=context_text
                ) + feedback

                # Salva prompt per debug
                os.makedirs(save_log, exist_ok=True)
                with open(os.path.join(save_log, "step4_prompt.txt"), "w", encoding="utf-8") as f:
                    f.write(prompt_content)

                # --- Invoca AutoGen ---
                prompt_msg = TextMessage(content=prompt_content, source="user")
                response = await self.agent.run(task=prompt_msg)
                await self.agent.on_reset(cancellation_token=None)
                raw_output = response.messages[-1].content

                # Salva output raw
                with open(os.path.join(save_log, "step4_output_raw.txt"), "w", encoding="utf-8") as f:
                    f.write(raw_output)

                # Parsing JSON robusto
                try:
                    parsed = json.loads(clean_raw_json(raw_output))
                except json.JSONDecodeError:
                    last_error = "LLM returned invalid JSON"
                    attempt += 1
                    continue

                # Validazione interna
                is_valid, error_msg = await self.validate_architectural_views(parsed)
                await self.agent.on_reset(cancellation_token=None)
                if is_valid:
                    views_list.append(parsed)
                    break

                last_error = (
                    f"The generated architectural views are invalid: {error_msg}. "
                    f"Refine ONLY the views. Do NOT change components or introduce new ones."
                )
                attempt += 1

            if attempt > max_attempts:
                raise RuntimeError(f"❌ Unable to generate valid architectural views for {arch.get('name')}")

        # Aggiorna memoria
        self.memory["architectural_views"] = views_list
        return views_list


    # ==================================================
    # STEP 5 – Architecture Evaluation / Refinement
    # ==================================================
    async def evaluate_architecture(self) -> list:
        if not self.memory["architectural_views"]:
            raise ValueError("❌ Step 4 non eseguito – architectural views mancanti")

        drivers = {
            "functional_drivers": self.memory["architectural_drivers"],
            "quality_attribute_scenarios": self.memory["quality_attribute_scenarios"],
            "constraints": self.memory["constraints"],
            "stakeholders": self.memory["stakeholders"]
        }

        # Recupera knowledge base per valutazione
        retrieval_query = """
            Architectural evaluation guidelines
            ADD Step 5 verification and refinement
            Quality attribute trade-offs
            ISO/IEC/IEEE 42010 compliance
            Risk identification and mitigation
        """
        context_text, _ = load_knowledge(self.embedding_function, database_step4, retrieval_query, k=20)

        evaluations = []

        for views in self.memory["architectural_views"]:
            views_json = json.dumps(views, indent=2)
            prompt_content = STEP5_PROMPT_TEMPLATE.format(
                drivers=json.dumps(drivers, indent=2),
                views=views_json,
                context=context_text
            )

            # Salva prompt per debug
            os.makedirs(save_log, exist_ok=True)
            with open(os.path.join(save_log, "step5_prompt.txt"), "w", encoding="utf-8") as f:
                f.write(prompt_content)

            # --- Invoca AutoGen ---
            prompt_msg = TextMessage(content=prompt_content, source="user")
            response = await self.agent.run(task=prompt_msg)
            await self.agent.on_reset(cancellation_token=None)
            raw_output = response.messages[-1].content

            # Salva output raw
            with open(os.path.join(save_log, "step5_output_raw.txt"), "w", encoding="utf-8") as f:
                f.write(raw_output)

            # Parsing JSON robusto
            try:
                parsed = json.loads(clean_raw_json(raw_output))
            except json.JSONDecodeError:
                raise ValueError(f"❌ Output non valido JSON dallo Step 5 per {views.get('architecture_id', 'Unknown')}")

            evaluations.append(parsed)

        # Aggiorna memoria
        self.memory["architecture_evaluation"] = evaluations
        return evaluations

    # ==================================================
    # 
    # ==================================================
    async def run_full_add_pipeline(
        self,
        rad_text: str,
        output_yaml_path: str = "output/output.yaml",
        output_json_path: str = "output/architecture_result.json"
    ):
        """
        Esegue tutti gli step ADD sull'input RAD usando AutoGen e salva:
        - YAML finale delle architetture
        - JSON completo della memoria dell'agente
        """
        import os
        import json
        import yaml

        os.makedirs("output", exist_ok=True)

        # ==================================================
        # STEP 1 – Architectural Drivers
        # ==================================================
        print("=== STEP 1: Identifying Architectural Drivers ===")
        drivers_result = await self.identify_drivers(rad_text)
        if not drivers_result:
            raise RuntimeError("❌ Step 1 non ha prodotto architectural drivers")
        self.memory["architectural_drivers"] = drivers_result.get("functional_drivers", [])
        self.memory["quality_attribute_scenarios"] = drivers_result.get("quality_attribute_scenarios", [])
        self.memory["constraints"] = drivers_result.get("constraints", [])
        self.memory["stakeholders"] = drivers_result.get("stakeholders", [])

        print("✅ Step 1 completato")
        print("Functional drivers:", json.dumps(self.memory["architectural_drivers"], indent=2))
        print("Quality attribute scenarios:", json.dumps(self.memory["quality_attribute_scenarios"], indent=2))

        # ==================================================
        # STEP 2 – Candidate Architectures
        # ==================================================
        print("=== STEP 2: Generating Candidate Architectures ===")
        await self.generate_candidate_architectures()

        # ==================================================
        # STEP 3 – Component Decomposition
        # ==================================================
        print("=== STEP 3: Decomposing Architectures into Components ===")
        await self.decompose_architectures()
            
        print("✅ Step 3 completato")

        # ==================================================
        # STEP 4 – Defining Architectural Views
        # ==================================================
        print("=== STEP 4: Defining Architectural Views ===")
        await self.define_views()

        print("✅ Step 4 completato")

        # ==================================================
        # STEP 5 – Evaluating Architectures
        # ==================================================
        print("=== STEP 5: Evaluating Architectures ===")
        await self.evaluate_architecture()

        print("✅ Step 5 completato")
        # ==================================================
        # Salva JSON completo della memoria
        # ==================================================
        with open(output_json_path, "w", encoding="utf-8") as f_json:
            json.dump(self.memory, f_json, indent=2, ensure_ascii=False)
        print(f"✅ JSON completo della memoria salvato in '{output_json_path}'.")

        # ==================================================
        # Genera YAML finale
        # ==================================================
        architecture_yaml_dict = generate_architecture_yaml(self.memory)
        with open(output_yaml_path, "w", encoding="utf-8") as f_yaml:
            yaml.dump(architecture_yaml_dict, f_yaml, sort_keys=False, allow_unicode=True)
        print(f"✅ YAML finale salvato in '{output_yaml_path}'.")

        return self.memory  # restituisce la memoria completa

    def generate_architecture_yaml(self):
        """
        Converte la memoria dell'agente in formato YAML compatto per report finale.
        """
        architectures = []

        for arch in self.memory["candidate_architectures"]:
            arch_id = arch.get("architecture_id", arch.get("name", "Unknown"))
            views = next((v for v in self.memory["architectural_views"]
                          if v.get("architecture_id") == arch_id), {})
            evaluations = next((e for e in self.memory["architecture_evaluation"]
                                if e.get("architecture_id") == arch_id), {})

            architectures.append({
                "architecture_id": arch_id,
                "name": arch.get("name"),
                "style": arch.get("style", []),
                "views": views.get("views", {}),
                "evaluation": evaluations
            })

        return {"architectures": architectures}

    async def validate_architectural_views(self, views: dict) -> tuple[bool, str]:
        """
        Validates architectural views using RAG approach and AutoGen LLM.
        Retrieves relevant guidance from KB and asks the LLM to evaluate quality.
        
        Returns:
            (bool, str): (is_valid, error_message). If valid, error_message may include LLM feedback.
        """
        # ---------------------------------------------------------
        # 1. Recupera knowledge base rilevante per la validazione
        # ---------------------------------------------------------
        retrieval_query = """
        Architectural views evaluation guidelines:
        - Attribute-Driven Design (ADD) principles
        - ISO/IEC/IEEE 42010 compliance
        - 4+1 View Model and C4 Model
        - Component consistency, connectors, and responsibilities
        - Quality attributes coverage and trade-offs
        """
        context_text, _ = load_knowledge(
            self.embedding_function, database_step4, retrieval_query, k=15
        )

        # ---------------------------------------------------------
        # 2. Prepara prompt per il controllo qualità
        # ---------------------------------------------------------
        quality_check_prompt = f"""
        You are a senior software architect applying ADD.

        TASK:
        Review the provided architectural views for correctness, completeness, and adherence to ADD principles.
        Use ONLY the CONTEXT (knowledge base) and the provided architectural drivers.
        Do NOT modify the architecture, only check quality.

        ARCHITECTURAL DRIVERS:
        {json.dumps({
            "functional_drivers": self.memory["architectural_drivers"],
            "quality_attribute_scenarios": self.memory["quality_attribute_scenarios"],
            "constraints": self.memory["constraints"],
            "stakeholders": self.memory["stakeholders"]
        }, indent=2)}

        ARCHITECTURAL VIEWS TO VALIDATE:
        {json.dumps(views, indent=2)}

        CONTEXT (Guidelines from KB):
        {context_text}

        OUTPUT:
        - valid: "yes" or "no"
        - issues: list of descriptions of problems (empty if valid)

        Return ONLY valid JSON.
            """

        # ---------------------------------------------------------
        # 3. Invoca AutoGen
        # ---------------------------------------------------------
        prompt_msg = TextMessage(content=quality_check_prompt, source="user")
        response = await self.agent.run(task=prompt_msg)
        raw_output = response.messages[-1].content

        # ---------------------------------------------------------
        # 4. Parsing JSON robusto
        # ---------------------------------------------------------
        try:
            parsed = json.loads(clean_raw_json(raw_output))
        except json.JSONDecodeError:
            return False, "LLM returned invalid JSON during quality validation"

        valid_flag = parsed.get("valid", "").lower()
        issues = parsed.get("issues", [])

        if valid_flag == "yes":
            return True, ""
        else:
            issue_text = "; ".join(issues) if issues else "Unknown issues detected by LLM"
            return False, issue_text


def ensure_dict(obj):
    """
    Converte ricorsivamente stringhe JSON in dict.
    """
    if isinstance(obj, str):
        try:
            return ensure_dict(json.loads(obj))
        except json.JSONDecodeError:
            return obj
    elif isinstance(obj, list):
        return [ensure_dict(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: ensure_dict(v) for k, v in obj.items()}
    else:
        return obj

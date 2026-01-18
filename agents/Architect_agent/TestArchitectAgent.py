import asyncio
import os
from dotenv import load_dotenv
from autogen_ext.models.openai import OpenAIChatCompletionClient
from ArchitectAgent import ArchitectAgent

async def main():
    # Carica eventuali variabili d'ambiente
    load_dotenv()

    # ==================================================
    # 1️⃣ Inizializza il modello LLM locale (Gemma)
    # ==================================================
    llm = OpenAIChatCompletionClient(
        model="google_gemma-3n-e4b",
        base_url="http://127.0.0.1:1234/v1",
        api_key="placeholder",
        temperature=0.1,
        timeout=600,
        model_info={
            "max_tokens": 10240,
            "context_length": 10240,
            "completion_params": {},
            "vision": None,
            "function_calling": None,
            "json_output": None,
            "family": "llm",
            "structured_output": None
        }
    )

    # ==================================================
    # 2️⃣ Crea l'agente AutoGen
    # ==================================================
    agent = ArchitectAgent(model_client=llm)

    # ==================================================
    # 3️⃣ Leggi RAD di input
    # ==================================================
    rad_path = "rad.txt"
    if not os.path.exists(rad_path):
        raise FileNotFoundError(f"❌ File RAD '{rad_path}' non trovato!")

    with open(rad_path, "r", encoding="utf-8") as f:
        rad_text = f.read()

    # ==================================================
    # 4️⃣ Esegui pipeline completa ADD
    # ==================================================
    memory = await agent.run_full_add_pipeline(
        rad_text=rad_text,
        output_yaml_path="output/final_architecture.yaml",
        output_json_path="output/final_architecture.json"
    )

    # ==================================================
    # 5️⃣ Stampa sintesi dei driver architetturali
    # ==================================================
    print("✅ Pipeline completata!")
    print("Sintesi driver architetturali estratti:")
    for fd in memory["architectural_drivers"]:
        print(f"- {fd.get('id')}: {fd.get('description')} (priority: {fd.get('priority')})")

if __name__ == "__main__":
    asyncio.run(main())

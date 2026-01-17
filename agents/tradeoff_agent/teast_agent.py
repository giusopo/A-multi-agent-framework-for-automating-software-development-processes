import asyncio
from dotenv import load_dotenv
from autogen_ext.models.openai import OpenAIChatCompletionClient
from agents.tradeoff_agent import TradeOffAgent

# python -m tests.test_agent
async def main():
    load_dotenv()

    # Inizializza il modello
    llm = OpenAIChatCompletionClient(
        model="google_gemma-3n-e4b-it",
        base_url="http://127.0.0.1:1234/v1",
        api_key="placeholder",
        temperature=0.1,
        timeout=600,
        model_info={
            "max_tokens": 6144,
            "context_length": 6144,
            "completion_params": {},
            "vision": None,
            "function_calling": None,
            "json_output": None,
            "family": "llm",
            "structured_output": None
        }
    )

    # Crea l'agente
    agent = TradeOffAgent(model_client=llm)

    # prendi l'input
    with open('input2.yaml') as f:
        input_yaml = f.read()

    response = await agent.analyze(input_yaml)


if __name__ == "__main__":
    asyncio.run(main())

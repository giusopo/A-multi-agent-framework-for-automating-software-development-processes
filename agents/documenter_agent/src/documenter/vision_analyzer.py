import requests
import base64
from typing import Dict
from PIL import Image
import io

LM_API_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "minicpm-v-2_6"


def encode_and_resize_image(image_path: str, max_size=800) -> str:
    """
    Ridimensiona immagine per evitare timeout Vision.
    Mantiene proporzioni e comprime PNG.
    """
    img = Image.open(image_path)

    img.thumbnail((max_size, max_size))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode("utf-8")


def analyze_diagram(image_path, diagram_type="generic"):

    # Ridimensionamento automatico
    image_base64 = encode_and_resize_image(image_path)

    prompt_map = {
        "sequence": "Analyze this UML SEQUENCE diagram. Focus only on layout and alignment issues. Do NOT modify semantic structure.",
        "context": "Analyze this UML CONTEXT diagram. Focus only on layout and visual clarity.",
        "component": "Analyze this UML COMPONENT diagram. Focus only on visual grouping and connector readability.",
        "deployment": "Analyze this UML DEPLOYMENT diagram. Focus only on node layout clarity.",
        "security": "Analyze this UML SECURITY diagram. Focus only on boundary readability and label clarity."
    }

    prompt = prompt_map.get(diagram_type, "Analyze this UML diagram layout only.")

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 500
    }

    try:
        response = requests.post(
            LM_API_URL,
            json=payload,
            timeout=60  #  timeout ridotto ma più realistico
        )

        if response.status_code == 200:
            return response.json()

        return {
            "error": "bad_status_code",
            "status": response.status_code
        }

    except Exception as e:
        return {
            "error": "timeout_or_connection_error",
            "message": str(e)
        }
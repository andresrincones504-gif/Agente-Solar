import asyncio
import os
from functools import partial

from google import genai
from google.genai import types


def _llamar_gemini_sync(api_key: str, model_name: str, prompt: str, config) -> str:
    """Llamada síncrona a Gemini. Se ejecuta en un thread para no bloquear."""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config,
    )
    return response.text


async def obtener_respuesta_gemini(
    prompt: str,
    system_instruction: str = None,
    model_name: str = None,
) -> str:
    """
    Llama a Gemini de forma no bloqueante usando run_in_executor.
    Evita depender de aiohttp (client.aio) cuya compatibilidad es inestable.
    """
    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY no está configurada")

    config = None
    if system_instruction:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
        )

    try:
        loop = asyncio.get_event_loop()
        fn = partial(_llamar_gemini_sync, api_key, model_name, prompt, config)
        return await loop.run_in_executor(None, fn)
    except Exception as e:
        print(f"Error al conectar con Gemini: {e}")
        return None

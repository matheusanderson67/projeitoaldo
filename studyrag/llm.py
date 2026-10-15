
from . import config
from .errors import LLMError


def chat(system: str, user: str, temperature: float = 0.2, json_mode: bool = False) -> str:
    if not config.LLM_API_KEY and not config.LLM_BASE_URL:
        raise LLMError("A API de IA não está configurada. Defina LLM_API_KEY no arquivo .env.")
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=config.LLM_API_KEY or "sem-chave",
            base_url=config.LLM_BASE_URL,
            timeout=180,
        )
        kwargs = dict(
            model=config.LLM_MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        if json_mode:
            try: 
                resp = client.chat.completions.create(**kwargs, response_format={"type": "json_object"})
            except Exception:
                resp = client.chat.completions.create(**kwargs)
        else:
            resp = client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        raise LLMError(
            f"Falha ao chamar a API de IA ({type(exc).__name__}). "
            "Verifique a chave e a conexão e tente novamente."
        ) from exc

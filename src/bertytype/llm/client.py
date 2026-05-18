import requests
from concurrent.futures import ThreadPoolExecutor, Future
from bertytype.llm.prompts import get_prompt

OLLAMA_URL = "http://localhost:11434/api/generate"

_executor = ThreadPoolExecutor(max_workers=1)


def refine(text: str, mode: str, model: str, timeout: int = 30) -> str:
    payload = {
        "model": model,
        "prompt": get_prompt(mode, text),
        "stream": False,
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.Timeout:
        raise RuntimeError(f"Ollama timed out after {timeout}s") from None
    except requests.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama at localhost:11434") from None
    except requests.HTTPError as e:
        raise RuntimeError(f"Ollama returned HTTP error: {e}") from e
    try:
        return resp.json()["response"].strip()
    except (KeyError, ValueError) as e:
        raise RuntimeError(f"Unexpected Ollama response format: {e}") from e


def refine_async(text: str, mode: str, model: str, timeout: int = 30) -> Future:
    return _executor.submit(refine, text, mode, model, timeout)


def shutdown() -> None:
    _executor.shutdown(cancel_futures=True)

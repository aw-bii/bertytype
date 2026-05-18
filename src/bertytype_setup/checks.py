from __future__ import annotations
import logging
import subprocess
from pathlib import Path


def _hf_cache_root() -> Path:
    return Path.home() / ".cache" / "huggingface" / "hub"


def is_ollama_installed() -> bool:
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_model_pulled(model: str = "gemma4:e2b") -> bool:
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        try:
            if resp.status_code != 200:
                return False
            names = [m["name"] for m in resp.json().get("models", [])]
            return model in names
        finally:
            resp.close()
    except requests.exceptions.ConnectionError:
        return False
    except Exception as e:
        logging.debug("is_model_pulled check failed: %s", e)
        return False


def is_vibevoice_cached() -> bool:
    model_dir = _hf_cache_root() / "models--microsoft--VibeVoice-ASR-HF"
    if not model_dir.exists():
        return False
    return any(model_dir.rglob("*.safetensors"))


def check_all() -> dict:
    return {
        "ollama": is_ollama_installed(),
        "model": is_model_pulled(),
        "vibevoice": is_vibevoice_cached(),
    }

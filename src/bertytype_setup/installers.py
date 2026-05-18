from __future__ import annotations
import hashlib
import json
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import requests

OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_API = "http://localhost:11434"
MODEL = "gemma4:e2b"
VIBEVOICE_REPO = "microsoft/VibeVoice-ASR-HF"

_ollama_proc: Optional[subprocess.Popen] = None


def _post(q: queue.Queue, event: str, *args) -> None:
    q.put((event, *args))


def _download_file(
    url: str,
    dest: Path,
    q: queue.Queue,
    cancel: threading.Event,
    step_key: str,
    expected_hash: Optional[str] = None,
) -> Optional[Path]:
    """Stream-download url to dest. Returns dest on success, None on cancel/error.

    Note: Ollama does not publish cryptographic hashes for its installer downloads.
    Therefore, _download_file cannot perform hash verification for OllamaSetup.exe.
    When/if Ollama provides hash verification, add the expected_hash parameter here.
    """
    tmp = dest.with_suffix(".tmp")
    try:
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if cancel.is_set():
                        tmp.unlink(missing_ok=True)
                        return None
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        _post(q, "step_progress", step_key, downloaded / total)
        tmp.rename(dest)

        # TODO: Hash verification for Ollama installer.
        # Currently not implemented because Ollama does not publish SHA256 hashes
        # for its installer. When hashes become available, add verification here:
        #   actual_hash = hashlib.sha256(dest.read_bytes()).hexdigest()
        #   assert actual_hash == expected_hash, f"Hash mismatch: {actual_hash} != {expected_hash}"
        if expected_hash:
            actual_hash = hashlib.sha256(dest.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                dest.unlink(missing_ok=True)
                _post(q, "log", f"Hash mismatch: {actual_hash} != {expected_hash}")
                return None

        return dest
    except Exception as e:
        tmp.unlink(missing_ok=True)
        _post(q, "log", f"Download failed: {e}")
        return None


def _ensure_ollama_service(q: queue.Queue, cancel: threading.Event) -> bool:
    """Start ollama serve if not already running. Poll up to 30s."""
    global _ollama_proc
    try:
        resp = requests.get(f"{OLLAMA_API}/api/tags", timeout=2)
        try:
            if resp.status_code == 200:
                return True
        finally:
            resp.close()
    except (requests.ConnectionError, requests.Timeout):
        pass
    _post(q, "log", "Starting Ollama service...")
    _ollama_proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        if cancel.is_set():
            _ollama_proc.terminate()
            _ollama_proc = None
            return False
        time.sleep(1)
        try:
            resp = requests.get(f"{OLLAMA_API}/api/tags", timeout=2)
            try:
                if resp.status_code == 200:
                    return True
            finally:
                resp.close()
        except (requests.ConnectionError, requests.Timeout):
            pass
    _post(q, "log", "Ollama service did not start within 30s")
    return False


def install_ollama(q: queue.Queue, cancel: threading.Event) -> bool:
    """Download OllamaSetup.exe, run silently, then ensure service is up."""
    if cancel.is_set():
        return False
    _post(q, "log", "Downloading Ollama installer...")
    tmp_dir = Path(tempfile.gettempdir())
    dest = tmp_dir / "OllamaSetup.exe"
    path = _download_file(OLLAMA_DOWNLOAD_URL, dest, q, cancel, "ollama")
    if path is None:
        return False
    _post(q, "log", "Running Ollama installer (this may take a minute)...")
    result = subprocess.run([str(path), "/SILENT"], timeout=180)
    path.unlink(missing_ok=True)
    if result.returncode != 0:
        _post(q, "log", f"Installer exited with code {result.returncode}")
        return False
    return _ensure_ollama_service(q, cancel)


def pull_model(q: queue.Queue, cancel: threading.Event, model: str = MODEL) -> bool:
    """Stream `ollama pull <model>` and report progress.

    Note: Ollama does not publish cryptographic hashes for model downloads.
    Therefore, no hash verification is performed on pulled model files.
    """
    _post(q, "log", f"Pulling {model} (this may take several minutes)...")
    try:
        proc = subprocess.Popen(
            ["ollama", "pull", model],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            if cancel.is_set():
                proc.kill()
                return False
            for line in proc.stdout:
                if cancel.is_set():
                    proc.kill()
                    return False
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    status = data.get("status", "")
                    if total and completed:
                        _post(q, "step_progress", "model", completed / total)
                    if status:
                        _post(q, "log", status)
                except json.JSONDecodeError:
                    _post(q, "log", line)
        finally:
            proc.wait()
        return proc.returncode == 0
    except Exception as e:
        _post(q, "log", f"Model pull failed: {e}")
        return False


def _list_hf_files(repo_id: str) -> list[str]:
    from huggingface_hub import list_repo_files
    return list(list_repo_files(repo_id))


def _hf_download_file(repo_id: str, filename: str, expected_hash: Optional[str] = None) -> None:
    from huggingface_hub import hf_hub_download
    hf_hub_download(repo_id=repo_id, filename=filename, hash=expected_hash)


def download_vibevoice(q: queue.Queue, cancel: threading.Event) -> bool:
    """Download VibeVoice ASR model files to the HuggingFace cache."""
    if cancel.is_set():
        return False
    _post(q, "log", "Fetching VibeVoice file list from Hugging Face...")
    try:
        files = _list_hf_files(VIBEVOICE_REPO)
    except Exception as e:
        _post(q, "log", f"Failed to fetch file list: {e}")
        return False

    total = len(files)
    for i, filename in enumerate(files):
        if cancel.is_set():
            return False
        _post(q, "log", f"Downloading {filename} ({i + 1}/{total})...")
        try:
            _hf_download_file(VIBEVOICE_REPO, filename, None)  # hash=None - TODO: add hardcoded hashes after first download
        except Exception as e:
            _post(q, "log", f"Failed to download {filename}: {e}")
            return False
        _post(q, "step_progress", "vibevoice", (i + 1) / total)

    return True


def run_all_installs(
    q: queue.Queue,
    cancel: threading.Event,
    steps: list[str],
) -> None:
    """Run install steps sequentially. steps is the list of keys needing installation."""
    results: dict[str, bool] = {}

    if "ollama" in steps:
        _post(q, "step_start", "ollama")
        ok = install_ollama(q, cancel)
        results["ollama"] = ok
        _post(q, "step_done" if ok else "step_failed", "ollama")
    elif "model" in steps:
        results["ollama"] = _ensure_ollama_service(q, cancel)

    if "model" in steps:
        if not results.get("ollama", True):
            _post(q, "step_skipped", "model")
        else:
            _post(q, "step_start", "model")
            ok = pull_model(q, cancel)
            _post(q, "step_done" if ok else "step_failed", "model")

    if "vibevoice" in steps:
        _post(q, "step_start", "vibevoice")
        ok = download_vibevoice(q, cancel)
        _post(q, "step_done" if ok else "step_failed", "vibevoice")

    _post(q, "all_done", results)

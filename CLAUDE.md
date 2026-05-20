# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BertyType is a local, offline voice-dictation app for Windows. It captures microphone audio, transcribes speech using VibeVoice (local STT), optionally refines the text with Gemma 4 (local LLM), and injects the result into whatever window the user has focused - system-wide, without any cloud dependency.

## Key Documentation

For comprehensive understanding of the project, refer to:
- **PRODUCT.md** - Product requirements, vision, and user stories
- **ARCHITECTURE.md** - Detailed system architecture and component design
- **AGENTS.md** - Agent configurations, responsibilities, and communication patterns
- **DESIGN.md** - Design specifications and guidelines

## Style Rules

- Never use em-dashes (--) in any text output, comments, docs, or UI strings. Use a hyphen (-), colon (:), or reword instead.

## Target Stack

- **Language**: Python (primary runtime)
- **STT**: VibeVoice - local speech-to-text engine
- **LLM post-processing**: Gemma 4 via Ollama (or llama.cpp) - cleans up filler words, formats punctuation, rewrites for context
- **Audio capture**: `sounddevice` or `pyaudio` for real-time microphone input
- **System integration (Windows)**: `pywin32` / `pygetwindow` for active-window detection; `pyperclip` + simulated keystrokes (`pyautogui`) for text injection
- **Hotkey daemon**: `keyboard` library for global push-to-talk or toggle shortcut
- **UI** (optional tray): `pystray` + `Pillow` for a system-tray icon

## Architecture

```
+--------------+     audio      +--------------+    raw text    +--------------+
|  Hotkey /    | -------------> |  VibeVoice   | -------------> |  Gemma 4     |
|  Audio Loop  |                |  STT Engine  |                |  Refinement  |
+--------------+                +--------------+                +--------------+
                                                                       |
                                                               refined text
                                                                       |
                                                                       v
                                                          +--------------------+
                                                          |  Text Injector     |
                                                          |  (active window)   |
                                                          +--------------------+
```

- **`audio/`**: microphone capture, VAD (voice activity detection), chunking; file reader for batch transcription
- **`stt/`**: VibeVoice wrapper; accepts audio bytes, returns transcript string
- **`llm/`**: Gemma 4 client (Ollama HTTP or subprocess); prompt templates for clean-up vs. rewrite modes
- **`injection/`**: clipboard-based text injection + optional direct keystroke injection; file exporter for saving transcripts
- **`hotkeys/`**: global hotkey registration (push-to-talk, toggle, cancel)
- **`ui/`**: system-tray icon, status indicator, settings window
- **`config.py`**: single source for user settings (hotkey, model name, refinement prompt, VAD threshold)

## Key Design Decisions

- **Offline-first**: no network calls in the hot path; Ollama must be running locally
- **Push-to-talk by default**: hold a key, record, release, transcribe, inject
- **Refinement is optional**: STT output can be injected raw; LLM pass is a toggle in config
- **Windows-first**: text injection uses the clipboard + `Ctrl+V` simulation; active-window detection via Win32 API
- **File transcription**: tray menu "Transcribe file..." opens a file picker; output goes to clipboard AND saved as `.txt` next to the source audio file

## Development Setup

```bash
# Create and activate virtualenv
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -e .

# Run the app
.venv\Scripts\python.exe -m bertytype

# Run tests (must use venv Python - system Python 3.14 breaks pydub)
.venv\Scripts\python.exe -m pytest tests/
```

## Project Entry Point

The application entry point is `src/bertytype/__main__.py` which initializes and runs all agents. To run the application directly:
```bash
python -m bertytype
```

## Project Structure

- `src/bertytype/` - Main source code organized by agent modules
  - `audio/` - Audio capture and VAD
  - `stt/` - Speech-to-text processing
  - `llm/` - LLM refinement via Ollama
  - `injection/` - Text injection and export
  - `hotkeys/` - Global hotkey management
  - `ui/` - System tray and settings interface
  - `config.py` - Centralized configuration
- `tests/` - Test suite
- `docs/` - Additional documentation and specifications
- `graphify-out/` - Knowledge graph for codebase understanding

## Ollama / Gemma 4

```bash
# Pull the model (one-time)
ollama pull gemma4

# Confirm it's running
ollama run gemma4 "hello"
```

The LLM client should call `http://localhost:11434/api/generate` (Ollama default).

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep - these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)

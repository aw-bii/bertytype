# BertyType TODO Features Design

Date: 2026-05-20

## Overview

This spec covers four features from TODO.md: wizard fix, undo hotkey, transcription history, and configuration profiles. All follow Approach A (minimal footprint) - no new windows beyond what is strictly necessary.

---

## 1. Wizard Fix

### Problem

Three bugs prevent the setup wizard from opening:

1. `bertytype/logging.py` shadows the stdlib `logging` module. When the app is launched via `python src/bertytype/__main__.py`, Python adds `src/bertytype/` to `sys.path`, so any `import logging` inside third-party packages (requests, urllib3, loguru) resolves to our file instead of stdlib, causing a circular import crash before Qt initializes.
2. `bertytype_setup` is absent from `[tool.hatch.build.targets.wheel].packages` in `pyproject.toml`, so a wheel install never includes it. When the main app tries to import it, the import silently fails and `_run_setup_if_needed()` returns `True` (skip wizard).
3. No `bertytype-setup` standalone entry point exists in `[project.gui-scripts]`, so users cannot re-run setup manually.

### Fix

**File rename:** Rename `src/bertytype/logging.py` to `src/bertytype/applog.py`. Update every `from bertytype import logging as log_module` / `import bertytype.logging` import across the codebase to use `applog`.

**pyproject.toml - wheel packages:**
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/bertytype", "src/bertytype_setup"]
```

**pyproject.toml - entry point:**
```toml
[project.gui-scripts]
bertytype = "bertytype.__main__:main"
bertytype-setup = "bertytype_setup.__main__:main"
```

**CLAUDE.md update:** Replace the broken `python src\bertytype\__main__.py` invocation with the correct `python -m bertytype`.

### No wizard logic changes

The wizard pages (Welcome, Check, Install, Finish) are unchanged. This is purely a packaging and import fix.

---

## 2. Undo Hotkey

### Behaviour

After a successful injection, the user can fire a configurable hotkey to undo the paste in the target application. Since the target window retains focus after injection, the undo hotkey simply re-fires `Ctrl+Z` at the current foreground window via pyautogui.

### Config

Add one field to `Config` in `config.py`:

```python
undo_hotkey: str = "ctrl+z"
```

Validation: same rules as `hotkey` and `cancel_hotkey` (non-empty string). Add to `_validate_value()` and the settings dialog.

### Hotkey registration

In `_register_hotkeys()` in `__main__.py`, register the undo hotkey alongside the existing ones:

```python
hotkey_daemon.register(cfg.undo_hotkey, _on_undo)
```

Handler:

```python
def _on_undo() -> None:
    pyautogui.hotkey("ctrl", "z")
```

### Settings UI

Add an "Undo hotkey" `QLineEdit` field to the Settings dialog in the same group as the existing hotkey fields.

---

## 3. Transcription History

### Storage

Each successful injection appends one JSON line to `~/.bertytype/history.jsonl`:

```jsonl
{"ts": 1748000000, "text": "The transcribed text goes here."}
```

The append function prunes entries older than 7 days on every write (read file, filter, rewrite). This keeps the file bounded without a separate cleanup job.

A new module `src/bertytype/injection/history.py` owns this:

```python
HISTORY_PATH = Path.home() / ".bertytype" / "history.jsonl"
MAX_AGE_DAYS = 7

def append(text: str) -> None: ...
def query(since: datetime) -> list[dict]: ...
```

### Write points

`_capture_and_process()` and `_do_file_transcription()` in `__main__.py` call `history.append(text)` after a successful `injector.inject()` call.

### Tray menu

Add a "View history" submenu to the tray with three items:

- "Last 8 hours"
- "Last 24 hours"
- "Last 7 days"

Each item:
1. Calls `history.query(since=now - timedelta)` to get matching entries.
2. Writes a formatted `.txt` export to `~/.bertytype/history_export.txt` (overwritten each time), one entry per line: `[HH:MM:SS] text`.
3. Opens the file with `os.startfile()`.

If the query returns no entries, shows a tray notification: "No history in that range."

---

## 4. Configuration Profiles

### Storage

Profiles live in `~/.bertytype/profiles/<name>.json`. Each file is a full serialized `Config` (same format as `config.json`). Profile names are the filename stems; they must match `^[\w\s\-]+$` (letters, digits, spaces, hyphens, underscores), max 64 characters.

A new module `src/bertytype/profiles.py` owns this:

```python
PROFILES_DIR = Path.home() / ".bertytype" / "profiles"

def list_profiles() -> list[str]: ...       # sorted names
def load_profile(name: str) -> Config: ...
def save_profile(name: str, cfg: Config) -> None: ...
def delete_profile(name: str) -> None: ...
```

### Active profile tracking

Add `active_profile: str | None = None` to `Config`. This is display-only - the actual settings always live in the main `config.json`. When a profile is switched to, its values are written to `config.json` (with `active_profile` set to the profile name), hotkeys are re-registered, and the tray tooltip updates.

### Tray menu

Add a "Profiles" submenu:

```
Profiles >
  Save current as profile...
  ----------------------
  (list of saved profiles, checkmark on active)
```

**Save current as profile:** Opens `QInputDialog.getText()` prompting for a name. Validates the name (non-empty, safe characters). Calls `profiles.save_profile(name, current_cfg)`.

**Switch to profile:** Loads the profile config, writes it to `config.json` via `cfg_module.save()`, updates `_cfg` in `__main__.py`, re-registers hotkeys, and emits a tray notification: "Switched to [name]".

### No profile editor

Profiles are created from the current config and deleted by removing the file. There is no rename or edit UI - if you want to change a profile, switch to it, adjust settings, then save it again under the same name.

---

## Files Changed Summary

| File | Change |
|------|--------|
| `src/bertytype/logging.py` | Rename to `applog.py` |
| All files importing `bertytype.logging` | Update import to `bertytype.applog` |
| `pyproject.toml` | Add `bertytype_setup` to wheel packages; add `bertytype-setup` entry point |
| `CLAUDE.md` | Fix launch invocation |
| `src/bertytype/config.py` | Add `undo_hotkey`, `active_profile` fields |
| `src/bertytype/__main__.py` | Add `_on_undo()`, register undo hotkey, write history on injection, wire profile switching |
| `src/bertytype/ui/settings.py` | Add "Undo hotkey" field |
| `src/bertytype/ui/tray.py` | Add "View history" and "Profiles" submenus |
| `src/bertytype/injection/history.py` | New module |
| `src/bertytype/profiles.py` | New module |

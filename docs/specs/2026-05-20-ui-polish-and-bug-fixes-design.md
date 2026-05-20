# UI Polish, Audio-Reactive Waveform, and Bug Fixes - Design Spec

**Date:** 2026-05-20
**Scope:** UI refinement, animation, dark mode system, audio-reactive tray waveform, performance, and bug fixes. Larger features (transcription history, undo/redo, configuration profiles, first-run wizard, full ARIA/screen reader support) are deferred.

---

## Approach

Foundation-first sequencing: build the two shared foundations (dark mode system, audio amplitude pipeline) before layering animations, polish, and bug fixes on top. This avoids mid-flight rework because downstream tasks build on a stable base.

---

## Section 1: Foundations

### 1A. Dark Mode System

**Goal:** Fill QSS gaps in the existing dark theme AND react to Windows system theme, switching to a light palette when the OS is in light mode.

**Implementation:**

- `tokens.py` gets a second palette - a light-mode variant with near-white surfaces, dark text, and the same green/red/orange semantic accents.
- `build_qss(theme: Literal["dark", "light"])` replaces the current parameter-less function. All callers pass the current theme.
- A new `ThemeWatcher` class in `ui/` polls `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme` via the Windows registry on a 2-second QTimer.
- When the registry value changes, `ThemeWatcher` emits a Qt signal connected to a handler that calls `build_qss(new_theme)` and `QApplication.setStyleSheet(...)`.
- On startup, the current system theme is detected once and the correct palette applied immediately before the tray icon appears.

**QSS Gap Fill:**

A manual audit of every Qt widget class used in the app verifies each has explicit QSS rules in both palettes:

- `QComboBox` dropdown list and popup
- `QScrollBar` (vertical and horizontal)
- `QSlider` groove and handle
- `QCheckBox` indicator
- `QToolTip`

Any widget falling back to system defaults gets explicit rules in both dark and light variants.

### 1B. Audio Amplitude Pipeline

**Goal:** Wire real microphone amplitude into the tray so bars respond to actual audio level during recording.

**Implementation:**

- New file `audio/amplitude.py`: exposes a single module-level `float` (`current_amplitude: float = 0.0`) written by the audio capture thread after each PCM chunk using a `threading.Lock`.
- Amplitude is computed as RMS of the raw PCM chunk: `np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) / 32768.0`, normalized to 0.0-1.0.
- The tray's existing 200ms QTimer tick reads `amplitude.current_amplitude` during `recording` state to compute bar targets. No new signals or queues needed - single float with a lock is sufficient.

---

## Section 2: Animation & Visual Feedback

### 2A. Easing Curves for Tray Bars

**Goal:** Smooth bar height transitions across all status changes instead of instant snaps.

**Implementation:**

- Each bar maintains a `current_height: float` stored as instance state on the tray class between ticks.
- Each tick, bars lerp toward `target_height` using exponential ease-out: `current += (target - current) * 0.35`.
- At 200ms ticks this converges in ~4 frames (~800ms), which matches natural motion feel.
- Applies to all status transitions: idle, recording, processing, error.
- No new timer needed - integrates into the existing tick loop.

### 2B. Audio-Reactive Waveform During Recording

**Goal:** During recording, tray bars respond to real mic amplitude with a natural bell-curve shape.

**Implementation:**

- Bar amplitude multipliers: `[0.6, 0.85, 1.0, 0.85, 0.6]` - center bar reacts strongest, edges softer.
- Target height formula per bar: `floor + (ceiling - floor) * amplitude * multiplier + noise`
  - Floor: 10px, Ceiling: 58px
  - Noise: small per-bar offset seeded deterministically by `(bar_index + frame_counter) % small_prime` to prevent perfectly synchronized movement.
- When amplitude is near zero (silence), bars settle near floor height via the easing curve naturally.

### 2C. Button States (Micro-interactions)

**Goal:** All interactive controls have visually distinct `:hover`, `:focus`, and `:pressed` states.

**Implementation:**

- `tokens.py` QSS already has `:hover` and `:focus` selectors. Audit and ensure:
  - `:hover` - subtle brightness shift (background lightens by ~10%)
  - `:focus` - border color changes to accent green, outline visible
  - `:pressed` - background darkens, slight scale illusion via padding adjustment
- No smooth CSS transitions (unreliable in Qt). Crisp, immediate state changes are the correct Qt idiom.
- Applies to: `QPushButton`, `QComboBox`, `QCheckBox`, `QSlider` handle.

### 2D. LLM Processing State Indicator

**Goal:** Make the processing state more informative without changing the tray icon visual.

**Implementation:**

- Tray tooltip during `processing` state: `"Processing with {config.llm_model}..."` instead of generic "Processing".
- On transcription completion, `QSystemTrayIcon.showMessage()` fires a brief OS notification: title "BertyType", body the first 60 chars of the transcribed text + ellipsis if longer.
- Notification is optional - gated on a config setting `show_completion_notification: bool = True`.

---

## Section 3: Polish & Bug Fixes

### 3A. Settings Dialog Spacing & Container Cleanup

**Goal:** Consistent spacing rhythm, remove redundant wrapper widgets.

**Implementation:**

- `QFormLayout` spacing locked to: 12px between rows, 20px top/bottom padding, 18px left/right margins.
- Any `QWidget` containers used purely as spacers replaced with `QSpacerItem`.
- Dialog minimum size policy changed from fixed `480x400` to `minimumSizeHint()` so it resizes naturally to content.

### 3B. Error State Visual Feedback

**Goal:** Make validation errors more specific and visually localized.

**Implementation:**

- On validation failure in settings, the offending field gets `border-left: 2px solid #f3727f` applied programmatically via `setStyleSheet()`. Cleared when the field is corrected.
- Footer error label behavior unchanged (red text), but messages become more specific (e.g., "Hotkey cannot be empty" rather than "Invalid settings").
- Tray tooltip in `error` state: `"Error: {last_error_message}"` - requires storing the last error string in tray state when `set_status("error", reason=...)` is called. `set_status` gets an optional `reason: str` parameter.

### 3C. Hotkey Registration Bug Fix

**Goal:** Prevent conflicts and dangling hooks on rapid settings saves or unclean exits.

**Implementation:**

- An `atexit` handler in `hotkeys/` calls `keyboard.unhook_all()` unconditionally on interpreter exit.
- A module-level `threading.Lock` in `hotkeys/` prevents concurrent re-registration (e.g., rapid settings saves).
- The `_register_hotkeys` function wraps the hotkey loop in `try/finally` so `unhook_all()` is always called before re-registering.

### 3D. Memory Leak Fixes

**Goal:** No dangling threads or uncollected Qt objects on exit.

**Implementation:**

- Audio capture threads set `daemon=True` so they don't block interpreter shutdown.
- QTimer instances in tray stored as `self._anim_timer` and `self._error_timer` (instance attributes) rather than local variables to prevent premature GC while still running.
- Audio capture `sounddevice` stream explicitly closed in a `finally` block on capture thread exit.

### 3E. DPI/Responsive Scaling

**Goal:** Settings dialog scales correctly on high-DPI displays.

**Implementation:**

- Dialog minimum width computed from `QApplication.primaryScreen().logicalDotsPerInch()`: `base_width * (dpi / 96.0)` rather than hardcoded pixels.
- Tray icon DPI handling already in place (device pixel ratio scaling) - no changes needed.

---

## Section 4: Performance & Reliability

### 4A. Slider Debounce

**Goal:** Avoid redundant validation passes on every slider tick during drag.

**Implementation:**

- Each slider's `valueChanged` signal connects to a debounce wrapper: a `QTimer` (single-shot, 150ms) reset on each signal. The actual validation runs only when the timer fires.
- Same pattern applied to text fields with live validation.

### 4B. Lazy Loading Settings Dialog

**Goal:** Remove settings dialog from startup critical path.

**Implementation:**

- `SettingsDialog` is not instantiated at startup. It is instantiated on first "Settings" click from the tray menu and stored as `self._settings_dialog` on the tray.
- On close, the dialog is hidden (`hide()`) rather than destroyed, so subsequent opens are instant.
- This removes settings dialog import and Qt widget instantiation from startup, saving ~50ms.

### 4C. Unified Exit Cleanup

**Goal:** Coordinated shutdown of all subsystems in correct order.

**Implementation:**

- `cleanup()` function in `__main__.py` registered with `atexit`.
- Shutdown order: (1) stop hotkey daemon, (2) stop audio capture, (3) stop tray animation timers, (4) `QApplication.quit()`.
- Replaces ad-hoc per-module cleanup with a single authoritative shutdown sequence.

### 4D. Keyboard Navigation

**Goal:** Settings dialog fully navigable by keyboard.

**Implementation:**

- `QWidget.setTabOrder()` called explicitly after all widgets are created, in visual top-to-bottom order.
- Save button is already the default (Enter submits) - confirmed.
- Escape key closes the dialog without saving - ensured via `keyPressEvent` override or `QDialog.reject()` connection.

### 4E. Color Contrast Audit

**Goal:** Verify all text/background combinations meet WCAG AA (4.5:1 for normal text, 3:1 for large text).

**Implementation:**

- Inline verification for key pairs:
  - `#ffffff` on `#121212`: ~19:1 (AAA pass)
  - `#b3b3b3` on `#121212`: ~7:1 (AAA pass)
  - `#888888` on `#121212`: ~5.5:1 (AA pass)
  - `#1ed760` on `#121212`: ~8.5:1 (AAA pass)
- Light mode palette values chosen to meet same standard during design.
- `#888888` (dim text) may be lightened to `#909090` in both palettes to add margin above AA.

---

## File Change Summary

| File | Change |
| ---- | ------ |
| `src/bertytype/ui/tokens.py` | Add light palette, refactor `build_qss(theme)`, fill QSS gaps, harden button states |
| `src/bertytype/ui/tray.py` | Add per-bar easing state, audio-reactive bar targets, `set_status(reason)`, processing tooltip, completion notification, store timers as instance attrs |
| `src/bertytype/ui/settings.py` | Spacing constants, field-level error highlight, slider debounce, lazy instantiation, tab order, DPI-aware sizing |
| `src/bertytype/ui/theme_watcher.py` | New file: `ThemeWatcher` class (registry poll, Qt signal) |
| `src/bertytype/audio/amplitude.py` | New file: shared amplitude float + lock, RMS computation helper |
| `src/bertytype/audio/capture.py` | Write amplitude after each chunk |
| `src/bertytype/hotkeys/__init__.py` | atexit handler, lock, try/finally around hotkey loop |
| `src/bertytype/__main__.py` | `cleanup()` function, atexit registration, lazy settings dialog wiring |

---

## Out of Scope (Deferred)

- Transcription history
- Undo/redo for text injection
- Configuration profiles
- First-run wizard
- Full ARIA labels and screen reader support
- Waveform visualization beyond tray icon (e.g., separate recording window)
- `QGraphicsOpacityEffect` smooth hover transitions (unreliable in Qt, crisp states used instead)

# Release Readiness Integration Design

**Date:** 2026-03-12  
**Scope:** Minimal-change release-readiness work for CipherClip packaging

## Goal

Bring the current app from "source tree works" to "ready to package and ship" without redesigning the Settings shell.

## Constraints

- Keep the existing Settings page shell and section structure.
- Do not re-add `Close to Tray` or `Follow System Theme` to the Settings UI.
- Favor the smallest implementation that turns persisted settings into real behavior.

## Chosen Approach

1. Keep the current backend/frontend boundaries.
2. Add a thin runtime integration layer for:
   - Windows startup registration
   - global toggle-panel hotkey registration
3. Reuse the existing shortcut text fields:
   - `Toggle Panel` becomes a real global hotkey
   - other shortcuts become real configurable in-panel shortcuts
4. Add confirmation before destructive clear-all actions in frontend surfaces.
5. Expose storage path selection with a small browse affordance, reusing existing backend storage path support.
6. Add PyInstaller-based packaging config and a repeatable Windows build script.

## Data Flow

- Frontend Settings save still sends one `SettingsState` payload.
- Backend persists settings as before.
- Runtime integration controller subscribes to state snapshots and updates OS integrations when relevant values change.
- Storage path selection flows through pywebview bridge methods and only becomes persistent after Save.

## Packaging Strategy

- Keep frontend built as static Vite assets with relative paths.
- Package `backend/main.py` with bundled `frontend/dist`.
- Default packaged-user data should live under `%LOCALAPPDATA%\\CipherClip\\data`.
- Startup command should launch the packaged executable hidden.

## Testing Strategy

- Backend unit tests for runtime path resolution, startup command generation, hotkey parsing, bridge delegation, and window visibility toggling.
- Frontend tests for clear-all confirmation, configurable shortcuts, and storage-path browse affordance.
- Existing full lint/test/build suite remains the release gate.

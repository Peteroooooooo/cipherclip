# Release Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn persisted-only release settings into working runtime behavior and add packaging/build configuration without redesigning the Settings shell.

**Architecture:** Add a backend runtime integration layer that subscribes to state snapshots, wire the window controller for hidden startup and visibility toggling, make frontend shortcuts configurable through a shared parser, expose storage path browsing through the existing pywebview bridge, and add a PyInstaller build path.

**Tech Stack:** Python 3.12, pywebview, pystray, ctypes, React 19, Vite, TypeScript, Vitest, PyInstaller

---

### Task 1: Backend Runtime Tests

**Files:**
- Create: `backend/tests/test_runtime_integration.py`
- Modify: `backend/tests/test_window.py`
- Modify: `backend/tests/test_bridge.py`

**Step 1:** Write failing tests for startup command resolution, packaged storage path resolution, hotkey parsing, runtime integration syncing, hidden startup, and bridge storage-path delegation.

**Step 2:** Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_runtime_integration.py backend/tests/test_window.py backend/tests/test_bridge.py -q
```

Expected: failure because runtime integration modules and bridge/window behaviors do not exist yet.

### Task 2: Backend Runtime Integration

**Files:**
- Create: `backend/app/runtime.py`
- Create: `backend/app/hotkeys.py`
- Create: `backend/app/runtime_integration.py`
- Modify: `backend/app/bridge.py`
- Modify: `backend/app/window.py`
- Modify: `backend/app/state.py`
- Modify: `backend/main.py`

**Step 1:** Implement runtime path helpers, startup command resolution, and hotkey parsing.

**Step 2:** Implement runtime integration controller plus Windows startup/hotkey managers.

**Step 3:** Wire window hidden startup and toggle visibility support.

**Step 4:** Re-run the backend runtime tests until green.

### Task 3: Frontend Failing Tests

**Files:**
- Modify: `frontend/src/App.test.tsx`

**Step 1:** Keep failing tests for:
- clear-all cancellation
- customized delete shortcut
- storage-path browse affordance

**Step 2:** Run:

```powershell
npm run test:run -- src/App.test.tsx
```

Expected: failing tests showing missing confirmation, missing shortcut configurability, and missing browse control.

### Task 4: Frontend Settings/Shortcut Wiring

**Files:**
- Create: `frontend/src/app/shortcuts.ts`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/app/pywebview.ts`
- Modify: `frontend/src/app/types.ts`
- Modify: `frontend/src/features/panel/QuickPanelView.tsx`
- Modify: `frontend/src/features/settings/SettingsView.tsx`
- Modify: `frontend/src/vite-env.d.ts`

**Step 1:** Add shortcut parsing/matching helpers.

**Step 2:** Make Quick Panel keyboard behavior use saved shortcut bindings.

**Step 3:** Add clear-all confirmation in Settings and panel surfaces.

**Step 4:** Add storage-path browse action while keeping save semantics explicit.

**Step 5:** Re-run `npm run test:run -- src/App.test.tsx` until green.

### Task 5: Packaging Configuration

**Files:**
- Create: `backend/requirements-build.txt`
- Create: `CipherClip.spec`
- Create: `scripts/build-release.ps1`
- Modify: `frontend/package.json`
- Modify: `README.md`

**Step 1:** Add PyInstaller build dependency and spec file.

**Step 2:** Add a repeatable PowerShell release build script that builds frontend and packages backend.

**Step 3:** Set release-oriented frontend package metadata.

**Step 4:** Document packaging/build steps.

### Task 6: Verification

**Files:**
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Step 1:** Run:

```powershell
npm run test:run
npm run build
npm run lint
.\.venv\Scripts\python -m pytest backend/tests -q
```

**Step 2:** If feasible in current environment, run the release build script for a packaging smoke test.

**Step 3:** Record outcomes in planning files and summarize any residual release risks.

# Clipboard PyWebView + React Skeleton Design

**Date:** 2026-03-11
**Scope:** Windows-only desktop skeleton for the Clipboard History V1 project

## Goal

Build a runnable Windows desktop skeleton that uses Python with `pywebview` as the shell and `React + Vite + TypeScript` as the UI. The skeleton should include:

- a quick panel shell
- a settings view shell
- a tray menu
- mock clipboard history cards
- a thin Python/JavaScript bridge

## Architecture

The project is split into two top-level applications:

- `backend/` contains the Windows desktop shell, tray integration, app state, and bridge methods exposed to the frontend.
- `frontend/` contains the React application that renders the quick panel and settings UI and calls the backend through `window.pywebview.api`.

Development mode loads the Vite dev server URL inside `pywebview`. Production mode is prepared to load `frontend/dist/index.html`.

## UX Direction

The UI should feel intentional and desktop-first rather than like a browser demo:

- compact floating panel layout
- warm neutral light theme with slate, paper, and rust accents
- subtle shadow and blur treatment
- fast 160-220ms transitions
- keyboard-visible focus states

## Module Boundaries

### Backend

- `main.py`: startup entrypoint
- `app/window.py`: window bootstrap and URL resolution
- `app/bridge.py`: API exposed to React
- `app/state.py`: in-memory app state and mock data operations
- `app/tray.py`: tray icon and menu actions
- `app/models.py`: typed data models

### Frontend

- `src/app/App.tsx`: root view switcher
- `src/app/pywebview.ts`: safe bridge wrapper
- `src/features/panel/*`: quick panel UI
- `src/features/settings/*`: settings UI
- `src/features/history/*`: history card list, mock mapping, and types
- `src/shared/ui/*`: reusable UI primitives

## Data Flow

1. React boots and loads initial state from Python.
2. Python returns the current pause state, active view, and mock records.
3. React renders the appropriate shell.
4. User interactions call bridge methods.
5. Python updates in-memory state and returns the new snapshot.
6. React updates from the returned snapshot.

## Out of Scope

This skeleton does not implement:

- real clipboard monitoring
- real global shortcuts
- real paste automation
- real persistence
- full packaging

These stay as extension points behind the existing module boundaries.

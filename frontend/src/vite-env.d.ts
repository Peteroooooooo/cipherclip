/// <reference types="vite/client" />

import type { AppSnapshot, AppView, SettingsState } from './app/types'

declare global {
  interface Window {
    pywebview?: {
      api: {
        get_app_state: () => Promise<AppSnapshot>
        set_view: (view: AppView) => Promise<AppSnapshot>
        toggle_pause: () => Promise<AppSnapshot>
        toggle_always_on_top: () => Promise<AppSnapshot>
        toggle_pin: (recordId: string) => Promise<AppSnapshot>
        delete_record: (recordId: string) => Promise<AppSnapshot>
        undo_delete: () => Promise<AppSnapshot>
        clear_all_history: () => Promise<AppSnapshot>
        clear_unpinned_history: () => Promise<AppSnapshot>
        copy_record: (recordId: string) => Promise<AppSnapshot>
        trigger_primary_action: (recordId: string) => Promise<AppSnapshot>
        paste_plain_text: (recordId: string) => Promise<AppSnapshot>
        save_settings: (settings: SettingsState, pauseRecording: boolean) => Promise<AppSnapshot>
        restore_default_shortcuts: () => Promise<AppSnapshot>
        dismiss_toast: () => Promise<AppSnapshot>
        hide_window: () => Promise<void>
        pick_storage_path: (currentPath: string) => Promise<string | null>
        confirm_clear_all_history: () => Promise<boolean>
      }
    }
  }
}

export {}

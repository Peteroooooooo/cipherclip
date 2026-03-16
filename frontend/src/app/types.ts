export type AppView = 'panel' | 'settings'

export type HistoryRecordType = 'text' | 'rich_text' | 'image' | 'file'

export interface HistoryRecord {
  id: string
  type: HistoryRecordType
  summary: string
  detail: string
  meta: string
  sourceApp: string
  sourceGlyph: string
  pinned: boolean
  createdAt: string
  updatedAt: string
  contentHash: string
  plainText: string | null
  richText: string | null
  imagePath: string | null
  imageWidth: number | null
  imageHeight: number | null
  filePaths: string[]
}

export interface ShortcutBindings {
  togglePanel: string
  primaryAction: string
  pastePlainText: string
  togglePin: string
  deleteRecord: string
}

export interface SettingsState {
  launchOnStartup: boolean
  closeToTray: boolean
  followSystemTheme: boolean
  recordText: boolean
  recordRichText: boolean
  historyLimit: number
  recordImages: boolean
  recordFiles: boolean
  storagePath: string
  shortcuts: ShortcutBindings
}

export type ToastTone = 'neutral' | 'success' | 'danger'

export type ToastActionKind = 'undo_delete' | null

export interface ToastMessage {
  id: string
  message: string
  tone: ToastTone
  title: string
  actionLabel?: string
  actionKind: ToastActionKind
}

export interface AppSnapshot {
  view: AppView
  isRecordingPaused: boolean
  pinnedRecords: HistoryRecord[]
  recentRecords: HistoryRecord[]
  settings: SettingsState
  toast: ToastMessage | null
}

import type { AppSnapshot, AppView, HistoryRecord, SettingsState, ToastMessage } from './types'

type WindowApi = {
  get_app_state: () => Promise<AppSnapshot>
  set_view: (view: AppView) => Promise<AppSnapshot>
  toggle_pause: () => Promise<AppSnapshot>
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

type SnapshotListener = (snapshot: AppSnapshot) => void

let deletedRecord: HistoryRecord | null = null

const defaultSettings: SettingsState = {
  launchOnStartup: true,
  closeToTray: true,
  followSystemTheme: true,
  recordText: true,
  recordRichText: true,
  textHistoryLimit: 1000,
  imageHistoryLimit: 100,
  recordImages: true,
  recordFiles: true,
  storagePath: '%LOCALAPPDATA%\\CipherClip\\data',
  shortcuts: {
    togglePanel: 'Alt + Space',
    primaryAction: 'Enter',
    pastePlainText: 'Ctrl + Shift + V',
    togglePin: 'Ctrl + P',
    deleteRecord: 'Delete',
  },
}

function normalizeSettings(settings: Partial<SettingsState>): SettingsState {
  return {
    ...structuredClone(defaultSettings),
    ...settings,
    shortcuts: {
      ...structuredClone(defaultSettings.shortcuts),
      ...(settings.shortcuts ?? {}),
    },
  }
}

function createMockRecords(): HistoryRecord[] {
  return [
    {
      id: 'text-1',
      type: 'text',
      summary: 'Build review notes for the quick panel and tray wiring.',
      detail: 'Build review notes for the quick panel and tray wiring.',
      meta: 'Text · 126 chars',
      sourceApp: 'PowerShell',
      sourceGlyph: 'PS',
      pinned: true,
      createdAt: '2026-03-11T10:14:00',
      updatedAt: '2026-03-11T10:14:00',
      contentHash: 'hash-text-1',
      plainText: 'Build review notes for the quick panel and tray wiring.',
      richText: null,
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: [],
    },
    {
      id: 'image-1',
      type: 'image',
      summary: 'Screenshot capture with 1440 × 900 preview ready to paste.',
      detail: 'Screenshot capture with 1440 × 900 preview ready to paste.',
      meta: 'Image · 1440 × 900',
      sourceApp: 'Snipping Tool',
      sourceGlyph: 'ST',
      pinned: true,
      createdAt: '2026-03-11T10:03:00',
      updatedAt: '2026-03-11T10:03:00',
      contentHash: 'hash-image-1',
      plainText: null,
      richText: null,
      imagePath: 'https://picsum.photos/seed/cipher1/64/64',
      imageWidth: 1440,
      imageHeight: 900,
      filePaths: [],
    },
    {
      id: 'rich-1',
      type: 'rich_text',
      summary: 'Meeting summary with bullet formatting for the V1 launch checklist.',
      detail: 'Meeting summary with bullet formatting for the V1 launch checklist.',
      meta: 'Rich text · 2.1 KB',
      sourceApp: 'Word',
      sourceGlyph: 'W',
      pinned: false,
      createdAt: '2026-03-11T09:51:00',
      updatedAt: '2026-03-11T09:51:00',
      contentHash: 'hash-rich-1',
      plainText: 'Meeting summary with bullet formatting for the V1 launch checklist.',
      richText: '<ul><li>Meeting summary with bullet formatting for the V1 launch checklist.</li></ul>',
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: [],
    },
    {
      id: 'file-1',
      type: 'file',
      summary: 'wireframe.png and 3 more files from the design handoff folder.',
      detail: 'wireframe.png and 3 more files from the design handoff folder.',
      meta: 'Files · 4 items',
      sourceApp: 'Explorer',
      sourceGlyph: 'EX',
      pinned: false,
      createdAt: '2026-03-11T09:32:00',
      updatedAt: '2026-03-11T09:32:00',
      contentHash: 'hash-file-1',
      plainText: 'wireframe.png and 3 more files from the design handoff folder.',
      richText: null,
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: [
        'mock-handoff\\wireframe.png',
        'mock-handoff\\handoff-notes.docx',
        'mock-handoff\\tokens.json',
        'mock-handoff\\review.png',
      ],
    },
    {
      id: 'text-2',
      type: 'text',
      summary: 'npm run test:run',
      detail: 'npm run test:run',
      meta: 'Text · command',
      sourceApp: 'Terminal',
      sourceGlyph: 'TM',
      pinned: false,
      createdAt: '2026-03-11T09:12:00',
      updatedAt: '2026-03-11T09:12:00',
      contentHash: 'hash-text-2',
      plainText: 'npm run test:run',
      richText: null,
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: [],
    },
    {
      id: 'text-3',
      type: 'text',
      summary: 'ssh deploy@staging-box',
      detail: 'ssh deploy@staging-box',
      meta: 'Text · command',
      sourceApp: 'Git Bash',
      sourceGlyph: 'GB',
      pinned: false,
      createdAt: '2026-03-11T08:58:00',
      updatedAt: '2026-03-11T08:58:00',
      contentHash: 'hash-text-3',
      plainText: 'ssh deploy@staging-box',
      richText: null,
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: [],
    },
    {
      id: 'rich-2',
      type: 'rich_text',
      summary: 'Sprint recap: finish tray wiring, validate pywebview bridge, update README.',
      detail: 'Sprint recap: finish tray wiring, validate pywebview bridge, update README.',
      meta: 'Rich text · 3.4 KB',
      sourceApp: 'Notion',
      sourceGlyph: 'N',
      pinned: false,
      createdAt: '2026-03-11T08:43:00',
      updatedAt: '2026-03-11T08:43:00',
      contentHash: 'hash-rich-2',
      plainText: 'Sprint recap: finish tray wiring, validate pywebview bridge, update README.',
      richText: '<p>Sprint recap: finish tray wiring, validate pywebview bridge, update README.</p>',
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: [],
    },
    {
      id: 'file-2',
      type: 'file',
      summary: 'release-notes.docx from mock-handoff',
      detail: 'release-notes.docx from mock-handoff',
      meta: 'File · DOCX',
      sourceApp: 'Explorer',
      sourceGlyph: 'EX',
      pinned: false,
      createdAt: '2026-03-11T08:26:00',
      updatedAt: '2026-03-11T08:26:00',
      contentHash: 'hash-file-2',
      plainText: 'release-notes.docx from mock-handoff',
      richText: null,
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: ['mock-handoff\\release-notes.docx'],
    },
    {
      id: 'image-2',
      type: 'image',
      summary: 'Component snapshot with 1280 × 720 preview for settings page review.',
      detail: 'Component snapshot with 1280 × 720 preview for settings page review.',
      meta: 'Image · 1280 × 720',
      sourceApp: 'Figma',
      sourceGlyph: 'FG',
      pinned: false,
      createdAt: '2026-03-11T08:10:00',
      updatedAt: '2026-03-11T08:10:00',
      contentHash: 'hash-image-2',
      plainText: null,
      richText: null,
      imagePath: 'https://picsum.photos/seed/cipher2/64/64',
      imageWidth: 1280,
      imageHeight: 720,
      filePaths: [],
    },
    {
      id: 'text-4',
      type: 'text',
      summary: 'pnpm add pywebview pystray pillow',
      detail: 'pnpm add pywebview pystray pillow',
      meta: 'Text · command',
      sourceApp: 'Warp',
      sourceGlyph: 'WP',
      pinned: false,
      createdAt: '2026-03-11T07:54:00',
      updatedAt: '2026-03-11T07:54:00',
      contentHash: 'hash-text-4',
      plainText: 'pnpm add pywebview pystray pillow',
      richText: null,
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: [],
    },
    {
      id: 'text-5',
      type: 'text',
      summary: 'Color token note: use warm paper background with rust accent and slate text.',
      detail: 'Color token note: use warm paper background with rust accent and slate text.',
      meta: 'Text · 92 chars',
      sourceApp: 'VS Code',
      sourceGlyph: 'VS',
      pinned: true,
      createdAt: '2026-03-11T07:40:00',
      updatedAt: '2026-03-11T07:40:00',
      contentHash: 'hash-text-5',
      plainText: 'Color token note: use warm paper background with rust accent and slate text.',
      richText: null,
      imagePath: null,
      imageWidth: null,
      imageHeight: null,
      filePaths: [],
    },
  ]
}

function createSnapshot(): AppSnapshot {
  const records = createMockRecords()

  return {
    view: 'panel',
    isRecordingPaused: false,
    pinnedRecords: records.filter((record) => record.pinned),
    recentRecords: records.filter((record) => !record.pinned),
    settings: normalizeSettings(defaultSettings),
    toast: null,
  }
}

let fallbackSnapshot = createSnapshot()
const listeners = new Set<SnapshotListener>()

function cloneSnapshot(snapshot: AppSnapshot): AppSnapshot {
  return structuredClone(snapshot)
}

function emitSnapshot(snapshot: AppSnapshot) {
  const cloned = cloneSnapshot(snapshot)
  for (const listener of listeners) {
    listener(cloned)
  }
}

function nextToast(toast: ToastMessage): ToastMessage {
  return {
    ...toast,
    id: `${toast.title}-${Date.now()}`,
  }
}

function allRecords(snapshot: AppSnapshot) {
  return [...snapshot.pinnedRecords, ...snapshot.recentRecords]
}

function repartition(records: HistoryRecord[]) {
  const sorted = [...records].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
  return {
    pinnedRecords: sorted.filter((record) => record.pinned),
    recentRecords: sorted.filter((record) => !record.pinned),
  }
}

function findRecord(snapshot: AppSnapshot, recordId: string) {
  return allRecords(snapshot).find((record) => record.id === recordId) ?? null
}

function applyFallbackMutation(mutator: (draft: AppSnapshot) => void) {
  const draft = cloneSnapshot(fallbackSnapshot)
  mutator(draft)
  fallbackSnapshot = draft
  emitSnapshot(fallbackSnapshot)
  return cloneSnapshot(fallbackSnapshot)
}

function fallbackApi(): WindowApi {
  return {
    async get_app_state() {
      return cloneSnapshot(fallbackSnapshot)
    },
    async set_view(view) {
      return applyFallbackMutation((draft) => {
        draft.view = view
      })
    },
    async toggle_pause() {
      return applyFallbackMutation((draft) => {
        draft.isRecordingPaused = !draft.isRecordingPaused
        draft.toast = nextToast({
          id: '',
          title: draft.isRecordingPaused ? '记录已暂停' : '已恢复记录',
          message: draft.isRecordingPaused
            ? '新的剪贴板内容暂时不会进入历史。'
            : '新的剪贴板内容会继续进入历史。',
          tone: draft.isRecordingPaused ? 'danger' : 'success',
          actionKind: null,
        })
      })
    },
    async toggle_pin(recordId) {
      return applyFallbackMutation((draft) => {
        const record = findRecord(draft, recordId)
        if (!record) {
          return
        }

        record.pinned = !record.pinned
        record.updatedAt = new Date().toISOString()
        const groups = repartition(allRecords(draft))
        draft.pinnedRecords = groups.pinnedRecords
        draft.recentRecords = groups.recentRecords
        draft.toast = nextToast({
          id: '',
          title: record.pinned ? '已固定记录' : '已取消固定',
          message: record.summary,
          tone: 'success',
          actionKind: null,
        })
      })
    },
    async delete_record(recordId) {
      return applyFallbackMutation((draft) => {
        const record = findRecord(draft, recordId)
        if (!record) {
          return
        }

        deletedRecord = structuredClone(record)
        draft.pinnedRecords = draft.pinnedRecords.filter((item) => item.id !== recordId)
        draft.recentRecords = draft.recentRecords.filter((item) => item.id !== recordId)
        draft.toast = nextToast({
          id: '',
          title: '记录已删除',
          message: record.summary,
          tone: 'danger',
          actionLabel: '撤销',
          actionKind: 'undo_delete',
        })
      })
    },
    async undo_delete() {
      return applyFallbackMutation((draft) => {
        if (!deletedRecord) {
          return
        }

        const groups = repartition([...allRecords(draft), deletedRecord])
        draft.pinnedRecords = groups.pinnedRecords
        draft.recentRecords = groups.recentRecords
        draft.toast = nextToast({
          id: '',
          title: '已恢复删除的记录',
          message: deletedRecord.summary,
          tone: 'success',
          actionKind: null,
        })
        deletedRecord = null
      })
    },
    async clear_all_history() {
      return applyFallbackMutation((draft) => {
        draft.pinnedRecords = []
        draft.recentRecords = []
        draft.toast = nextToast({
          id: '',
          title: '已清空全部历史',
          message: '固定和最近记录都已移除。',
          tone: 'danger',
          actionKind: null,
        })
      })
    },
    async clear_unpinned_history() {
      return applyFallbackMutation((draft) => {
        draft.recentRecords = []
        draft.toast = nextToast({
          id: '',
          title: '已清除未固定记录',
          message: '仅保留固定记录。',
          tone: 'danger',
          actionKind: null,
        })
      })
    },
    async copy_record(recordId) {
      return applyFallbackMutation((draft) => {
        const record = findRecord(draft, recordId)
        if (!record) {
          return
        }
      })
    },
    async trigger_primary_action(recordId) {
      return applyFallbackMutation((draft) => {
        const record = findRecord(draft, recordId)
        if (!record) {
          return
        }

        draft.toast = nextToast({
          id: '',
          title: '已复制到剪贴板',
          message: record.summary,
          tone: 'success',
          actionKind: null,
        })
      })
    },
    async paste_plain_text(recordId) {
      return applyFallbackMutation((draft) => {
        const record = findRecord(draft, recordId)
        if (!record) {
          return
        }

        draft.toast = nextToast({
          id: '',
          title: '已纯文本粘贴',
          message: record.summary,
          tone: 'success',
          actionKind: null,
        })
      })
    },
    async save_settings(settings, pauseRecording) {
      return applyFallbackMutation((draft) => {
        draft.settings = normalizeSettings(settings)
        draft.isRecordingPaused = pauseRecording
        draft.view = 'panel'
        draft.toast = nextToast({
          id: '',
          title: '设置已保存',
          message: '新的应用配置已经生效。',
          tone: 'success',
          actionKind: null,
        })
      })
    },
    async restore_default_shortcuts() {
      return applyFallbackMutation((draft) => {
        draft.settings.shortcuts = structuredClone(defaultSettings.shortcuts)
        draft.toast = nextToast({
          id: '',
          title: '快捷键已恢复默认',
          message: '可以继续编辑后再保存。',
          tone: 'neutral',
          actionKind: null,
        })
      })
    },
    async dismiss_toast() {
      return applyFallbackMutation((draft) => {
        draft.toast = null
      })
    },
    async hide_window() {
      return Promise.resolve()
    },
    async pick_storage_path(currentPath) {
      const basePath = currentPath.replace(/[\\/]?data$/, '').replace(/[\\/]$/, '')
      return `${basePath}\\selected-data`
    },
    async confirm_clear_all_history() {
      return window.confirm('Clear all clipboard history? Pinned and recent clips will be removed.')
    },
  }
}

function getWindowApi(): WindowApi {
  return window.pywebview?.api ?? fallbackApi()
}

export const desktopApi = {
  getAppState() {
    return getWindowApi().get_app_state()
  },
  setView(view: AppView) {
    return getWindowApi().set_view(view)
  },
  togglePause() {
    return getWindowApi().toggle_pause()
  },
  togglePin(recordId: string) {
    return getWindowApi().toggle_pin(recordId)
  },
  deleteRecord(recordId: string) {
    return getWindowApi().delete_record(recordId)
  },
  undoDelete() {
    return getWindowApi().undo_delete()
  },
  clearAllHistory() {
    return getWindowApi().clear_all_history()
  },
  clearUnpinnedHistory() {
    return getWindowApi().clear_unpinned_history()
  },
  copyRecord(recordId: string) {
    return getWindowApi().copy_record(recordId)
  },
  triggerPrimaryAction(recordId: string) {
    return getWindowApi().trigger_primary_action(recordId)
  },
  pastePlainText(recordId: string) {
    return getWindowApi().paste_plain_text(recordId)
  },
  saveSettings(settings: SettingsState, pauseRecording: boolean) {
    return getWindowApi().save_settings(settings, pauseRecording)
  },
  restoreDefaultShortcuts() {
    return getWindowApi().restore_default_shortcuts()
  },
  dismissToast() {
    return getWindowApi().dismiss_toast()
  },
  hideWindow() {
    return getWindowApi().hide_window()
  },
  pickStoragePath(currentPath: string) {
    return getWindowApi().pick_storage_path(currentPath)
  },
  confirmClearAllHistory() {
    return getWindowApi().confirm_clear_all_history()
  },
}

export function subscribeSnapshot(listener: SnapshotListener) {
  const onEvent = (event: Event) => {
    const customEvent = event as CustomEvent<AppSnapshot>
    listener(customEvent.detail)
  }

  listeners.add(listener)
  window.addEventListener('clipboard:snapshot', onEvent)

  return () => {
    listeners.delete(listener)
    window.removeEventListener('clipboard:snapshot', onEvent)
  }
}

export function resetDesktopApiMock() {
  deletedRecord = null
  fallbackSnapshot = createSnapshot()
  listeners.clear()
}

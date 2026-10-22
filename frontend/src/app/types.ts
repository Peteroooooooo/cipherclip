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
  /** The source app's own icon, when the backend could read it from the app's exe. */
  sourceIcon?: string | null
}

export interface ShortcutBindings {
  togglePanel: string
  primaryAction: string
  pastePlainText: string
  togglePin: string
  deleteRecord: string
}

/** Text and controls: 'auto' picks white or black from how bright the glass comes out. */
export type TextTone = 'auto' | 'light' | 'dark'

/** Where the window glass gets its picture: the live compositor blur, or a desktop snapshot. */
export type GlassSource = 'live' | 'snapshot'

export type LiquidMode = 'standard' | 'polar' | 'prominent' | 'shader'

/**
 * Every look is this one set of parameters; presets (appearance.ts) are just saved values.
 * Order of the window layers, top first: sheen, tint, backdrop.
 */
export interface AppearanceSettings {
  glassSource: GlassSource
  /** Window corner radius in px. */
  cornerRadius: number
  /** Grey level (0-255) that white on the desktop comes out at through the glass. */
  whitePoint: number
  /** Grey level (0-255) that black on the desktop comes out at; at least 4 below whitePoint. */
  blackPoint: number
  /** CSS blur() of the backdrop in px, 0-20. */
  backdropBlur: number
  /** CSS saturate() of the backdrop in %. */
  backdropSaturation: number
  /** Diagonal rim light that catches the corners, 0-100 (%). */
  rimLight: number
  /** Top sheen, top 1px light and a brighter outline, 0-100 (%). */
  edgeHighlight: number
  textTone: TextTone
  /** Glow behind the text (dark behind white text, light behind black), 0-100 (%). */
  textHalo: number
  /** Opacity of secondary text, 30-100 (%). */
  secondaryTextOpacity: number
  liquidEnabled: boolean
  liquidMode: LiquidMode
  displacementScale: number
  aberrationIntensity: number
  elasticity: number
  /** Frost of liquid controls, 0-1 (liquid-glass-react's blurAmount). */
  frost: number
  liquidSaturation: number
  /** Dark layer inside liquid controls, 0-50 (%): calmer glass over bright content. */
  liquidShade: number
  animations: boolean
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
  appearance: AppearanceSettings
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
  isAlwaysOnTop: boolean
  pinnedRecords: HistoryRecord[]
  recentRecords: HistoryRecord[]
  settings: SettingsState
  toast: ToastMessage | null
}

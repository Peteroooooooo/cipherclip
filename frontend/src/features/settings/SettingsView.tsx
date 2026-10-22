import { useState } from 'react'
import { ArrowCounterClockwise, CaretDown, CaretLeft, CaretUp, FloppyDisk, X } from '@phosphor-icons/react'
import { DEFAULT_APPEARANCE } from '../../app/appearance'
import type { AppearanceSettings, SettingsState, ShortcutBindings } from '../../app/types'
import { AppearanceSections, type GlassInfo } from './AppearanceSections'
import { ToggleRow } from './controls'

export type { GlassInfo }

interface SettingsViewProps {
  settings: SettingsState
  glassInfo?: GlassInfo
  onSave: (settings: SettingsState) => void
  onCancel: () => void
  /** Resolves to the factory shortcuts, which only replace the unsaved draft. */
  onRestoreDefaults: () => Promise<ShortcutBindings>
  onClearAllHistory: () => void
  onPickStoragePath: (currentPath: string) => Promise<string | null>
  /** Called with the unsaved appearance on every edit, so the app can show it live. */
  onPreviewAppearance?: (appearance: AppearanceSettings) => void
}

const HISTORY_LIMIT_MIN = 1
const HISTORY_LIMIT_MAX = 5000


function ShortcutRow({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="shortcut-row">
      <span className="field-label">
        <strong>{label}</strong>
      </span>
      <input className="field-input" onChange={(event) => onChange(event.target.value)} value={value} />
    </label>
  )
}

function clampHistoryLimit(value: number) {
  if (!Number.isFinite(value)) {
    return HISTORY_LIMIT_MIN
  }

  return Math.min(HISTORY_LIMIT_MAX, Math.max(HISTORY_LIMIT_MIN, Math.trunc(value)))
}

const NO_GLASS: GlassInfo = { mode: null, liveAvailable: false }

export function SettingsView({
  settings,
  glassInfo = NO_GLASS,
  onSave,
  onCancel,
  onRestoreDefaults,
  onClearAllHistory,
  onPickStoragePath,
  onPreviewAppearance,
}: SettingsViewProps) {
  const [draft, setDraft] = useState(settings)

  const setAppearance = (appearance: AppearanceSettings) => {
    setDraft((currentDraft) => ({ ...currentDraft, appearance }))
    onPreviewAppearance?.(appearance)
  }
  const [historyLimitInput, setHistoryLimitInput] = useState(String(settings.historyLimit))

  const updateHistoryLimit = (value: number) => {
    const nextValue = clampHistoryLimit(value)
    setDraft((currentDraft) => ({
      ...currentDraft,
      historyLimit: nextValue,
    }))
    setHistoryLimitInput(String(nextValue))
  }

  // Snapshots are pushed whenever anything changes (e.g. a new clip arrives), each with a
  // fresh settings object. Only reset the draft when the saved values actually change,
  // otherwise background pushes would wipe what the user is typing.
  const settingsKey = JSON.stringify(settings)
  const [syncedSettingsKey, setSyncedSettingsKey] = useState(settingsKey)

  if (settingsKey !== syncedSettingsKey) {
    setSyncedSettingsKey(settingsKey)
    setDraft(settings)
    setHistoryLimitInput(String(settings.historyLimit))
  }

  return (
    <section className="settings-shell">
      <header className="settings-header">
        <button aria-label="Back" className="icon-button" onClick={onCancel} title="Back" type="button">
          <CaretLeft size={17} weight="bold" />
        </button>
        <div className="window-drag-region settings-title">
          <h1>Settings</h1>
          <p>Configure CipherClip behavior, shortcuts, and storage.</p>
        </div>
      </header>

      <div className="settings-scroll">
        <section aria-labelledby="general-heading" className="settings-section">
          <h2 id="general-heading">General</h2>
          <div className="settings-grid">
            <ToggleRow
              checked={draft.launchOnStartup}
              description="Auto-run after Windows login"
              label="Launch on Startup"
              onClick={() => setDraft({ ...draft, launchOnStartup: !draft.launchOnStartup })}
            />
          </div>
        </section>

        <AppearanceSections
          appearance={draft.appearance}
          glassInfo={glassInfo}
          onChange={(patch) => setAppearance({ ...draft.appearance, ...patch })}
          onReset={() => setAppearance(DEFAULT_APPEARANCE)}
        />

        <section aria-labelledby="capture-heading" className="settings-section">
          <h2 id="capture-heading">Capture</h2>
          <div className="settings-grid">
            <ToggleRow
              checked={draft.recordText}
              description="Store plain text copied from apps"
              label="Record Text"
              onClick={() => setDraft({ ...draft, recordText: !draft.recordText })}
            />
            <ToggleRow
              checked={draft.recordRichText}
              description="Keep formatting when rich content is available"
              label="Record Rich Text"
              onClick={() => setDraft({ ...draft, recordRichText: !draft.recordRichText })}
            />
            <ToggleRow
              checked={draft.recordImages}
              description="Store copied screenshots and image clips"
              label="Record Images"
              onClick={() => setDraft({ ...draft, recordImages: !draft.recordImages })}
            />
            <ToggleRow
              checked={draft.recordFiles}
              description="Keep copied files and file groups in history"
              label="Record Files"
              onClick={() => setDraft({ ...draft, recordFiles: !draft.recordFiles })}
            />
          </div>
        </section>

        <section aria-labelledby="shortcut-heading" className="settings-section">
          <h2 id="shortcut-heading">Shortcuts</h2>
          <div className="shortcut-grid">
            <ShortcutRow
              label="Toggle Panel"
              onChange={(value) =>
                setDraft({
                  ...draft,
                  shortcuts: { ...draft.shortcuts, togglePanel: value },
                })
              }
              value={draft.shortcuts.togglePanel}
            />
            <ShortcutRow
              label="Primary Action"
              onChange={(value) =>
                setDraft({
                  ...draft,
                  shortcuts: { ...draft.shortcuts, primaryAction: value },
                })
              }
              value={draft.shortcuts.primaryAction}
            />
            <ShortcutRow
              label="Plain Text Paste"
              onChange={(value) =>
                setDraft({
                  ...draft,
                  shortcuts: { ...draft.shortcuts, pastePlainText: value },
                })
              }
              value={draft.shortcuts.pastePlainText}
            />
            <ShortcutRow
              label="Toggle Pin"
              onChange={(value) =>
                setDraft({
                  ...draft,
                  shortcuts: { ...draft.shortcuts, togglePin: value },
                })
              }
              value={draft.shortcuts.togglePin}
            />
            <ShortcutRow
              label="Delete Record"
              onChange={(value) =>
                setDraft({
                  ...draft,
                  shortcuts: { ...draft.shortcuts, deleteRecord: value },
                })
              }
              value={draft.shortcuts.deleteRecord}
            />
          </div>
          <button
            className="ghost-button"
            onClick={() =>
              void onRestoreDefaults().then((shortcuts) => setDraft((currentDraft) => ({ ...currentDraft, shortcuts })))
            }
            type="button"
          >
            <ArrowCounterClockwise size={14} weight="bold" />
            Restore Defaults
          </button>
        </section>

        <section aria-labelledby="history-heading" className="settings-section">
          <h2 id="history-heading">History &amp; Storage</h2>
          <div className="settings-grid">
            <label className="field-row">
              <span className="field-label">
                <strong>History Limit</strong>
                <span>Max unpinned records to keep. Pinned items always stay.</span>
              </span>
              <div className="stepper-control">
                <input
                  aria-label="History Limit"
                  className="stepper-input"
                  inputMode="numeric"
                  max={HISTORY_LIMIT_MAX}
                  min={HISTORY_LIMIT_MIN}
                  onBlur={() => {
                    if (historyLimitInput.trim() === '') {
                      setHistoryLimitInput(String(draft.historyLimit))
                    }
                  }}
                  onChange={(event) => {
                    const nextValue = event.target.value
                    setHistoryLimitInput(nextValue)

                    if (nextValue.trim() === '') {
                      return
                    }

                    updateHistoryLimit(Number(nextValue))
                  }}
                  type="number"
                  value={historyLimitInput}
                />
                <div className="stepper-buttons">
                  <button
                    aria-label="Increase history limit"
                    className="stepper-button"
                    onClick={() => updateHistoryLimit(draft.historyLimit + 1)}
                    type="button"
                  >
                    <CaretUp size={12} weight="bold" />
                  </button>
                  <button
                    aria-label="Decrease history limit"
                    className="stepper-button"
                    onClick={() => updateHistoryLimit(draft.historyLimit - 1)}
                    type="button"
                  >
                    <CaretDown size={12} weight="bold" />
                  </button>
                </div>
              </div>
            </label>
            <div className="field-row field-row-storage">
              <div className="field-label">
                <strong>Storage Path</strong>
                <span>Choose where local history and images are stored</span>
              </div>
              <div className="storage-path-stack" data-testid="storage-path-stack">
                <div className="storage-path-value" data-testid="storage-path-value" title={draft.storagePath}>
                  {draft.storagePath}
                </div>
                <button
                  className="ghost-button storage-path-browse"
                  onClick={() =>
                    void onPickStoragePath(draft.storagePath).then((selectedPath) => {
                      if (!selectedPath) {
                        return
                      }

                      setDraft((currentDraft) => ({
                        ...currentDraft,
                        storagePath: selectedPath,
                      }))
                    })
                  }
                  type="button"
                >
                  Browse
                </button>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="data-heading" className="settings-section settings-section-danger">
          <h2 id="data-heading">Data Management</h2>
          <div className="settings-grid">
            <div className="field-row field-row-actions">
              <div className="field-label">
                <strong>Clear All History</strong>
                <span>Remove pinned and recent clips from local history</span>
              </div>
              <button className="danger-button" onClick={onClearAllHistory} type="button">
                Clear All History
              </button>
            </div>
          </div>
        </section>
      </div>

      <footer className="settings-footer">
        <button className="ghost-button" onClick={onCancel} type="button">
          <X size={14} weight="bold" />
          Cancel
        </button>
        <button className="primary-button" onClick={() => onSave(draft)} type="button">
          <FloppyDisk size={15} />
          Save
        </button>
      </footer>
    </section>
  )
}

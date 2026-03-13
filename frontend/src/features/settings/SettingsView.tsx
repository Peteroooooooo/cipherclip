import { useEffect, useState } from 'react'
import { ArrowLeft, RotateCcw, Save, X } from 'lucide-react'
import type { SettingsState } from '../../app/types'

interface SettingsViewProps {
  settings: SettingsState
  onSave: (settings: SettingsState) => void
  onCancel: () => void
  onRestoreDefaults: () => void
  onClearAllHistory: () => void
  onPickStoragePath: (currentPath: string) => Promise<string | null>
}

function Toggle({
  checked,
  label,
  onClick,
}: {
  checked: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      aria-label={label}
      aria-pressed={checked}
      className={`toggle ${checked ? 'is-on' : ''}`}
      onClick={onClick}
      type="button"
    />
  )
}

function ToggleRow({
  checked,
  description,
  label,
  onClick,
}: {
  checked: boolean
  description: string
  label: string
  onClick: () => void
}) {
  return (
    <div className="field-row">
      <div className="field-label">
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <Toggle checked={checked} label={label} onClick={onClick} />
    </div>
  )
}

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

export function SettingsView({
  settings,
  onSave,
  onCancel,
  onRestoreDefaults,
  onClearAllHistory,
  onPickStoragePath,
}: SettingsViewProps) {
  const [draft, setDraft] = useState(settings)

  useEffect(() => {
    setDraft(settings)
  }, [settings])

  return (
    <section className="settings-shell">
      <header className="settings-header">
        <div>
          <h1>Settings</h1>
          <p>Configure CipherClip behavior, shortcuts, and storage.</p>
        </div>
        <button aria-label="Back" className="icon-button" onClick={onCancel} title="Back" type="button">
          <ArrowLeft size={18} />
        </button>
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
          <button className="ghost-button" onClick={onRestoreDefaults} type="button">
            <RotateCcw size={14} />
            Restore Defaults
          </button>
        </section>

        <section aria-labelledby="history-heading" className="settings-section">
          <h2 id="history-heading">History &amp; Storage</h2>
          <div className="settings-grid">
            <label className="field-row">
              <span className="field-label">
                <strong>Text Clip Limit</strong>
                <span>100 – 5000</span>
              </span>
              <input
                className="field-input"
                max={5000}
                min={100}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    textHistoryLimit: Number(event.target.value),
                  })
                }
                type="number"
                value={draft.textHistoryLimit}
              />
            </label>
            <label className="field-row">
              <span className="field-label">
                <strong>Image Clip Limit</strong>
                <span>10 – 500</span>
              </span>
              <input
                className="field-input"
                max={500}
                min={10}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    imageHistoryLimit: Number(event.target.value),
                  })
                }
                type="number"
                value={draft.imageHistoryLimit}
              />
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
          <X size={14} />
          Cancel
        </button>
        <button className="primary-button" onClick={() => onSave(draft)} type="button">
          <Save size={14} />
          Save
        </button>
      </footer>
    </section>
  )
}

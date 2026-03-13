import { startTransition, useEffect, useState } from 'react'
import { QuickPanelView } from '../features/panel/QuickPanelView'
import { SettingsView } from '../features/settings/SettingsView'
import { desktopApi, subscribeSnapshot } from './pywebview'
import type { AppSnapshot, SettingsState } from './types'

function App() {
  const [snapshot, setSnapshot] = useState<AppSnapshot | null>(null)

  useEffect(() => {
    let mounted = true

    desktopApi.getAppState().then((nextSnapshot) => {
      if (!mounted) {
        return
      }

      startTransition(() => {
        setSnapshot(nextSnapshot)
      })
    })

    const unsubscribe = subscribeSnapshot((nextSnapshot) => {
      startTransition(() => {
        setSnapshot(nextSnapshot)
      })
    })

    return () => {
      mounted = false
      unsubscribe()
    }
  }, [])

  async function syncSnapshot(promise: Promise<AppSnapshot>) {
    const nextSnapshot = await promise
    startTransition(() => {
      setSnapshot(nextSnapshot)
    })
  }

  const handleClearHistory = async () => {
    await syncSnapshot(desktopApi.clearUnpinnedHistory())
  }

  const handleClearAllHistory = async () => {
    if (!(await desktopApi.confirmClearAllHistory())) {
      return
    }

    await syncSnapshot(desktopApi.clearAllHistory())
  }

  if (!snapshot) {
    return (
      <main className="app-shell">
        <div className="app-loading">正在初始化 CipherClip…</div>
      </main>
    )
  }

  const frame =
    snapshot.view === 'settings' ? (
      <SettingsView
        onCancel={() => syncSnapshot(desktopApi.setView('panel'))}
        onClearAllHistory={() => void handleClearAllHistory()}
        onPickStoragePath={(currentPath: string) => desktopApi.pickStoragePath(currentPath)}
        onRestoreDefaults={() => syncSnapshot(desktopApi.restoreDefaultShortcuts())}
        onSave={(settings: SettingsState) =>
          syncSnapshot(desktopApi.saveSettings(settings, snapshot.isRecordingPaused))
        }
        settings={snapshot.settings}
      />
    ) : (
      <QuickPanelView
        shortcuts={snapshot.settings.shortcuts}
        isRecordingPaused={snapshot.isRecordingPaused}
        onClearHistory={() => void handleClearHistory()}
        onCopy={(recordId: string) => syncSnapshot(desktopApi.copyRecord(recordId))}
        onDelete={(recordId: string) => syncSnapshot(desktopApi.deleteRecord(recordId))}
        onHideWindow={() => desktopApi.hideWindow()}
        onOpenSettings={() => syncSnapshot(desktopApi.setView('settings'))}
        onPastePlainText={(recordId: string) => syncSnapshot(desktopApi.pastePlainText(recordId))}
        onPrimaryAction={(recordId: string) => syncSnapshot(desktopApi.triggerPrimaryAction(recordId))}
        onTogglePause={() => syncSnapshot(desktopApi.togglePause())}
        onTogglePin={(recordId: string) => syncSnapshot(desktopApi.togglePin(recordId))}
        pinnedRecords={snapshot.pinnedRecords}
        recentRecords={snapshot.recentRecords}
      />
    )

  return (
    <main className="app-shell">
      {frame}
    </main>
  )
}

export default App

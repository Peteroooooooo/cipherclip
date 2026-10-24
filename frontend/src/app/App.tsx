import { startTransition, useCallback, useEffect, useMemo, useState } from 'react'
import { MotionConfig, motion } from 'motion/react'
import { QuickPanelView } from '../features/panel/QuickPanelView'
import { SettingsView, type GlassInfo } from '../features/settings/SettingsView'
import { LiquidGlassContext } from '../shared/ui/liquid/liquidContext'
import { SPRING_SMOOTH } from '../shared/ui/motionTokens'
import { ToastHost } from '../shared/ui/ToastHost'
import { applyAppearance, DEFAULT_APPEARANCE } from './appearance'
import { desktopApi, subscribeSnapshot } from './pywebview'
import type { AppearanceSettings, AppSnapshot, SettingsState } from './types'

// How long slider drags settle before the native window (live blur, snapshot) is updated.
const NATIVE_PREVIEW_DELAY_MS = 220
const PAGE_SETTLE_CALM_MS = 150
const PAGE_SETTLE_CAP_MS = 1500

// Settings slides "forward" (zooms in from slightly larger), the panel comes back from slightly smaller.
const VIEW_ENTER = {
  panel: { opacity: 0, scale: 0.985, filter: 'blur(4px)' },
  settings: { opacity: 0, scale: 1.02, filter: 'blur(4px)' },
} as const

const VIEW_TRANSITION = {
  default: SPRING_SMOOTH,
  opacity: { duration: 0.22, ease: 'easeOut' },
  filter: { duration: 0.28, ease: 'easeOut' },
} as const

function App() {
  const [snapshot, setSnapshot] = useState<AppSnapshot | null>(null)
  // Unsaved appearance from the settings page, shown live until saved or cancelled.
  const [previewAppearance, setPreviewAppearance] = useState<AppearanceSettings | null>(null)
  const [glassInfo, setGlassInfo] = useState<GlassInfo>({ mode: null, liveAvailable: false })

  const savedAppearance = snapshot?.settings.appearance ?? DEFAULT_APPEARANCE
  // Only the settings page previews; anywhere else the saved look applies.
  const activePreview = snapshot?.view === 'settings' ? previewAppearance : null
  const appearanceKey = JSON.stringify(activePreview ?? savedAppearance)
  // Snapshots arrive as fresh objects; key on content so effects only run on real changes.
  const appearance = useMemo<AppearanceSettings>(() => JSON.parse(appearanceKey), [appearanceKey])

  useEffect(() => applyAppearance(appearance), [appearance])

  const liquidSettings = useMemo(
    // Only the desktop snapshot paints an opaque picture inside the page; live glass (and the
    // browser preview, whose window uses backdrop-filter) leave a translucent backdrop.
    () => ({ ...appearance, translucentBackdrop: glassInfo.mode !== 'snapshot' }),
    [appearance, glassInfo.mode],
  )

  useEffect(() => {
    if (!previewAppearance) {
      return
    }
    const timer = window.setTimeout(() => void desktopApi.previewAppearance(previewAppearance), NATIVE_PREVIEW_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [previewAppearance])

  useEffect(() => {
    const handleGlass = (event: Event) => {
      const detail = (event as CustomEvent<Partial<GlassInfo>>).detail
      setGlassInfo({
        mode: detail?.mode ?? null,
        liveAvailable: Boolean(detail?.liveAvailable),
        filtered: Boolean(detail?.filtered),
      })
    }
    window.addEventListener('clipdeck:glass', handleGlass)
    return () => window.removeEventListener('clipdeck:glass', handleGlass)
  }, [])

  const endAppearancePreview = useCallback(() => {
    setPreviewAppearance(null)
  }, [])

  // Settings can also be left without Cancel or Save (tray "显示主面板"); an unsaved look must not
  // outlive the page that was editing it.
  const strandedPreview = Boolean(previewAppearance) && snapshot !== null && snapshot.view !== 'settings'
  const savedAppearanceKey = JSON.stringify(savedAppearance)
  useEffect(() => {
    if (!strandedPreview) {
      return
    }
    void desktopApi.previewAppearance(JSON.parse(savedAppearanceKey)).then(() => setPreviewAppearance(null))
  }, [strandedPreview, savedAppearanceKey])

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

  const hasSnapshot = snapshot !== null
  useEffect(() => {
    if (!hasSnapshot) {
      return
    }
    // A normal launch shows the window only once the panel has settled. Right after the first
    // snapshot, cards are still arriving and nothing is painted yet (measured: ~0.35 s of empty
    // glass, then the list sliding into place); so wait for the same cards over a stretch of
    // smooth frames (frames stall while the panel is still being rasterized). Capped, so a busy
    // machine still shows the panel.
    let frame = 0
    const started = performance.now()
    let cards = -1
    let last = started
    let calmSince = started
    const tick = (now: number) => {
      const count = document.querySelectorAll('.panel-card').length
      if (count !== cards || now - last > 50) calmSince = now
      cards = count
      last = now
      if (now - calmSince >= PAGE_SETTLE_CALM_MS || now - started >= PAGE_SETTLE_CAP_MS) {
        void desktopApi.pageReady()
        return
      }
      frame = window.requestAnimationFrame(tick)
    }
    frame = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(frame)
  }, [hasSnapshot])

  const syncSnapshot = useCallback(async (promise: Promise<AppSnapshot>) => {
    const nextSnapshot = await promise
    startTransition(() => {
      setSnapshot(nextSnapshot)
    })
  }, [])

  const handleDismissToast = useCallback(() => {
    void syncSnapshot(desktopApi.dismissToast())
  }, [syncSnapshot])

  const handleToastAction = () => {
    if (snapshot?.toast?.actionKind === 'undo_delete') {
      void syncSnapshot(desktopApi.undoDelete())
    }
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
        <div className="app-loading">正在初始化 ClipDeck…</div>
      </main>
    )
  }

  const frame =
    snapshot.view === 'settings' ? (
      <SettingsView
        glassInfo={glassInfo}
        onCancel={() => {
          // Put the native window back to the saved look before leaving.
          if (previewAppearance) {
            void desktopApi.previewAppearance(snapshot.settings.appearance)
          }
          endAppearancePreview()
          void syncSnapshot(desktopApi.setView('panel'))
        }}
        onPreviewAppearance={setPreviewAppearance}
        onClearAllHistory={() => void handleClearAllHistory()}
        onPickStoragePath={(currentPath: string) => desktopApi.pickStoragePath(currentPath)}
        onRestoreDefaults={() => desktopApi.defaultShortcuts()}
        onSave={(settings: SettingsState) => {
          endAppearancePreview()
          void syncSnapshot(desktopApi.saveSettings(settings, snapshot.isRecordingPaused))
        }}
        settings={snapshot.settings}
      />
    ) : (
      <QuickPanelView
        isAlwaysOnTop={snapshot.isAlwaysOnTop}
        shortcuts={snapshot.settings.shortcuts}
        isRecordingPaused={snapshot.isRecordingPaused}
        onClearHistory={() => void handleClearHistory()}
        onCopy={(recordId: string) => syncSnapshot(desktopApi.copyRecord(recordId))}
        onDelete={(recordId: string) => syncSnapshot(desktopApi.deleteRecord(recordId))}
        onHideWindow={() => desktopApi.hideWindow()}
        onOpenSettings={() => syncSnapshot(desktopApi.setView('settings'))}
        onPastePlainText={(recordId: string) => syncSnapshot(desktopApi.pastePlainText(recordId))}
        onPrimaryAction={(recordId: string) => syncSnapshot(desktopApi.triggerPrimaryAction(recordId))}
        onToggleAlwaysOnTop={() => syncSnapshot(desktopApi.toggleAlwaysOnTop())}
        onTogglePause={() => syncSnapshot(desktopApi.togglePause())}
        onTogglePin={(recordId: string) => syncSnapshot(desktopApi.togglePin(recordId))}
        pinnedRecords={snapshot.pinnedRecords}
        recentRecords={snapshot.recentRecords}
      />
    )

  return (
    <MotionConfig reducedMotion={appearance.animations ? 'user' : 'always'}>
      <LiquidGlassContext.Provider value={liquidSettings}>
      {/* A press on the transparent shadow margin around the panel counts as clicking away. */}
      <main
        className="app-shell"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget && document.documentElement.classList.contains('is-desktop')) {
            void desktopApi.hideWindow()
          }
        }}
      >
        <div className="glass-window" data-view={snapshot.view}>
          <div aria-hidden="true" className="glass-backdrop" />
          {/* transitionEnd drops the filter afterwards: a lingering filter would keep the whole
              view on its own render surface and isolate it from backdrop-filter glass. */}
          <motion.div
            animate={{ opacity: 1, scale: 1, filter: 'blur(0px)', transitionEnd: { filter: 'none' } }}
            className="view-frame"
            initial={VIEW_ENTER[snapshot.view]}
            key={snapshot.view}
            transition={VIEW_TRANSITION}
          >
            {frame}
          </motion.div>
          <ToastHost onAction={handleToastAction} onDismiss={handleDismissToast} toast={snapshot.toast} />
        </div>
      </main>
      </LiquidGlassContext.Provider>
    </MotionConfig>
  )
}

export default App

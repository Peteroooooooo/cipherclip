import { useDeferredValue, useEffect, useRef, useState } from 'react'
import { Settings } from 'lucide-react'
import { matchesShortcut } from '../../app/shortcuts'
import type { HistoryRecord, ShortcutBindings } from '../../app/types'
import { HistoryCard } from '../history/HistoryCard'

/* Custom CipherClip logo — file with cyan lines + purple pen */
function CipherClipLogo() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* File body */}
      <path
        d="M6 2h8.5L19 6.5V20a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"
        fill="rgba(22,22,26,0.8)"
        stroke="rgba(255,255,255,0.15)"
        strokeWidth="1"
      />
      {/* Folded corner */}
      <path d="M14 2v5h5" stroke="rgba(255,255,255,0.12)" strokeWidth="1" fill="none" />
      {/* Cyan text lines */}
      <line x1="7" y1="10" x2="14" y2="10" stroke="#00F0FF" strokeWidth="1.5" strokeLinecap="round" opacity="0.8" />
      <line x1="7" y1="13" x2="12" y2="13" stroke="#00F0FF" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
      <line x1="7" y1="16" x2="10" y2="16" stroke="#00F0FF" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      {/* Purple pen, angled */}
      <g transform="translate(14.5, 8) rotate(25)">
        <rect x="0" y="0" width="3" height="12" rx="1" fill="#A855F7" opacity="0.9" />
        <polygon points="0.3,12 1.5,15 2.7,12" fill="#A855F7" opacity="0.7" />
        <rect x="0" y="0" width="3" height="2.5" rx="0.5" fill="#C084FC" opacity="0.6" />
      </g>
    </svg>
  )
}

interface QuickPanelViewProps {
  isRecordingPaused: boolean
  pinnedRecords: HistoryRecord[]
  recentRecords: HistoryRecord[]
  shortcuts: ShortcutBindings
  onOpenSettings: () => void
  onTogglePause: () => void
  onTogglePin: (recordId: string) => void
  onDelete: (recordId: string) => void
  onCopy: (recordId: string) => void
  onPrimaryAction: (recordId: string) => void
  onPastePlainText: (recordId: string) => void
  onClearHistory: () => void
  onHideWindow: () => void
}

function matchesQuery(record: HistoryRecord, query: string) {
  const searchable = `${record.summary} ${record.detail} ${record.sourceApp}`.toLowerCase()
  return searchable.includes(query.toLowerCase())
}

export function QuickPanelView({
  isRecordingPaused,
  pinnedRecords,
  recentRecords,
  shortcuts,
  onOpenSettings,
  onTogglePause,
  onTogglePin,
  onDelete,
  onCopy,
  onPrimaryAction,
  onPastePlainText,
  onClearHistory,
  onHideWindow,
}: QuickPanelViewProps) {
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const [activeId, setActiveId] = useState<string | null>(null)
  const panelRef = useRef<HTMLElement | null>(null)
  const shouldScrollActiveIntoViewRef = useRef(false)

  const visiblePinned = pinnedRecords.filter((record) => matchesQuery(record, deferredQuery))
  const visibleRecent = recentRecords.filter((record) => matchesQuery(record, deferredQuery))
  const allCards = [...visiblePinned, ...visibleRecent]
  const resolvedActiveId =
    activeId === null ? null : allCards.some((record) => record.id === activeId) ? activeId : (allCards[0]?.id ?? null)

  useEffect(() => {
    panelRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!resolvedActiveId) return
    if (!shouldScrollActiveIntoViewRef.current) return
    shouldScrollActiveIntoViewRef.current = false
    const el = document.querySelector<HTMLElement>(`[data-record-id="${resolvedActiveId}"]`)
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest' })
    }
  }, [resolvedActiveId])

  function moveActive(direction: -1 | 1) {
    if (!allCards.length) return
    const i = allCards.findIndex((r) => r.id === resolvedActiveId)
    const next = i === -1 ? 0 : (i + direction + allCards.length) % allCards.length
    shouldScrollActiveIntoViewRef.current = true
    setActiveId(allCards[next].id)
  }

  const activeRecord = allCards.find((r) => r.id === resolvedActiveId) ?? null

  function handleKeyDown(event: React.KeyboardEvent<HTMLElement>) {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        moveActive(1)
        break
      case 'ArrowUp':
        event.preventDefault()
        moveActive(-1)
        break
      case 'Escape':
        event.preventDefault()
        if (query) { setQuery('') }
        else { onHideWindow() }
        break
      default:
        break
    }

    if (activeRecord && matchesShortcut(event, shortcuts.primaryAction)) {
      event.preventDefault()
      onPrimaryAction(activeRecord.id)
      return
    }

    if (activeRecord && matchesShortcut(event, shortcuts.deleteRecord)) {
      event.preventDefault()
      onDelete(activeRecord.id)
      return
    }

    if (activeRecord && matchesShortcut(event, shortcuts.togglePin)) {
      event.preventDefault()
      onTogglePin(activeRecord.id)
      return
    }

    if (activeRecord?.type === 'rich_text' && matchesShortcut(event, shortcuts.pastePlainText)) {
      event.preventDefault()
      onPastePlainText(activeRecord.id)
    }
  }

  return (
    <section className="panel-shell" onKeyDown={handleKeyDown} ref={panelRef} tabIndex={-1}>
      <header className="toolbar">
        {/* Row 1: Brand + REC + Settings */}
        <div className="toolbar-row-top">
          <div className="brand">
            <span className="brand-icon" aria-hidden="true">
              <CipherClipLogo />
            </span>
            <h1>CipherClip</h1>
          </div>

          <div className="toolbar-right">
            <button
              className={`rec-toggle ${isRecordingPaused ? 'is-paused' : ''}`}
              onClick={onTogglePause}
              title={isRecordingPaused ? 'Resume recording' : 'Pause recording'}
              type="button"
            >
              {isRecordingPaused ? 'PAUSED' : 'REC'}
            </button>

            <button
              aria-label="Settings"
              className="toolbar-icon-btn"
              onClick={onOpenSettings}
              title="Settings"
              type="button"
            >
              <Settings size={16} />
            </button>
          </div>
        </div>

        {/* Row 2: Search + Clear */}
        <div className="toolbar-row-bottom">
          <input
            aria-label="Search clipboard history"
            className="search-box"
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search clips…"
            value={query}
          />

          <button
            className="clear-all-btn"
            onClick={onClearHistory}
            title="Clear recent history"
            type="button"
          >
            Clear
          </button>
        </div>
      </header>

      <div className="panel-scroll">
        {allCards.length ? (
          <div className="card-list">
            {visiblePinned.length ? <p className="section-label">Pinned</p> : null}
            {visiblePinned.map((record) => (
              <HistoryCard
                isActive={resolvedActiveId === record.id}
                isPinned={record.pinned}
                key={record.id}
                onActivate={() => setActiveId(record.id)}
                onDelete={onDelete}
                onCopy={onCopy}
                onPinToggle={onTogglePin}
                onPlainTextPaste={onPastePlainText}
                onPrimaryAction={onPrimaryAction}
                record={record}
              />
            ))}
            {visibleRecent.length ? <p className="section-label">Recent</p> : null}
            {visibleRecent.map((record) => (
              <HistoryCard
                isActive={resolvedActiveId === record.id}
                isPinned={record.pinned}
                key={record.id}
                onActivate={() => setActiveId(record.id)}
                onDelete={onDelete}
                onCopy={onCopy}
                onPinToggle={onTogglePin}
                onPlainTextPaste={onPastePlainText}
                onPrimaryAction={onPrimaryAction}
                record={record}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state">No clips yet. Copy something to get started.</div>
        )}
      </div>
    </section>
  )
}

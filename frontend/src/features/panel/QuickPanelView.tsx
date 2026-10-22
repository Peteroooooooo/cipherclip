import { useDeferredValue, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { AnimatePresence, LayoutGroup, motion, useAnimate } from 'motion/react'
import { GearSix, MagnifyingGlass, X } from '@phosphor-icons/react'
import { matchesShortcut } from '../../app/shortcuts'
import type { HistoryRecord, HistoryRecordType, ShortcutBindings } from '../../app/types'
import { AppLogo } from '../../shared/ui/AppLogo'
import { EdgeGlow } from '../../shared/ui/EdgeGlow'
import { playLiquidRipple } from '../../shared/ui/liquidRipple'
import { useLensDrop, useLensGroup } from '../../shared/ui/liquid/useLiquidLens'
import { LiquidGlass } from '../../shared/ui/liquid/LiquidGlass'
import { SPRING_SMOOTH, SPRING_SNAPPY } from '../../shared/ui/motionTokens'
import { HistoryCard } from '../history/HistoryCard'

type FilterKey = 'all' | 'text' | 'image' | 'file'

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'text', label: 'Text' },
  { key: 'image', label: 'Images' },
  { key: 'file', label: 'Files' },
]

const FILTER_TYPES: Record<FilterKey, HistoryRecordType[] | null> = {
  all: null,
  text: ['text', 'rich_text'],
  image: ['image'],
  file: ['file'],
}

// Search bar geometry (px): the drop it starts as, the bar it spreads into, and the room it
// pushes the list down by. Matches .search-row / .search-bar in index.css.
const DROP = 30
const BAR_HEIGHT = 40
const BAR_INSET_X = 14
const BAR_INSET_Y = 4
const SEARCH_GAP = BAR_HEIGHT + BAR_INSET_Y + 6
// An empty search folds back once focus has really left it (not just moved to its clear button).
const BLUR_CLOSE_DELAY_MS = 120

interface QuickPanelViewProps {
  isAlwaysOnTop: boolean
  isRecordingPaused: boolean
  pinnedRecords: HistoryRecord[]
  recentRecords: HistoryRecord[]
  shortcuts: ShortcutBindings
  onOpenSettings: () => void
  onToggleAlwaysOnTop: () => void
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

function matchesFilter(record: HistoryRecord, filter: FilterKey) {
  const types = FILTER_TYPES[filter]
  return types === null || types.includes(record.type)
}

const motionOff = () =>
  document.documentElement.classList.contains('no-motion') ||
  Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)

/** The pushpin from the design demo: head at the top right, needle to the bottom left. */
function PinGlyph({ ref }: { ref: React.Ref<SVGSVGElement> }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="17"
      ref={ref}
      stroke="currentColor"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      width="17"
    >
      <path d="M14.6 3.6l5.8 5.8-2.4 1-3.9 3.9.3 4.4-1.6 1.6-3.6-3.6-4.7 4.7-1-1 4.7-4.7-3.6-3.6 1.6-1.6 4.4.3 3.9-3.9z" />
    </svg>
  )
}

// Pinning: the pin lifts off along its needle, drives into the glass and settles with a small
// bounce. `transform` composes after the CSS `rotate`, so these offsets run along the needle
// whichever way the pin is turned.
const PIN_PRESS: Keyframe[] = [
  { transform: 'none' },
  { transform: 'translate(2.6px, -3.4px) scale(1.16)', offset: 0.3 },
  { transform: 'translate(-1.2px, 1.6px) scale(0.86)', offset: 0.52 },
  { transform: 'translate(0.4px, -0.5px) scale(1.04)', offset: 0.74 },
  { transform: 'none' },
]

// When in PIN_PRESS the pin reaches the glass (offset 0.52 of 640 ms, a little early so the
// ripple starts with the impact).
const PIN_HIT_MS = 300

// …and as it goes in, the whole window gives a little, as if pressed onto the desktop.
const WINDOW_PULL: Keyframe[] = [
  { transform: 'none' },
  { transform: 'none', offset: 0.4 },
  { transform: 'scale(0.988)', offset: 0.55 },
  { transform: 'scale(1.003)', offset: 0.78 },
  { transform: 'none' },
]

/** Bumps a counter whenever `value` turns on, so a feature being enabled can be greeted once. */
function useTurnOnCounter(value: boolean) {
  const [count, setCount] = useState(0)
  const [previous, setPrevious] = useState(value)
  if (value !== previous) {
    setPrevious(value)
    if (value) {
      setCount(count + 1)
    }
  }
  return count
}

export function QuickPanelView({
  isAlwaysOnTop,
  isRecordingPaused,
  pinnedRecords,
  recentRecords,
  shortcuts,
  onOpenSettings,
  onToggleAlwaysOnTop,
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
  const [filter, setFilter] = useState<FilterKey>('all')
  const deferredQuery = useDeferredValue(query)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  // Stays true while the bar folds back into the magnifier, after searchOpen has gone false.
  const [searchShown, setSearchShown] = useState(false)
  const [searchFocused, setSearchFocused] = useState(false)
  const panelRef = useRef<HTMLElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const magnifierRef = useRef<HTMLButtonElement | null>(null)
  const searchRowRef = useRef<HTMLDivElement | null>(null)
  const blurTimerRef = useRef(0)
  const [barRef, animateBar] = useAnimate<HTMLDivElement>()
  const shouldScrollActiveIntoViewRef = useRef(false)
  const { groupRef: headerGroupRef, lensRef: headerLensRef } = useLensGroup<HTMLDivElement>()
  const { groupRef: filterGroupRef, dropRef: filterDropRef } = useLensDrop<HTMLDivElement>(filter)

  const pinPulse = useTurnOnCounter(isAlwaysOnTop)
  const recordPulse = useTurnOnCounter(!isRecordingPaused)
  const pinGlyphRef = useRef<SVGSVGElement | null>(null)

  useEffect(() => {
    if (!pinPulse || motionOff()) return
    const glyph = pinGlyphRef.current
    if (!glyph || typeof glyph.animate !== 'function') return
    const easing = 'cubic-bezier(0.3, 0.7, 0.4, 1)'
    const press = glyph.animate(PIN_PRESS, { duration: 640, easing })
    const frame = panelRef.current?.closest<HTMLElement>('.glass-window')
    const pull = frame?.animate(WINDOW_PULL, { duration: 640, easing })
    // The moment the pin goes in, a ripple runs out from it across the whole panel.
    let stopRipple = () => {}
    const timer = window.setTimeout(() => {
      const panel = panelRef.current
      if (!panel) return
      const pin = glyph.getBoundingClientRect()
      stopRipple = playLiquidRipple(panel, pin.left + pin.width / 2, pin.top + pin.height / 2)
    }, PIN_HIT_MS)
    return () => {
      window.clearTimeout(timer)
      press.cancel()
      pull?.cancel()
      stopRipple()
    }
  }, [pinPulse])

  const isVisible = (record: HistoryRecord) => matchesFilter(record, filter) && matchesQuery(record, deferredQuery)
  const visiblePinned = pinnedRecords.filter(isVisible)
  const visibleRecent = recentRecords.filter(isVisible)
  const allCards = [...visiblePinned, ...visibleRecent]
  const hasRecords = pinnedRecords.length + recentRecords.length > 0
  const resolvedActiveId =
    activeId === null ? null : allCards.some((record) => record.id === activeId) ? activeId : (allCards[0]?.id ?? null)

  useEffect(() => {
    panelRef.current?.focus()
  }, [])

  useEffect(() => () => window.clearTimeout(blurTimerRef.current), [])

  useEffect(() => {
    if (!resolvedActiveId) return
    if (!shouldScrollActiveIntoViewRef.current) return
    shouldScrollActiveIntoViewRef.current = false
    const el = document.querySelector<HTMLElement>(`[data-record-id="${resolvedActiveId}"]`)
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest' })
    }
  }, [resolvedActiveId])

  // The search bar drips out of the magnifier: it falls as a drop, then spreads sideways into a
  // bar. Closing runs the same path backwards and lifts it back into the magnifier.
  const animatedOpen = useRef(false)
  // Read inside the close animation's callback, which may finish after the search reopened.
  const searchOpenRef = useRef(searchOpen)
  useLayoutEffect(() => {
    searchOpenRef.current = searchOpen
    if (animatedOpen.current === searchOpen) {
      return
    }
    animatedOpen.current = searchOpen
    const bar = barRef.current
    const row = searchRowRef.current
    const magnifier = magnifierRef.current
    if (!bar || !row || !magnifier) {
      return
    }
    if (searchOpen) {
      inputRef.current?.focus({ preventScroll: true })
    }
    const rowBox = row.getBoundingClientRect()
    const magBox = magnifier.getBoundingClientRect()
    const fullWidth = rowBox.width - BAR_INSET_X * 2
    const dropX = magBox.left + magBox.width / 2 - DROP / 2 - (rowBox.left + BAR_INSET_X)
    const dropY = magBox.top + magBox.height / 2 - DROP / 2 - (rowBox.top + BAR_INSET_Y)
    const instant = motionOff()

    if (searchOpen) {
      void animateBar(
        bar,
        {
          x: [dropX, dropX, 0],
          y: [dropY, 0, 0],
          width: [DROP, DROP, fullWidth],
          height: [DROP, DROP + 4, BAR_HEIGHT],
          opacity: [0, 1, 1],
        },
        { duration: instant ? 0 : 0.62, times: [0, 0.38, 1], ease: ['easeIn', [0.34, 1.32, 0.64, 1]] },
      ).then(() => {
        // Back to the stylesheet's size, so the bar follows the window if it is resized.
        bar.style.width = ''
        bar.style.height = ''
      })
      return
    }

    void animateBar(
      bar,
      {
        x: [0, dropX, dropX],
        y: [0, 0, dropY],
        width: [bar.offsetWidth, DROP, DROP],
        height: [BAR_HEIGHT, DROP + 4, DROP],
        opacity: [1, 1, 0],
      },
      { duration: instant ? 0 : 0.5, times: [0, 0.55, 1], ease: ['easeInOut', 'easeIn'] },
    ).then(() => setSearchShown((shown) => (searchOpenRef.current ? shown : false)))
  }, [searchOpen, animateBar, barRef])

  function openSearch() {
    window.clearTimeout(blurTimerRef.current)
    if (searchOpen) {
      inputRef.current?.focus({ preventScroll: true })
      return
    }
    setSearchShown(true)
    setSearchOpen(true)
  }

  function closeSearch() {
    window.clearTimeout(blurTimerRef.current)
    if (!searchOpen) return
    setSearchOpen(false)
    setQuery('')
    if (document.activeElement === inputRef.current) {
      panelRef.current?.focus({ preventScroll: true })
    }
  }

  function toggleSearch() {
    if (!searchOpen) openSearch()
    else if (!query) closeSearch()
    else inputRef.current?.focus({ preventScroll: true })
  }

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
        if (searchOpen) {
          closeSearch()
        } else {
          onHideWindow()
        }
        return
      default:
        break
    }

    if (activeRecord && matchesShortcut(event, shortcuts.primaryAction)) {
      event.preventDefault()
      onPrimaryAction(activeRecord.id)
      return
    }

    // While typing in the search box, plain keys (Delete, letters...) edit the text; only
    // chords with Ctrl / Alt / Win still act on the highlighted record.
    const typing =
      event.target instanceof HTMLInputElement && !event.ctrlKey && !event.altKey && !event.metaKey

    if (activeRecord && !typing && matchesShortcut(event, shortcuts.deleteRecord)) {
      event.preventDefault()
      onDelete(activeRecord.id)
      return
    }

    if (activeRecord && !typing && matchesShortcut(event, shortcuts.togglePin)) {
      event.preventDefault()
      onTogglePin(activeRecord.id)
      return
    }

    if (activeRecord?.type === 'rich_text' && matchesShortcut(event, shortcuts.pastePlainText)) {
      event.preventDefault()
      onPastePlainText(activeRecord.id)
      return
    }

    // Just start typing anywhere on the panel: the search drips out with that first letter.
    const printable = event.key.length === 1 && event.key !== ' ' && !event.ctrlKey && !event.altKey && !event.metaKey
    if (printable && !(event.target instanceof HTMLInputElement)) {
      event.preventDefault()
      setQuery((current) => current + event.key)
      openSearch()
    }
  }

  const renderCard = (record: HistoryRecord) => (
    <HistoryCard
      isActive={resolvedActiveId === record.id}
      isPinned={record.pinned}
      key={record.id}
      onActivate={setActiveId}
      onDelete={onDelete}
      onCopy={onCopy}
      onPinToggle={onTogglePin}
      onPlainTextPaste={onPastePlainText}
      onPrimaryAction={onPrimaryAction}
      record={record}
    />
  )

  const recordingLabel = isRecordingPaused ? 'Resume recording' : 'Pause recording'

  return (
    <section className="panel-shell" onKeyDown={handleKeyDown} ref={panelRef} tabIndex={-1}>
      <h1 className="sr-only">ClipDeck</h1>

      {/* One row: pin · type filter · search / recording / settings / close. The gaps between
          them are where the window is dragged from. */}
      <header className="titlebar window-drag-region magnet-group">
        <LiquidGlass className={`pin-glass is-raised ${isAlwaysOnTop ? 'is-on' : ''}`} magnetic>
          <button
            aria-label="Always on top"
            aria-pressed={isAlwaysOnTop}
            className="pin-button"
            onClick={onToggleAlwaysOnTop}
            title={isAlwaysOnTop ? 'Disable always on top' : 'Enable always on top'}
            type="button"
          >
            <PinGlyph ref={pinGlyphRef} />
          </button>
        </LiquidGlass>

        <LiquidGlass className="filter-glass is-raised" magnetic>
          {/* The selected tab sits under a drop of clear glass that slides between tabs. */}
          <div aria-label="Filter by type" className="segmented" ref={filterGroupRef} role="tablist">
            {FILTERS.map((item) => (
              <button
                aria-selected={filter === item.key}
                className={`segment ${filter === item.key ? 'is-selected' : ''}`}
                data-lens=""
                key={item.key}
                onClick={() => setFilter(item.key)}
                role="tab"
                type="button"
              >
                <span className="segment-label">{item.label}</span>
              </button>
            ))}
            <LiquidGlass className="segment-drop" ref={filterDropRef} variant="lens" />
          </div>
        </LiquidGlass>

        <LiquidGlass className="header-glass is-raised" magnetic>
          {/* One lens for the four buttons: it follows the pointer from button to button. */}
          <div className="lens-group" ref={headerGroupRef}>
            <button
              aria-expanded={searchOpen}
              aria-label="Search"
              className="lens-button"
              data-lens=""
              onClick={toggleSearch}
              ref={magnifierRef}
              title="Search (or just start typing)"
              type="button"
            >
              <MagnifyingGlass size={16} weight="bold" />
            </button>

            <button
              aria-label={recordingLabel}
              className={`lens-button rec-button ${isRecordingPaused ? 'is-paused' : ''}`}
              data-lens=""
              onClick={onTogglePause}
              title={recordingLabel}
              type="button"
            >
              <span aria-hidden="true" className="rec-dot" />
              {/* Resuming sends two small rings out of the dot; the key replays them. */}
              {recordPulse && !isRecordingPaused ? <span aria-hidden="true" className="rec-ripple" key={recordPulse} /> : null}
            </button>

            <button
              aria-label="Settings"
              className="lens-button"
              data-lens=""
              onClick={onOpenSettings}
              title="Settings"
              type="button"
            >
              <GearSix size={17} />
            </button>

            <button
              aria-label="Hide window"
              className="lens-button"
              data-lens=""
              onClick={onHideWindow}
              title="Hide (Esc)"
              type="button"
            >
              <X size={15} weight="bold" />
            </button>
            <LiquidGlass className="button-lens" ref={headerLensRef} variant="lens" />
          </div>
        </LiquidGlass>
      </header>

      {/* The room the search bar takes; growing it pushes the list down on a spring. */}
      <motion.div
        animate={{ height: searchOpen ? SEARCH_GAP : 0 }}
        className="search-row"
        initial={false}
        ref={searchRowRef}
        transition={SPRING_SNAPPY}
      >
        <div
          aria-hidden={!searchOpen}
          className={`search-bar ${searchShown ? 'is-shown' : ''} ${searchOpen ? 'is-open' : ''}`}
          ref={barRef}
        >
          <label className="search-field">
            <LiquidGlass className="search-glass">
              <MagnifyingGlass className="search-icon" size={15} weight="bold" />
              <input
                aria-label="Search clipboard history"
                className="search-box"
                onBlur={() => {
                  setSearchFocused(false)
                  // Only an empty search folds back; with text in it the list stays filtered.
                  blurTimerRef.current = window.setTimeout(() => {
                    if (document.activeElement !== inputRef.current && !inputRef.current?.value) {
                      closeSearch()
                    }
                  }, BLUR_CLOSE_DELAY_MS)
                }}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => {
                  window.clearTimeout(blurTimerRef.current)
                  setSearchFocused(true)
                }}
                placeholder="Search clips"
                ref={inputRef}
                tabIndex={searchOpen ? 0 : -1}
                value={query}
              />
              {query ? (
                <button
                  aria-label="Clear search"
                  className="search-clear"
                  onClick={() => {
                    setQuery('')
                    inputRef.current?.focus({ preventScroll: true })
                  }}
                  onMouseDown={(event) => event.preventDefault()}
                  type="button"
                >
                  <X size={10} weight="bold" />
                </button>
              ) : null}
            </LiquidGlass>
          </label>
        </div>
      </motion.div>

      {/* Leaving the list puts the highlight away; the keyboard brings it back with the arrows. */}
      <motion.div
        className="panel-scroll"
        layoutScroll
        onPointerLeave={(event) => {
          if (event.pointerType === 'mouse') setActiveId(null)
        }}
      >
        {allCards.length ? (
          // Keyed by filter: switching tabs cross-fades the whole list instead of popping rows.
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="card-list"
            initial={{ opacity: 0, y: 6 }}
            key={filter}
            transition={SPRING_SMOOTH}
          >
            <LayoutGroup id="cards">
              {visiblePinned.length ? <p className="section-label">Pinned</p> : null}
              <AnimatePresence initial={false}>{visiblePinned.map(renderCard)}</AnimatePresence>
              {visibleRecent.length ? (
                <div className="section-head">
                  <p className="section-label">Recent</p>
                  <button className="section-action" onClick={onClearHistory} title="Clear recent history" type="button">
                    Clear
                  </button>
                </div>
              ) : null}
              <AnimatePresence initial={false}>{visibleRecent.map(renderCard)}</AnimatePresence>
            </LayoutGroup>
          </motion.div>
        ) : hasRecords ? (
          <motion.p animate={{ opacity: 1, y: 0 }} className="no-match" initial={{ opacity: 0, y: 6 }} transition={SPRING_SMOOTH}>
            没有匹配的记录
          </motion.p>
        ) : (
          <motion.div animate={{ opacity: 1, y: 0 }} className="empty-state" initial={{ opacity: 0, y: 6 }} transition={SPRING_SMOOTH}>
            <span className="empty-icon">
              <AppLogo size={48} />
            </span>
            <span>No clips yet. Copy something to get started.</span>
          </motion.div>
        )}
      </motion.div>

      <EdgeGlow active={searchOpen && searchFocused} />
    </section>
  )
}

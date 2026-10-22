import { memo, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { motion, PresenceContext } from 'motion/react'
import { Copy, File, Image, PushPin, TextAa, TextAlignLeft, TrashSimple } from '@phosphor-icons/react'
import type { HistoryRecord } from '../../app/types'
import { LiquidGlass } from '../../shared/ui/liquid/LiquidGlass'
import { useLensGroup } from '../../shared/ui/liquid/useLiquidLens'
import { SPRING_SMOOTH, SPRING_SNAPPY } from '../../shared/ui/motionTokens'
import { timeAgo } from '../../shared/utils/timeAgo'
import { capsuleRef, trackCapsule } from './capsuleHole'

// Under half of SPRING_SNAPPY's visual duration (0.3 s): the spring covers most of the way early,
// so the buttons start fading in as the capsule comes into place, not after it has settled.
const CAPSULE_ARRIVAL_MS = 140
// .panel-card-highlight's fade-out, plus a frame.
const HIGHLIGHT_FADE_MS = 400

/**
 * Puts the row's meteor lap on the page clock (start time 0), the same for every row, so the
 * meteor carries on round the next row from where it was rather than starting a new lap.
 */
function syncMeteor(card: HTMLElement) {
  if (typeof card.getAnimations !== 'function' || typeof CSSAnimation === 'undefined') return
  for (const animation of card.getAnimations({ subtree: true })) {
    if (animation instanceof CSSAnimation && animation.animationName === 'row-meteor') {
      animation.startTime = 0
    }
  }
}

const TYPE_ICONS = {
  text: TextAlignLeft,
  rich_text: TextAa,
  image: Image,
  file: File,
} as const

function SourceAvatar({ record }: { record: HistoryRecord }) {
  const [iconError, setIconError] = useState(false)
  const glyph = record.sourceGlyph || record.sourceApp.slice(0, 2).toUpperCase()
  const TypeIcon = TYPE_ICONS[record.type] ?? TextAlignLeft
  const badge = (
    <span className="record-avatar-badge">
      <TypeIcon size={9} weight="bold" />
    </span>
  )

  // The app's own icon, as the backend read it from its exe; the lettered bead is the fallback.
  if (record.sourceIcon && !iconError) {
    return (
      <span className="record-avatar is-app" aria-hidden="true" title={record.sourceApp}>
        <img alt="" className="record-app-icon" draggable={false} onError={() => setIconError(true)} src={record.sourceIcon} />
        {badge}
      </span>
    )
  }

  return (
    <span className={`record-avatar is-${record.type}`} aria-hidden="true" title={record.sourceApp}>
      <span className="record-avatar-glyph">{glyph}</span>
      {badge}
    </span>
  )
}

function PreviewAvatar({ record }: { record: HistoryRecord }) {
  const [imgError, setImgError] = useState(false)

  if (record.type === 'image' && record.imagePath && !imgError) {
    return (
      <img
        alt={record.summary}
        className="record-preview-image"
        height={38}
        src={record.imagePath}
        width={38}
        onError={() => setImgError(true)}
      />
    )
  }

  return <SourceAvatar record={record} />
}

// The highlight's soft light follows the pointer; written straight to CSS vars so hovering never
// re-renders. On the highlight itself, not the row: a var on the row restyles everything in it.
function trackSpotlight(event: React.MouseEvent<HTMLElement>) {
  const card = event.currentTarget
  const highlight = card.querySelector<HTMLElement>('.panel-card-highlight')
  if (!highlight) return
  const rect = card.getBoundingClientRect()
  highlight.style.setProperty('--mx', `${Math.round(event.clientX - rect.left)}px`)
  highlight.style.setProperty('--my', `${Math.round(event.clientY - rect.top)}px`)
}

interface HistoryCardProps {
  record: HistoryRecord
  isActive: boolean
  isPinned: boolean
  onActivate: (recordId: string) => void
  onDelete: (recordId: string) => void
  onPinToggle: (recordId: string) => void
  onCopy: (recordId: string) => void
  onPlainTextPaste?: (recordId: string) => void
  onPrimaryAction?: (recordId: string) => void
}

// Memoised: moving the pointer down the list re-renders only the row it left and the one it
// entered, not every row.
export const HistoryCard = memo(function HistoryCard({
  record,
  isActive,
  isPinned,
  onActivate,
  onDelete,
  onPinToggle,
  onCopy,
  onPlainTextPaste,
  onPrimaryAction,
}: HistoryCardProps) {
  const { groupRef: actionsRef, lensRef } = useLensGroup<HTMLDivElement>()
  const cardRef = useRef<HTMLElement | null>(null)

  // The meteor on the edge runs while the row is lit: active, and for the highlight's fade after.
  // Written to the element before paint, so it starts in the same frame as the highlight.
  useLayoutEffect(() => {
    const card = cardRef.current
    if (!card) return
    if (isActive) {
      card.dataset.lit = ''
      syncMeteor(card)
      return
    }
    if (!('lit' in card.dataset)) return
    const timer = window.setTimeout(() => delete card.dataset.lit, HIGHLIGHT_FADE_MS)
    return () => window.clearTimeout(timer)
  }, [isActive])
  // While the capsule is still gliding over from another row, its buttons wait: the glass arrives
  // first, then the buttons appear on it.
  const [capsuleGliding, setCapsuleGliding] = useState(false)
  const glideTimer = useRef(0)
  useEffect(() => () => window.clearTimeout(glideTimer.current), [])
  // The spring only reports completion after its last tiny wobble; the capsule looks arrived
  // well before that, so the buttons come in at its visual arrival.
  const startGlide = () => {
    setCapsuleGliding(true)
    window.clearTimeout(glideTimer.current)
    glideTimer.current = window.setTimeout(() => setCapsuleGliding(false), CAPSULE_ARRIVAL_MS)
  }

  return (
    <motion.article
      animate={{ opacity: 1, y: 0, scale: 1 }}
      className={`panel-card ${isPinned ? 'is-pinned' : ''}`}
      data-active={isActive}
      data-record-id={record.id}
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      layout="position"
      onMouseEnter={() => onActivate(record.id)}
      onMouseMove={trackSpotlight}
      ref={cardRef}
      transition={SPRING_SMOOTH}
      whileTap={{ scale: 0.985 }}
    >
      {/* Fades in under the active row and out of the previous one; a thin edge of drifting colour. */}
      <span aria-hidden="true" className="panel-card-highlight">
        <span className="panel-card-edge" />
      </span>

      <button
        aria-label={`${record.summary} from ${record.sourceApp}`}
        className="panel-card-main"
        onClick={() => {
          onActivate(record.id)
          onPrimaryAction?.(record.id)
        }}
        type="button"
      >
        <PreviewAvatar record={record} />

        <span className="record-copy">
          <span className="record-summary">{record.summary}</span>
          <span className="record-meta">
            <span>{record.sourceApp}</span>
            <span className="meta-dot">·</span>
            <span className="record-time">{timeAgo(record.updatedAt)}</span>
          </span>
        </span>
      </button>

      <div className="card-actions" data-gliding={isActive && capsuleGliding} ref={actionsRef}>
        {/* One capsule of liquid glass for the whole list: the active row hosts it, so it glides
            from row to row. The old one is unmounted at once and the new one glides in from where
            it was, so there is only ever one: kept around (AnimatePresence), Motion stacks the two
            for the whole glide (brighter while moving), or, without its crossfade, leaves old ones
            visible. No presence scope of its own either: a deleted row must not wait for it. */}
        <PresenceContext.Provider value={null}>
          {isActive ? (
            <motion.div
              aria-hidden="true"
              className="card-actions-glass"
              layoutId="card-actions-glass"
              onLayoutAnimationComplete={() => {
                setCapsuleGliding(false)
                trackCapsule(0)
              }}
              onLayoutAnimationStart={() => {
                startGlide()
                trackCapsule()
              }}
              ref={capsuleRef}
              transition={SPRING_SNAPPY}
            >
              {/* The same glass as the title bar controls. */}
              <LiquidGlass className="card-actions-liquid is-raised" />
            </motion.div>
          ) : null}
        </PresenceContext.Provider>
        <button aria-label="Copy" className="action-button" data-lens="" onClick={() => onCopy(record.id)} title="Copy" type="button">
          <Copy size={15} />
        </button>
        {record.type === 'rich_text' && onPlainTextPaste && (
          <button
            aria-label="Paste as plain text"
            className="action-button"
            data-lens=""
            onClick={() => onPlainTextPaste(record.id)}
            title="纯文本粘贴"
            type="button"
          >
            <TextAa size={15} />
          </button>
        )}
        <button
          aria-label={record.pinned ? 'Unpin' : 'Pin'}
          className={`action-button is-pin ${record.pinned ? 'is-pinned' : ''}`}
          data-lens=""
          onClick={() => onPinToggle(record.id)}
          title={record.pinned ? 'Unpin' : 'Pin'}
          type="button"
        >
          <PushPin size={15} weight={record.pinned ? 'fill' : 'regular'} />
        </button>
        <button
          aria-label="Delete"
          className="action-button is-danger"
          data-lens=""
          onClick={() => onDelete(record.id)}
          title="Delete"
          type="button"
        >
          <TrashSimple size={15} />
        </button>
        {/* The lens that follows the pointer across the buttons. */}
        <LiquidGlass className="button-lens" ref={lensRef} variant="lens" />
      </div>
    </motion.article>
  )
})

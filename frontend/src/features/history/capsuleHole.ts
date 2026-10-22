import { cancelFrame, frame } from 'motion/react'

// The row highlight leaves a hole exactly where the action capsule is, wherever it is: resting
// in a row, or halfway between two rows while it glides. So the capsule only ever has the window
// behind it and always looks the same, and a row the capsule has left (or not reached yet) has
// no empty hole in its highlight.
//
// The hole is placed in Motion's postRender step, after Motion has written that frame's glide
// transform, so it moves in the same frame as the capsule instead of one frame behind it.

const OFF = '-9999px'
const TRACK_MS = 700

let capsule: HTMLElement | null = null
let trackUntil = 0
let tracking = false
const written = new WeakMap<HTMLElement, string>()

function write(highlight: HTMLElement, key: string, apply: () => void) {
  if (written.get(highlight) === key) return
  written.set(highlight, key)
  apply()
}

function placeHoles() {
  // The glass itself: it also leans and stretches towards the pointer, on top of the glide.
  const glass = capsule?.querySelector<HTMLElement>('.liquid') ?? capsule
  const box = glass?.isConnected ? glass.getBoundingClientRect() : null
  // The capsule's own width (3 or 4 buttons), before any glide transform: picks the hole's shape.
  const wide = capsule && capsule.offsetWidth > 111 ? '4' : '3'

  // All measuring first, then all writing: a read after a write would make the browser redo
  // style and layout once per row, every frame.
  const updates: Array<[HTMLElement, string, () => void]> = []
  for (const highlight of document.querySelectorAll<HTMLElement>('.panel-card-highlight')) {
    const rect = highlight.getBoundingClientRect()
    if (!box || !highlight.offsetWidth || box.bottom <= rect.top || box.top >= rect.bottom) {
      updates.push([highlight, 'off', () => highlight.style.setProperty('--hole-y', OFF)])
      continue
    }
    // The row's own scale (a press squeezes it slightly): the mask lives in its untransformed space.
    const k = rect.width / highlight.offsetWidth || 1
    const x = ((box.left - rect.left) / k).toFixed(2)
    const y = ((box.top - rect.top) / k).toFixed(2)
    const w = (box.width / k).toFixed(2)
    const h = (box.height / k).toFixed(2)
    updates.push([
      highlight,
      `${wide} ${x} ${y} ${w} ${h}`,
      () => {
        highlight.dataset.hole = wide
        highlight.style.setProperty('--hole-x', `${x}px`)
        highlight.style.setProperty('--hole-y', `${y}px`)
        highlight.style.setProperty('--hole-w', `${w}px`)
        highlight.style.setProperty('--hole-h', `${h}px`)
      },
    ])
  }
  for (const [highlight, key, apply] of updates) write(highlight, key, apply)
}

function tick() {
  placeHoles()
  if (performance.now() > trackUntil) {
    cancelFrame(tick)
    tracking = false
  }
}

/** Keeps the holes on the capsule for the next `ms` (it is moving, or about to). */
export function trackCapsule(ms = TRACK_MS) {
  trackUntil = Math.max(trackUntil, performance.now() + ms)
  if (!tracking) {
    tracking = true
    frame.postRender(tick, true)
  }
}

// The hover magnet's spring (.liquid.is-magnetic) settles about 520ms after each move.
const followPointer = () => trackCapsule(650)

/** Ref callback for the capsule element. */
export function capsuleRef(element: HTMLElement | null) {
  if (element) {
    capsule = element
    trackCapsule()
    window.addEventListener('pointermove', followPointer, { passive: true })
    return () => {
      if (capsule === element) {
        capsule = null
        window.removeEventListener('pointermove', followPointer)
        trackCapsule(0)
      }
    }
  }
  return undefined
}

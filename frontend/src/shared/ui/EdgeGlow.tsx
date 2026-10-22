import { useLayoutEffect, useRef } from 'react'

// .edge-glow's opacity transition when it goes out.
const FADE_MS = 800

interface EdgeGlowProps {
  /** Glows while something is in progress (the search box is in use). */
  active: boolean
}

/**
 * Soft, luminous light seeping in from the window's edges, after the ColorOS / Apple Intelligence
 * listening glow: a near-white core, a colour band and two softer rings of the same palette,
 * drifting round together (see .edge-glow in index.css). Deliberately no mix-blend-mode: a blended
 * layer in the window would cut the liquid glass off from what is behind it.
 */
export function EdgeGlow({ active }: EdgeGlowProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const wasActive = useRef(active)

  // Keeps moving while it fades out, then stops: is-fading. Before paint, so its animations carry
  // straight on from is-active instead of being dropped for a frame and restarted.
  useLayoutEffect(() => {
    const element = ref.current
    const fadingOut = wasActive.current && !active
    wasActive.current = active
    if (!element || !fadingOut) return
    element.classList.add('is-fading')
    const timer = window.setTimeout(() => element.classList.remove('is-fading'), FADE_MS)
    return () => {
      window.clearTimeout(timer)
      element.classList.remove('is-fading')
    }
  }, [active])

  return (
    <div aria-hidden="true" className={`edge-glow ${active ? 'is-active' : ''}`} ref={ref}>
      <i />
      <i />
      <i />
      <i />
    </div>
  )
}

// While the panel is hidden in the tray, WebView2 still treats the page as visible and would keep
// drawing every animation frame for nobody: the backend sends "clipdeck:sleep" when it hides the
// window and "clipdeck:reveal" when it shows it, and html.is-asleep pauses all animations in
// between (index.css). Installed before React, so a sleep sent while the app is still starting up
// is not missed.
//
// The same events drive the summon motion. Asleep, the panel also sits "concealed" (transparent,
// slightly small and blurred, html.is-concealed), so the frame WebView2 shows first when the
// window appears is already the start of the reveal, never a flash of the old panel. The backend
// sends "clipdeck:reveal" just before showing the window and "clipdeck:conceal" just before a
// short animated hide. The native glass under the page runs the same motion on the compositor.
//
// Each event carries a running number; a late "sleep" can never put a panel that has been shown
// again to sleep.

import { SPRING_SMOOTH_EASING } from './motionTokens'

// Must match CONCEAL_SCALE / REVEAL_MS / CONCEAL_MS in backend/app/backdrop.py.
export const CONCEAL_SCALE = 0.97
export const REVEAL_MS = 260
export const CONCEAL_MS = 130

const CONCEALED: Keyframe = { opacity: 0, transform: `scale(${CONCEAL_SCALE})`, filter: 'blur(6px)' }
const SHOWN: Keyframe = { opacity: 1, transform: 'none', filter: 'blur(0px)' }
const STAGGERED_CARDS = 8

function motionAllowed() {
  return !(
    document.documentElement.classList.contains('no-motion') ||
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  )
}

function panelElement() {
  return document.querySelector<HTMLElement>('.glass-window')
}

export function installPanelSleep() {
  const root = document.documentElement
  let latest = -1
  let running: Animation[] = []

  const isCurrent = (event: Event) => {
    const seq = Number((event as CustomEvent<{ seq?: number } | null>).detail?.seq ?? Number.NaN)
    if (Number.isNaN(seq)) return true
    if (seq < latest) return false
    latest = seq
    return true
  }

  const stopRunning = () => {
    running.forEach((animation) => animation.cancel())
    running = []
  }

  const handleSleep = (event: Event) => {
    if (!isCurrent(event)) return
    stopRunning()
    root.classList.add('is-asleep', 'is-concealed')
  }

  const handleReveal = (event: Event) => {
    if (!isCurrent(event)) return
    const panel = panelElement()
    // Start from wherever the panel is now (mid-conceal when summoned again quickly).
    const from: Keyframe = panel ? currentLook(panel) : CONCEALED
    const wasConcealed = root.classList.contains('is-concealed') || running.length > 0
    stopRunning()
    root.classList.remove('is-asleep', 'is-concealed')
    if (!panel || !wasConcealed || !motionAllowed() || typeof panel.animate !== 'function') return

    running.push(panel.animate([from, SHOWN], { duration: REVEAL_MS, easing: SPRING_SMOOTH_EASING }))
    if (from.opacity === 0) {
      panel.querySelectorAll<HTMLElement>('.panel-card').forEach((card, index) => {
        if (index >= STAGGERED_CARDS) return
        running.push(
          card.animate([{ opacity: 0, translate: '0 8px' }, { opacity: 1, translate: '0 0' }], {
            duration: 300,
            delay: 30 + index * 22,
            easing: SPRING_SMOOTH_EASING,
            fill: 'backwards',
          }),
        )
      })
    }
    const own = running
    void Promise.allSettled(own.map((animation) => animation.finished)).then(() => {
      if (running === own) running = []
    })
  }

  const handleConceal = (event: Event) => {
    if (!isCurrent(event)) return
    const panel = panelElement()
    const from: Keyframe = panel ? currentLook(panel) : SHOWN
    stopRunning()
    if (!panel || !motionAllowed() || typeof panel.animate !== 'function') {
      root.classList.add('is-concealed')
      return
    }
    const animation = panel.animate([from, CONCEALED], {
      duration: CONCEAL_MS,
      easing: 'cubic-bezier(0.4, 0, 1, 1)',
      fill: 'forwards',
    })
    running = [animation]
    void animation.finished.then(
      () => {
        if (running[0] !== animation) return
        root.classList.add('is-concealed')
        animation.cancel()
        running = []
      },
      () => undefined,
    )
  }

  window.addEventListener('clipdeck:sleep', handleSleep)
  window.addEventListener('clipdeck:reveal', handleReveal)
  window.addEventListener('clipdeck:conceal', handleConceal)
  return () => {
    stopRunning()
    window.removeEventListener('clipdeck:sleep', handleSleep)
    window.removeEventListener('clipdeck:reveal', handleReveal)
    window.removeEventListener('clipdeck:conceal', handleConceal)
  }
}

/** The panel's look right now, including any running animation. */
function currentLook(panel: HTMLElement): Keyframe {
  if (document.documentElement.classList.contains('is-concealed')) return CONCEALED
  const style = getComputedStyle(panel)
  const opacity = Number.parseFloat(style.opacity)
  return {
    opacity: Number.isNaN(opacity) ? 1 : opacity,
    transform: style.transform && style.transform !== 'none' ? style.transform : 'none',
    filter: style.filter && style.filter !== 'none' ? style.filter : 'blur(0px)',
  }
}

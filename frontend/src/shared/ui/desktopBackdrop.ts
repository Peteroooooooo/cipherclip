/**
 * Desktop glass backdrop.
 *
 * The native window is fully transparent, so the backend sends a pre-blurred snapshot of the
 * monitor behind it (`cipherclip:backdrop`) and the window position on every move
 * (`cipherclip:moved`). Both arrive in physical pixels; this module turns them into CSS
 * variables that `.glass-backdrop` uses to line the snapshot up with the real desktop.
 */

interface BackdropDetail {
  url: string
  left: number
  top: number
  width: number
  height: number
  windowLeft: number
  windowTop: number
}

type MovedDetail = Pick<BackdropDetail, 'windowLeft' | 'windowTop'>

let current: BackdropDetail | null = null

function applyPosition(root: HTMLElement) {
  if (!current) {
    return
  }
  const dpr = window.devicePixelRatio || 1
  const x = (current.left - current.windowLeft) / dpr
  const y = (current.top - current.windowTop) / dpr
  root.style.setProperty('--backdrop-x', `calc(${x}px - var(--shell-pad))`)
  root.style.setProperty('--backdrop-y', `calc(${y}px - var(--shell-pad))`)
  root.style.setProperty('--backdrop-w', `${current.width / dpr}px`)
  root.style.setProperty('--backdrop-h', `${current.height / dpr}px`)
}

function fadeIn(element: HTMLElement | null) {
  if (!element || typeof element.animate !== 'function') {
    return
  }
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    return
  }
  element.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 280, easing: 'cubic-bezier(0.4, 0, 0.2, 1)' })
}

export function installDesktopBackdrop(root: HTMLElement = document.documentElement) {
  const handleBackdrop = (event: Event) => {
    const detail = (event as CustomEvent<BackdropDetail>).detail
    if (!detail?.url) {
      return
    }
    // Keep the previous snapshot underneath and fade the new one in, so the glass never
    // flashes back to the plain fallback colour.
    const previous = root.style.getPropertyValue('--backdrop-image')
    root.style.setProperty('--backdrop-prev', previous || 'none')
    current = detail
    root.style.setProperty('--backdrop-image', `url("${detail.url}")`)
    applyPosition(root)
    root.classList.add('has-backdrop')
    fadeIn(document.querySelector<HTMLElement>('.glass-backdrop'))
  }

  const handleMoved = (event: Event) => {
    const detail = (event as CustomEvent<MovedDetail>).detail
    if (!current || !detail) {
      return
    }
    current = { ...current, ...detail }
    applyPosition(root)
  }

  // "live": the Windows compositor blurs the desktop under the page in real time, so the page
  // only adds its tint. "snapshot": the page paints the frosted snapshot itself.
  const handleGlass = (event: Event) => {
    const detail = (event as CustomEvent<{ mode: string }>).detail
    root.classList.toggle('glass-live', detail?.mode === 'live')
  }

  window.addEventListener('cipherclip:backdrop', handleBackdrop)
  window.addEventListener('cipherclip:moved', handleMoved)
  window.addEventListener('cipherclip:glass', handleGlass)
  return () => {
    window.removeEventListener('cipherclip:backdrop', handleBackdrop)
    window.removeEventListener('cipherclip:moved', handleMoved)
    window.removeEventListener('cipherclip:glass', handleGlass)
  }
}

// While the panel is hidden in the tray, WebView2 still treats the page as visible and would keep
// drawing every animation frame for nobody: the backend sends "clipdeck:sleep" when it hides the
// window and "clipdeck:reveal" when it shows it, and html.is-asleep pauses all animations in
// between (index.css). Installed before React, so a sleep sent while the app is still starting up
// is not missed.
//
// Each event carries a running number; a late "sleep" can never put a panel that has been shown
// again to sleep.

export function installPanelSleep() {
  const root = document.documentElement
  let latest = -1
  const isCurrent = (event: Event) => {
    const seq = Number((event as CustomEvent<{ seq?: number } | null>).detail?.seq ?? Number.NaN)
    if (Number.isNaN(seq)) return true
    if (seq < latest) return false
    latest = seq
    return true
  }
  const handleSleep = (event: Event) => {
    if (isCurrent(event)) root.classList.add('is-asleep')
  }
  const handleReveal = (event: Event) => {
    if (isCurrent(event)) root.classList.remove('is-asleep')
  }
  window.addEventListener('clipdeck:sleep', handleSleep)
  window.addEventListener('clipdeck:reveal', handleReveal)
  return () => {
    window.removeEventListener('clipdeck:sleep', handleSleep)
    window.removeEventListener('clipdeck:reveal', handleReveal)
  }
}

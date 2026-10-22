import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { applyAppearance, DEFAULT_APPEARANCE } from './app/appearance'
import { installDesktopBackdrop } from './shared/ui/desktopBackdrop'
import { installPanelSleep } from './shared/ui/panelSleep'
import { installWindowDrag } from './shared/ui/windowDrag'

// Resolve the theme before the first paint; App re-applies the saved appearance once it loads.
applyAppearance(DEFAULT_APPEARANCE)

// Inside the desktop host the page background must stay transparent so the native
// acrylic backdrop shows through; in a plain browser we paint a preview wallpaper instead.
function markDesktopHost() {
  document.documentElement.classList.add('is-desktop')
}

if ((window as Window & { pywebview?: unknown }).pywebview) {
  markDesktopHost()
} else {
  window.addEventListener('pywebviewready', markDesktopHost, { once: true })
}

installDesktopBackdrop()
installWindowDrag()
installPanelSleep()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

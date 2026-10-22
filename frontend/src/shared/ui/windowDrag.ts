import { desktopApi } from '../../app/pywebview'

const INTERACTIVE = 'button, input, textarea, select, a, label, [role="tab"]'

/**
 * Window dragging from `.window-drag-region` elements.
 *
 * The press is handed to the backend once; it then follows the pointer natively, once per
 * display frame and on a spring, until the button is released. (pywebview's own drag region
 * sends every mouse move through the bridge, which stutters.) The grab point goes in physical
 * pixels, the unit the native side moves the window in.
 */
export function installWindowDrag(target: Document = document) {
  const handleMouseDown = (event: MouseEvent) => {
    if (event.button !== 0 || !(event.target instanceof Element) || !event.target.closest('.window-drag-region')) {
      return
    }
    // A drag region may hold controls (the title bar is all buttons); pressing those is a click.
    if (event.target.closest(INTERACTIVE)) {
      return
    }
    // Keeps focus where it is and stops a text selection from starting under the drag.
    event.preventDefault()
    const scale = window.devicePixelRatio || 1
    void desktopApi.beginWindowDrag(Math.round(event.clientX * scale), Math.round(event.clientY * scale))
  }

  target.addEventListener('mousedown', handleMouseDown)
  return () => target.removeEventListener('mousedown', handleMouseDown)
}

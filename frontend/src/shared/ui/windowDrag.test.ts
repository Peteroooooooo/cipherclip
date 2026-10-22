import { afterEach, describe, expect, test, vi } from 'vitest'
import { desktopApi } from '../../app/pywebview'
import { installWindowDrag } from './windowDrag'

describe('window drag', () => {
  let uninstall: (() => void) | null = null

  afterEach(() => {
    uninstall?.()
    uninstall = null
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  test('hands a press on the drag region to the backend in physical pixels', () => {
    const begin = vi.spyOn(desktopApi, 'beginWindowDrag').mockResolvedValue(undefined)
    vi.spyOn(window, 'devicePixelRatio', 'get').mockReturnValue(1.5)
    document.body.innerHTML = '<div class="window-drag-region"><h1>ClipDeck</h1></div><button>Other</button>'
    uninstall = installWindowDrag()

    const title = document.querySelector('h1')!
    const press = new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0, clientX: 40, clientY: 21 })
    title.dispatchEvent(press)

    expect(begin).toHaveBeenCalledWith(60, 32)
    expect(press.defaultPrevented).toBe(true)
  })

  test('ignores other buttons and presses outside the drag region', () => {
    const begin = vi.spyOn(desktopApi, 'beginWindowDrag').mockResolvedValue(undefined)
    document.body.innerHTML = '<div class="window-drag-region"></div><button>Other</button>'
    uninstall = installWindowDrag()

    document.querySelector('.window-drag-region')!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 2 }))
    document.querySelector('button')!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }))

    expect(begin).not.toHaveBeenCalled()
  })

  test('lets controls inside the drag region be clicked', () => {
    const begin = vi.spyOn(desktopApi, 'beginWindowDrag').mockResolvedValue(undefined)
    document.body.innerHTML = '<header class="window-drag-region"><button><svg></svg></button><span class="gap"></span></header>'
    uninstall = installWindowDrag()

    const press = new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0 })
    document.querySelector('svg')!.dispatchEvent(press)
    expect(begin).not.toHaveBeenCalled()
    expect(press.defaultPrevented).toBe(false)

    document.querySelector('.gap')!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0 }))
    expect(begin).toHaveBeenCalledTimes(1)
  })
})

import { render } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { DEFAULT_APPEARANCE } from '../../../app/appearance'
import { LiquidGlass } from './LiquidGlass'
import { LiquidGlassContext } from './liquidContext'

function renderToolbar() {
  return render(
    <LiquidGlassContext.Provider value={{ ...DEFAULT_APPEARANCE, translucentBackdrop: true }}>
      <div className="magnet-group">
        <LiquidGlass className="first" magnetic />
        <LiquidGlass className="second" magnetic />
        <LiquidGlass className="plain" />
      </div>
    </LiquidGlassContext.Provider>,
  )
}

// jsdom lays nothing out: give the capsule a box so the pointer has a place on it.
function placeAt(element: HTMLElement, width: number, height: number) {
  element.getBoundingClientRect = () => ({ x: 0, y: 0, left: 0, top: 0, width, height, right: width, bottom: height, toJSON() {} })
}

const pointer = (type: string, x: number, y: number) => new MouseEvent(type, { clientX: x, clientY: y })

describe('hover magnet', () => {
  test('a hovered capsule swells and follows the pointer, and its neighbours step back', () => {
    const { container } = renderToolbar()
    const group = container.querySelector<HTMLElement>('.magnet-group')!
    const first = container.querySelector<HTMLElement>('.first')!
    placeAt(first, 100, 40)

    first.dispatchEvent(pointer('pointerenter', 100, 20))
    expect(first.classList.contains('is-hovered')).toBe(true)
    expect(group.classList.contains('is-magnet-on')).toBe(true)
    // At the right edge: pulled 4px right, swollen by the wide-capsule base (4.5%) plus stretch.
    expect(first.style.getPropertyValue('--lg-tx')).toBe('4.00px')
    expect(first.style.getPropertyValue('--lg-sx')).toBe('1.0570')
    expect(first.style.getPropertyValue('--lg-spot-x')).toBe('100px')
    expect(container.querySelector('.second .liquid-spot')).not.toBeNull()
    expect(container.querySelector('.plain .liquid-spot')).toBeNull()

    first.dispatchEvent(pointer('pointerdown', 50, 20))
    expect(first.style.getPropertyValue('--lg-sx')).toBe(String((1 - 0.045 * 0.6).toFixed(4)))

    first.dispatchEvent(pointer('pointerleave', 200, 20))
    expect(first.classList.contains('is-hovered')).toBe(false)
    expect(first.style.getPropertyValue('--lg-tx')).toBe('')
    expect(group.classList.contains('is-magnet-on')).toBe(false)
  })

  test('round buttons swell more than wide capsules', () => {
    const { container } = renderToolbar()
    const first = container.querySelector<HTMLElement>('.first')!
    placeAt(first, 38, 38)
    first.dispatchEvent(pointer('pointerenter', 19, 19))
    expect(first.style.getPropertyValue('--lg-sx')).toBe('1.1000')
  })

  test('no magnet with animations off', () => {
    const { container } = render(
      <LiquidGlassContext.Provider value={{ ...DEFAULT_APPEARANCE, animations: false, translucentBackdrop: true }}>
        <LiquidGlass className="first" magnetic />
      </LiquidGlassContext.Provider>,
    )
    const first = container.querySelector<HTMLElement>('.first')!
    first.dispatchEvent(pointer('pointerenter', 10, 10))
    expect(first.classList.contains('is-hovered')).toBe(false)
    expect(first.querySelector('.liquid-spot')).toBeNull()
  })
})

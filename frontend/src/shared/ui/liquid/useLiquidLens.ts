// The moving liquid lenses from docs/liquid-glass-demo.html, on the same spring physics:
//
// - useLensGroup: one lens shared by a row of buttons. It slides to the button under the pointer,
//   stretches like jelly while it travels, squishes when a button is pressed, and fades away when
//   the pointer leaves the row.
// - useLensDrop: the selection drop of a segmented control. It sits on the selected tab, leans a
//   little towards a hovered one, as if tempted across, and travels the same way when a tab is
//   picked.
//
// Everything is written straight to the lens element per frame; React never re-renders for it.
// The frame loop only runs while something is still moving.

import { useEffect, useRef } from 'react'

// Movement spring (stiffness, and the 0-1 jelly amount that lowers its damping).
const STIFFNESS = 360
const ELASTIC = 0.6
const DAMPING = 2 * Math.sqrt(STIFFNESS) * (1 - 0.62 * ELASTIC)
// Press: a quick squish that wobbles back, stiffer than the movement spring.
const PRESS_STIFFNESS = 900
const PRESS_DAMPING = 2 * Math.sqrt(PRESS_STIFFNESS) * (0.55 - 0.35 * ELASTIC)
const FADE_DAMPING = 2 * Math.sqrt(STIFFNESS)
const SUBSTEP = 0.004

interface Spring {
  x: number
  v: number
  t: number
}

const spring = (x = 0): Spring => ({ x, v: 0, t: x })
const clamp01 = (x: number) => Math.max(0, Math.min(1, x))
const settled = (s: Spring) => Math.abs(s.x - s.t) < 0.005 && Math.abs(s.v) < 0.005

function motionOff() {
  return (
    document.documentElement.classList.contains('no-motion') ||
    Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
  )
}

function advance(s: Spring, dt: number, k: number, c: number) {
  const a = -k * (s.x - s.t) - c * s.v
  s.v += a * dt
  s.x += s.v * dt
}

function snap(s: Spring) {
  s.x = s.t
  s.v = 0
}

/** A frame loop that runs `tick(dt)` until it returns false, and can be restarted with `kick`. */
function createLoop(tick: (dt: number) => boolean) {
  let frame = 0
  let last = 0
  const run = (now: number) => {
    const dt = last ? Math.min(0.034, (now - last) / 1000) : 1 / 60
    last = now
    if (tick(dt)) {
      frame = requestAnimationFrame(run)
    } else {
      frame = 0
      last = 0
    }
  }
  return {
    kick() {
      if (!frame && typeof requestAnimationFrame === 'function') {
        frame = requestAnimationFrame(run)
      }
    },
    stop() {
      if (frame) cancelAnimationFrame(frame)
      frame = 0
      last = 0
    },
  }
}

function substeps(dt: number, each: (h: number) => void) {
  const steps = Math.max(1, Math.ceil(dt / SUBSTEP))
  for (let i = 0; i < steps; i += 1) each(dt / steps)
}

const centreOf = (element: HTMLElement) => element.offsetLeft + element.offsetWidth / 2

/**
 * A lens shared by the buttons in `groupRef` that carry `data-lens`. Put the lens element (a
 * LiquidGlass variant="lens") in the group and give it `lensRef`.
 */
export function useLensGroup<G extends HTMLElement = HTMLElement>() {
  const groupRef = useRef<G | null>(null)
  const lensRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const group = groupRef.current
    const lens = lensRef.current
    if (!group || !lens) return
    const st = { x: spring(), vis: spring(), press: spring() }

    const render = () => {
      const stretch = Math.min(Math.abs(st.x.v) / 900, 0.55) * ELASTIC
      const appear = 0.55 + 0.45 * clamp01(st.vis.x)
      const sx = (1 + stretch + st.press.x * 0.16) * appear
      const sy = (1 - stretch * 0.45 - st.press.x * 0.16) * appear
      const half = lens.offsetWidth / 2
      lens.style.transform = `translateX(${(st.x.x - half).toFixed(2)}px) scale(${sx.toFixed(4)}, ${sy.toFixed(4)})`
      lens.style.setProperty('--vis', clamp01(st.vis.x).toFixed(3))
      // Faded out it is taken out of drawing altogether: every row has one, and an invisible
      // lens still runs its backdrop filter on every frame the window draws.
      lens.style.visibility = st.vis.x < 0.01 ? 'hidden' : ''
    }

    const loop = createLoop((dt) => {
      if (motionOff()) {
        snap(st.x)
        snap(st.vis)
        snap(st.press)
      } else {
        substeps(dt, (h) => {
          advance(st.x, h, STIFFNESS, DAMPING)
          advance(st.vis, h, STIFFNESS, FADE_DAMPING)
          advance(st.press, h, PRESS_STIFFNESS, PRESS_DAMPING)
        })
      }
      render()
      return !(settled(st.x) && settled(st.vis) && settled(st.press))
    })

    const moveTo = (button: HTMLElement) => {
      // Appearing: start right on the button instead of sliding in from the last one.
      if (st.vis.x < 0.05) {
        st.x.x = centreOf(button)
        st.x.v = 0
      }
      st.x.t = centreOf(button)
      st.vis.t = 1
      loop.kick()
    }
    const targetOf = (event: Event) =>
      event.target instanceof Element ? event.target.closest<HTMLElement>('[data-lens]') : null

    const onOver = (event: PointerEvent) => {
      const button = targetOf(event)
      if (button && group.contains(button)) moveTo(button)
    }
    const onDown = (event: PointerEvent) => {
      const button = targetOf(event)
      if (!button || !group.contains(button)) return
      moveTo(button)
      st.press.v = 7
      loop.kick()
    }
    const onLeave = () => {
      st.vis.t = 0
      loop.kick()
    }
    const onFocusIn = (event: FocusEvent) => {
      const button = targetOf(event)
      if (button && group.contains(button) && button.matches(':focus-visible')) moveTo(button)
    }
    const onFocusOut = (event: FocusEvent) => {
      if (!(event.relatedTarget instanceof Node && group.contains(event.relatedTarget))) onLeave()
    }

    render()
    group.addEventListener('pointerover', onOver)
    group.addEventListener('pointerdown', onDown)
    group.addEventListener('pointerleave', onLeave)
    group.addEventListener('focusin', onFocusIn)
    group.addEventListener('focusout', onFocusOut)
    return () => {
      loop.stop()
      group.removeEventListener('pointerover', onOver)
      group.removeEventListener('pointerdown', onDown)
      group.removeEventListener('pointerleave', onLeave)
      group.removeEventListener('focusin', onFocusIn)
      group.removeEventListener('focusout', onFocusOut)
    }
  }, [])

  return { groupRef, lensRef }
}

/**
 * The drop under the selected tab of `groupRef` (tabs carry `data-lens`; the selected one
 * `aria-selected="true"`). `selectedKey` changes whenever another tab is picked.
 */
export function useLensDrop<G extends HTMLElement = HTMLElement>(selectedKey: string) {
  const groupRef = useRef<G | null>(null)
  const dropRef = useRef<HTMLDivElement | null>(null)
  const control = useRef<{ select: (instant: boolean) => void } | null>(null)

  useEffect(() => {
    const group = groupRef.current
    const drop = dropRef.current
    if (!group || !drop) return
    const st = { x: spring(), press: spring() }
    let hovered: HTMLElement | null = null

    const selected = () => group.querySelector<HTMLElement>('[data-lens][aria-selected="true"]')
    const aim = (instant: boolean) => {
      const current = selected()
      if (!current) return
      drop.style.width = `${current.offsetWidth}px`
      // Leans a little towards a hovered tab, like a drop being tempted across.
      const lean = hovered && hovered !== current ? (hovered.offsetLeft - current.offsetLeft) * 0.1 : 0
      st.x.t = current.offsetLeft + lean
      if (instant) snap(st.x)
      loop.kick()
    }

    const render = () => {
      const stretch = Math.min(Math.abs(st.x.v) / 1100, 0.6) * ELASTIC
      const sx = 1 + stretch + st.press.x * 0.1
      const sy = 1 - stretch * 0.4 - st.press.x * 0.12
      drop.style.transform = `translateX(${st.x.x.toFixed(2)}px) scale(${sx.toFixed(4)}, ${sy.toFixed(4)})`
    }

    const loop = createLoop((dt) => {
      if (motionOff()) {
        snap(st.x)
        snap(st.press)
      } else {
        substeps(dt, (h) => {
          advance(st.x, h, STIFFNESS, DAMPING)
          advance(st.press, h, PRESS_STIFFNESS, PRESS_DAMPING)
        })
      }
      render()
      return !(settled(st.x) && settled(st.press))
    })

    const onOver = (event: PointerEvent) => {
      const tab = event.target instanceof Element ? event.target.closest<HTMLElement>('[data-lens]') : null
      if (tab && tab !== hovered && group.contains(tab)) {
        hovered = tab
        aim(false)
      }
    }
    const onLeave = () => {
      hovered = null
      aim(false)
    }
    const onDown = (event: PointerEvent) => {
      if (event.target instanceof Element && event.target.closest('[data-lens]')) {
        st.press.v = 5
        loop.kick()
      }
    }

    control.current = {
      select: (instant) => {
        if (!instant) st.press.v = Math.max(st.press.v, 5)
        aim(instant)
      },
    }
    aim(true)
    render()
    const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => aim(true))
    resize?.observe(group)
    group.addEventListener('pointerover', onOver)
    group.addEventListener('pointerleave', onLeave)
    group.addEventListener('pointerdown', onDown)
    return () => {
      loop.stop()
      resize?.disconnect()
      control.current = null
      group.removeEventListener('pointerover', onOver)
      group.removeEventListener('pointerleave', onLeave)
      group.removeEventListener('pointerdown', onDown)
    }
  }, [])

  // A newly picked tab: the drop travels there.
  const firstKey = useRef(selectedKey)
  useEffect(() => {
    if (selectedKey === firstKey.current) return
    firstKey.current = selectedKey
    control.current?.select(false)
  }, [selectedKey])

  return { groupRef, dropRef }
}

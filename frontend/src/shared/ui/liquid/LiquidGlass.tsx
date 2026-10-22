// Liquid glass surface, after rdev/liquid-glass-react (MIT, Copyright 2025 Max Rovensky):
// the same SVG displacement filter with per-channel chromatic aberration, edge-only bending and
// light-catching rim layers. Unlike the original it takes part in normal layout (no absolute
// centring), and instead of its pull towards the pointer it has a hover magnet (magnetize),
// driven through CSS variables so moving the mouse never re-renders React.

import { useContext, useEffect, useId, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { LiquidGlassContext } from './liquidContext'
import { createLiquidMap, type LiquidMaps } from './liquidMaps'

interface GlassFilterProps {
  id: string
  maps: LiquidMaps
  width: number
  height: number
  displacementScale: number
  aberrationIntensity: number
}

/** The map and mask are drawn for this element's exact size, so they are placed 1:1 on it. */
function MapImages({ maps, width, height }: Pick<GlassFilterProps, 'maps' | 'width' | 'height'>) {
  return (
    <>
      <feImage height={height} href={maps.map} preserveAspectRatio="none" result="DISPLACEMENT_MAP" width={width} x="0" y="0" />
      <feImage height={height} href={maps.mask} preserveAspectRatio="none" result="EDGE_MASK" width={width} x="0" y="0" />
      <feImage height={height} href={maps.shape} preserveAspectRatio="none" result="SHAPE" width={width} x="0" y="0" />
    </>
  )
}

/** Last step of both filters: nothing outside the rounded shape (see createShapeImage). */
function ClipToShape() {
  return <feComposite in="UNCLIPPED" in2="SHAPE" operator="in" />
}

/**
 * Edge displacement without the RGB split. Splitting channels and screen-blending them back is
 * only correct over an opaque backdrop: over a translucent one (live mode, where the desktop is
 * composited by Windows outside the page) the three passes stack their alpha and turn grey.
 */
function PlainGlassFilter({ id, maps, width, height, displacementScale }: GlassFilterProps) {
  return (
    <svg aria-hidden="true" className="liquid-defs" focusable="false">
      <filter colorInterpolationFilters="sRGB" filterUnits="userSpaceOnUse" height={height} id={id} width={width} x="0" y="0">
        <MapImages height={height} maps={maps} width={width} />
        <feDisplacementMap
          in="SourceGraphic"
          in2="DISPLACEMENT_MAP"
          result="UNCLIPPED"
          scale={displacementScale}
          xChannelSelector="R"
          yChannelSelector="B"
        />
        <ClipToShape />
      </filter>
    </svg>
  )
}

/** liquid-glass-react's filter: per-channel displacement for chromatic aberration on the rim. */
function GlassFilter({ id, maps, width, height, displacementScale, aberrationIntensity }: GlassFilterProps) {
  return (
    <svg aria-hidden="true" className="liquid-defs" focusable="false">
      <filter colorInterpolationFilters="sRGB" filterUnits="userSpaceOnUse" height={height} id={id} width={width} x="0" y="0">
        <MapImages height={height} maps={maps} width={width} />
        <feDisplacementMap
          in="SourceGraphic"
          in2="DISPLACEMENT_MAP"
          result="RED_DISPLACED"
          scale={displacementScale}
          xChannelSelector="R"
          yChannelSelector="B"
        />
        <feColorMatrix in="RED_DISPLACED" result="RED_CHANNEL" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" />
        <feDisplacementMap
          in="SourceGraphic"
          in2="DISPLACEMENT_MAP"
          result="GREEN_DISPLACED"
          scale={displacementScale * (1 - aberrationIntensity * 0.05)}
          xChannelSelector="R"
          yChannelSelector="B"
        />
        <feColorMatrix in="GREEN_DISPLACED" result="GREEN_CHANNEL" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" />
        <feDisplacementMap
          in="SourceGraphic"
          in2="DISPLACEMENT_MAP"
          result="BLUE_DISPLACED"
          scale={displacementScale * (1 - aberrationIntensity * 0.1)}
          xChannelSelector="R"
          yChannelSelector="B"
        />
        <feColorMatrix in="BLUE_DISPLACED" result="BLUE_CHANNEL" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" />
        <feBlend in="GREEN_CHANNEL" in2="BLUE_CHANNEL" mode="screen" result="GB_COMBINED" />
        <feBlend in="RED_CHANNEL" in2="GB_COMBINED" mode="screen" result="RGB_COMBINED" />
        <feGaussianBlur in="RGB_COMBINED" result="ABERRATED_BLURRED" stdDeviation={Math.max(0.1, 0.5 - aberrationIntensity * 0.1)} />
        <feComposite in="ABERRATED_BLURRED" in2="EDGE_MASK" operator="in" result="EDGE_ABERRATION" />
        <feComponentTransfer in="EDGE_MASK" result="INVERTED_MASK">
          <feFuncA tableValues="1 0" type="table" />
        </feComponentTransfer>
        <feComposite in="SourceGraphic" in2="INVERTED_MASK" operator="in" result="CENTER_CLEAN" />
        <feComposite in="EDGE_ABERRATION" in2="CENTER_CLEAN" operator="over" result="UNCLIPPED" />
        <ClipToShape />
      </filter>
    </svg>
  )
}
// Hover magnet, after the glass toolbar capsule design: the hovered capsule swells a little and
// follows the pointer on a spring, a specular light sits under the pointer, its neighbours in the
// same `.magnet-group` step back, and a press squeezes it. The pointer is followed only while it
// is over the capsule (or over its `.magnet-target`, for glass that takes no pointer events).
const MAGNET_VARS = ['--lg-tx', '--lg-ty', '--lg-sx', '--lg-sy']
// The magnet's pull at the default elasticity, the design's own numbers.
const DEFAULT_ELASTICITY = 0.15

// Where the pointer is, for a capsule that appears under a pointer already resting there.
let lastPointer: { x: number; y: number } | null = null
let trackingPointer = false

function trackPointer() {
  if (trackingPointer || typeof window === 'undefined') return
  trackingPointer = true
  window.addEventListener(
    'pointermove',
    (event) => {
      lastPointer = { x: event.clientX, y: event.clientY }
    },
    { capture: true, passive: true },
  )
}

function magnetize(element: HTMLElement, strength: number) {
  trackPointer()
  const target = element.closest<HTMLElement>('.magnet-target') ?? element
  const group = element.closest<HTMLElement>('.magnet-group')
  let pressed = false

  const place = (x: number, y: number) => {
    const area = target.getBoundingClientRect()
    if (!area.width || !area.height) return
    const nx = ((x - area.left) / area.width - 0.5) * 2
    const ny = ((y - area.top) / area.height - 0.5) * 2
    // Round buttons swell more than wide capsules, as in the design.
    const base = Math.abs(area.width - area.height) < 4 ? 0.1 : 0.045
    const k = Math.abs(nx) * strength
    const [sx, sy, tx, ty] = pressed
      ? [1 - base * 0.6, 1 - base * 0.9, nx * 2 * strength, ny * strength]
      : [1 + base + k * 0.012, 1 + base - k * 0.008, nx * 4 * strength, ny * 2.5 * strength - 1]
    const glass = element.getBoundingClientRect()
    setVar(element, '--lg-sx', sx.toFixed(4))
    setVar(element, '--lg-sy', sy.toFixed(4))
    setVar(element, '--lg-tx', `${tx.toFixed(2)}px`)
    setVar(element, '--lg-ty', `${ty.toFixed(2)}px`)
    setVar(element, '--lg-spot-x', `${Math.round(x - glass.left)}px`)
    setVar(element, '--lg-spot-y', `${Math.round(y - glass.top)}px`)
  }

  const enter = (x: number, y: number) => {
    element.classList.add('is-hovered')
    group?.classList.add('is-magnet-on')
    place(x, y)
  }

  const leave = () => {
    pressed = false
    element.classList.remove('is-hovered', 'is-pressed')
    for (const name of MAGNET_VARS) {
      element.style.removeProperty(name)
      writtenVars.get(element)?.delete(name)
    }
    if (group && !group.querySelector('.liquid.is-hovered')) group.classList.remove('is-magnet-on')
  }

  const onEnter = (event: PointerEvent) => enter(event.clientX, event.clientY)
  const onMove = (event: PointerEvent) => place(event.clientX, event.clientY)
  const onDown = (event: PointerEvent) => {
    pressed = true
    element.classList.add('is-pressed')
    place(event.clientX, event.clientY)
  }
  const onUp = (event: PointerEvent) => {
    pressed = false
    element.classList.remove('is-pressed')
    place(event.clientX, event.clientY)
  }

  target.addEventListener('pointerenter', onEnter)
  target.addEventListener('pointermove', onMove)
  target.addEventListener('pointerleave', leave)
  target.addEventListener('pointerdown', onDown)
  target.addEventListener('pointerup', onUp)
  if (lastPointer && target.matches(':hover')) enter(lastPointer.x, lastPointer.y)

  return () => {
    target.removeEventListener('pointerenter', onEnter)
    target.removeEventListener('pointermove', onMove)
    target.removeEventListener('pointerleave', leave)
    target.removeEventListener('pointerdown', onDown)
    target.removeEventListener('pointerup', onUp)
    leave()
  }
}

// Rounded to what can be seen, and only written when it changes: an unchanged write still
// restyles and repaints.
const writtenVars = new WeakMap<HTMLElement, Map<string, string>>()

function setVar(element: HTMLElement, name: string, value: string) {
  let vars = writtenVars.get(element)
  if (!vars) {
    vars = new Map()
    writtenVars.set(element, vars)
  }
  if (vars.get(name) === value) return
  vars.set(name, value)
  element.style.setProperty(name, value)
}

// A lens: the clear, bright drop of glass that slides over a row of buttons or tabs and
// magnifies what is under it (polar map, almost no frost). Its movement is driven from outside
// (useLiquidLens).
const LENS_DISPLACEMENT = 16
const LENS_BACKDROP = 'blur(0.4px) saturate(180%) brightness(1.14)'

interface LiquidGlassProps {
  children?: ReactNode
  className?: string
  /** Corner radius in px; defaults to a capsule. */
  cornerRadius?: number
  /** Hover magnet (see magnetize): for capsules the pointer works on. */
  magnetic?: boolean
  /** "lens": the moving magnifying drop instead of a frosted surface. */
  variant?: 'surface' | 'lens'
  style?: CSSProperties
  ref?: React.Ref<HTMLDivElement>
}

export function LiquidGlass({
  children,
  className = '',
  cornerRadius = 999,
  magnetic = false,
  variant = 'surface',
  style,
  ref,
}: LiquidGlassProps) {
  const settings = useContext(LiquidGlassContext)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const filterId = `liquid-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const [size, setSize] = useState({ width: 0, height: 0 })
  const liquid = settings.liquidEnabled
  const lens = variant === 'lens'
  const magnet = magnetic && !lens && settings.animations
  const setRoot = (element: HTMLDivElement | null) => {
    rootRef.current = element
    if (typeof ref === 'function') ref(element)
    else if (ref) ref.current = element
  }

  useEffect(() => {
    const element = rootRef.current
    if (!element || !liquid || typeof ResizeObserver === 'undefined') {
      return
    }
    const resize = (width: number, height: number) =>
      setSize((current) => (current.width === width && current.height === height ? current : { width, height }))
    const observer = new ResizeObserver(([entry]) => {
      resize(Math.round(entry.contentRect.width), Math.round(entry.contentRect.height))
    })
    observer.observe(element)
    // Measured right away as well: the app starts hidden in the tray, and a hidden page delivers
    // no ResizeObserver callbacks until it is first shown. Without this every surface would draw
    // its maps in the very frame the panel is first summoned, and that first summon stuttered.
    const style = getComputedStyle(element)
    const pad = (value: string) => parseFloat(value) || 0
    resize(
      Math.round(element.clientWidth - pad(style.paddingLeft) - pad(style.paddingRight)),
      Math.round(element.clientHeight - pad(style.paddingTop) - pad(style.paddingBottom)),
    )
    return () => observer.disconnect()
  }, [liquid])

  const mode = lens ? 'lens' : settings.liquidMode
  const map = useMemo(
    () => (liquid ? createLiquidMap(mode, size.width, size.height, cornerRadius) : null),
    [liquid, mode, size.width, size.height, cornerRadius],
  )

  useEffect(() => {
    const element = rootRef.current
    if (!element || !magnet) {
      return
    }
    return magnetize(element, settings.elasticity / DEFAULT_ELASTICITY)
  }, [magnet, settings.elasticity])

  // Frost formula from liquid-glass-react: a 4px base blur plus frost.
  const blur = 4 + settings.frost * 32
  const displacement = lens ? LENS_DISPLACEMENT : settings.displacementScale
  const backdrop = lens ? LENS_BACKDROP : `blur(${blur}px) saturate(${settings.liquidSaturation}%)`
  const warpStyle: CSSProperties = {
    backdropFilter: backdrop,
    WebkitBackdropFilter: backdrop,
    filter: map && displacement > 0 ? `url(#${filterId})` : undefined,
  }

  const classes = [
    'liquid',
    liquid ? 'is-liquid' : 'is-plain',
    magnet ? 'is-magnetic' : '',
    lens ? 'is-lens' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      aria-hidden={lens || undefined}
      className={classes}
      ref={setRoot}
      style={{ ...style, '--lg-radius': `${cornerRadius}px`, '--lg-shade': settings.liquidShade / 100 } as CSSProperties}
    >
      {map && displacement > 0 ? (
        settings.translucentBackdrop || settings.aberrationIntensity === 0 ? (
          <PlainGlassFilter
            aberrationIntensity={settings.aberrationIntensity}
            displacementScale={displacement}
            height={size.height}
            id={filterId}
            maps={map}
            width={size.width}
          />
        ) : (
          <GlassFilter
            aberrationIntensity={settings.aberrationIntensity}
            displacementScale={displacement}
            height={size.height}
            id={filterId}
            maps={map}
            width={size.width}
          />
        )
      ) : null}
      <span aria-hidden="true" className="liquid-warp" style={warpStyle} />
      <span aria-hidden="true" className="liquid-shade" />
      <span aria-hidden="true" className="liquid-rim is-screen" />
      <span aria-hidden="true" className="liquid-rim is-overlay" />
      {magnet ? <span aria-hidden="true" className="liquid-spot" /> : null}
      {children === undefined ? null : <div className="liquid-content">{children}</div>}
    </div>
  )
}

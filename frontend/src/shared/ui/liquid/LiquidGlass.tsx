// Liquid glass surface, after rdev/liquid-glass-react (MIT, Copyright 2025 Max Rovensky):
// the same SVG displacement filter with per-channel chromatic aberration, edge-only bending,
// light-catching rim layers and an elastic pull towards the pointer. Unlike the original it
// takes part in normal layout (no absolute centring) and drives the pointer-dependent styles
// through CSS variables, so moving the mouse never re-renders React.

import { useContext, useEffect, useId, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { LiquidGlassContext } from './liquidContext'
import { createLiquidMap, type LiquidMaps } from './liquidMaps'

const ACTIVATION_ZONE = 200

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
// One shared pointer listener for every liquid surface on the page. Each surface measures, and
// hands back its writes; they all run after every surface has measured, so the browser lays the
// page out once per pointer frame rather than once per surface.
type PointerListener = (x: number, y: number) => () => void
const pointerListeners = new Set<PointerListener>()
let pointerFrame = 0
let pointerX = 0
let pointerY = 0

function handlePointerMove(event: PointerEvent) {
  pointerX = event.clientX
  pointerY = event.clientY
  if (pointerFrame) {
    return
  }
  pointerFrame = requestAnimationFrame(() => {
    pointerFrame = 0
    const writes = [...pointerListeners].map((listener) => listener(pointerX, pointerY))
    writes.forEach((write) => write())
  })
}

function subscribePointer(listener: PointerListener) {
  if (pointerListeners.size === 0) {
    window.addEventListener('pointermove', handlePointerMove, { passive: true })
  }
  pointerListeners.add(listener)
  return () => {
    pointerListeners.delete(listener)
    if (pointerListeners.size === 0) {
      window.removeEventListener('pointermove', handlePointerMove)
    }
  }
}

/** Elastic pull + rim light angle for one pointer position, as in liquid-glass-react. */
function updateLiquidPointer(element: HTMLElement, x: number, y: number, elasticity: number) {
  const rect = element.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2
  const deltaX = x - centerX
  const deltaY = y - centerY

  const edgeX = Math.max(0, Math.abs(deltaX) - rect.width / 2)
  const edgeY = Math.max(0, Math.abs(deltaY) - rect.height / 2)
  const edgeDistance = Math.hypot(edgeX, edgeY)
  const fade = edgeDistance > ACTIVATION_ZONE ? 0 : 1 - edgeDistance / ACTIVATION_ZONE

  let scaleX = 1
  let scaleY = 1
  const centerDistance = Math.hypot(deltaX, deltaY)
  if (fade > 0 && centerDistance > 0) {
    const nx = Math.abs(deltaX / centerDistance)
    const ny = Math.abs(deltaY / centerDistance)
    const stretch = Math.min(centerDistance / 300, 1) * elasticity * fade
    scaleX = Math.max(0.8, 1 + nx * stretch * 0.3 - ny * stretch * 0.15)
    scaleY = Math.max(0.8, 1 + ny * stretch * 0.3 - nx * stretch * 0.15)
  }

  const offsetX = rect.width ? (deltaX / rect.width) * 100 : 0
  const offsetY = rect.height ? (deltaY / rect.height) * 100 : 0
  const clampedX = Math.max(-60, Math.min(60, offsetX))
  const clampedY = Math.max(-60, Math.min(60, offsetY))
  return () => {
    setVar(element, '--lg-tx', `${(deltaX * elasticity * 0.1 * fade).toFixed(1)}px`)
    setVar(element, '--lg-ty', `${(deltaY * elasticity * 0.1 * fade).toFixed(1)}px`)
    setVar(element, '--lg-sx', scaleX.toFixed(3))
    setVar(element, '--lg-sy', scaleY.toFixed(3))
    setVar(element, '--lg-angle', `${(135 + clampedX * 1.2).toFixed(1)}deg`)
    setVar(element, '--lg-boost', Math.min(1, Math.abs(offsetX) / 100).toFixed(2))
    setVar(element, '--lg-stop-1', `${Math.max(10, 33 + clampedY * 0.3).toFixed(1)}%`)
    setVar(element, '--lg-stop-2', `${Math.min(90, 66 + clampedY * 0.4).toFixed(1)}%`)
  }
}

// Every surface hears every pointer move; most moves leave a given surface's values as they were
// (the pointer is far off, and they are clamped), and an unchanged write still restyles and
// repaints it. Rounded to what can be seen, and only written when it changes.
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
// (useLiquidLens), so it takes no part in the pointer pull.
const LENS_DISPLACEMENT = 16
const LENS_BACKDROP = 'blur(0.4px) saturate(180%) brightness(1.14)'

interface LiquidGlassProps {
  children?: ReactNode
  className?: string
  /** Corner radius in px; defaults to a capsule. */
  cornerRadius?: number
  /** Adds the hover/press glow used by clickable surfaces. */
  interactive?: boolean
  /** "lens": the moving magnifying drop instead of a frosted surface. */
  variant?: 'surface' | 'lens'
  style?: CSSProperties
  ref?: React.Ref<HTMLDivElement>
}

export function LiquidGlass({
  children,
  className = '',
  cornerRadius = 999,
  interactive = false,
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
  const elastic = liquid && !lens && settings.animations && settings.elasticity > 0
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
    if (!element) {
      return
    }
    if (!elastic) {
      for (const name of ['--lg-tx', '--lg-ty', '--lg-sx', '--lg-sy']) {
        element.style.removeProperty(name)
        writtenVars.get(element)?.delete(name)
      }
      return
    }
    return subscribePointer((x, y) => updateLiquidPointer(element, x, y, settings.elasticity))
  }, [elastic, settings.elasticity])

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
    interactive ? 'is-interactive' : '',
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
      {interactive ? <span aria-hidden="true" className="liquid-glow" /> : null}
      {children === undefined ? null : <div className="liquid-content">{children}</div>}
    </div>
  )
}

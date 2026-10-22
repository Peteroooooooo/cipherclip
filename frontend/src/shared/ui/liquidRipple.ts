// A water ripple across a whole element: real refraction, not drawn circles.
//
// An SVG displacement filter is put on the element for the length of the ripple. Its map is a
// ring of radial waves (a strong front with a few weaker ones trailing behind it, like a stone
// dropped in water), drawn once and then placed, grown and faded per frame: the feImage grows
// outwards from the origin while the displacement scale dies away. Where the wave passes, what is
// under it is bent towards and away from the centre. A faint ring of reflected light rides on the
// front.
//
// While the filter is on, backdrop-filter glass inside the element only sees the element itself
// (a filter isolates its subtree), which is why it is removed again as soon as the wave has gone.

import { createPixelCanvas } from './pixelCanvas'

const FILTER_ID = 'cc-liquid-ripple'
const MAP_SIZE = 384
const DURATION_MS = 1600
// Strongest bend (px) at the start; the wave loses energy as it spreads.
const MAX_SCALE = 22
// Softens the map once it is stretched over the panel, so the water bends instead of tearing.
const MAP_SMOOTHING = 2.5

let mapUrl: string | null = null
let nodes: { map: SVGFEImageElement; displace: SVGFEDisplacementMapElement; filter: SVGFilterElement } | null = null

function smoothStep(edge0: number, edge1: number, x: number) {
  const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)))
  return t * t * (3 - 2 * t)
}

/** Radial wave profile at normalised radius t (0 centre, 1 edge of the map). */
function wave(t: number) {
  const FRONT = 0.93
  if (t >= 1 || t < 0.12) return 0
  if (t > FRONT) {
    // The leading edge rises out of still water.
    return Math.sin(((t - FRONT) / (1 - FRONT)) * Math.PI) * 0.6 * (1 - smoothStep(FRONT, 1, t))
  }
  const behind = FRONT - t
  // Two or three crests behind the front, each weaker than the one before; calm in the middle.
  return -Math.sin(behind * Math.PI * 2 * 3.2) * Math.exp(-behind * 3.6) * smoothStep(0.12, 0.4, t)
}

function createMap() {
  const { canvas, context } = createPixelCanvas(MAP_SIZE, MAP_SIZE)
  if (!context) return null
  const image = context.createImageData(MAP_SIZE, MAP_SIZE)
  const half = MAP_SIZE / 2
  for (let y = 0; y < MAP_SIZE; y += 1) {
    for (let x = 0; x < MAP_SIZE; x += 1) {
      const px = (x + 0.5 - half) / half
      const py = (y + 0.5 - half) / half
      const t = Math.hypot(px, py)
      const strength = wave(t)
      const ux = t ? px / t : 0
      const uy = t ? py / t : 0
      const index = (y * MAP_SIZE + x) * 4
      image.data[index] = 128 + ux * strength * 127
      image.data[index + 1] = 128 + uy * strength * 127
      image.data[index + 2] = 128
      image.data[index + 3] = 255
    }
  }
  context.putImageData(image, 0, 0)
  return canvas.toDataURL()
}

function ensureFilter() {
  if (nodes && document.getElementById(FILTER_ID)) return nodes
  mapUrl ??= createMap()
  if (!mapUrl) return null
  const ns = 'http://www.w3.org/2000/svg'
  const svg = document.createElementNS(ns, 'svg')
  svg.setAttribute('aria-hidden', 'true')
  svg.setAttribute('width', '0')
  svg.setAttribute('height', '0')
  svg.style.position = 'absolute'
  const filter = document.createElementNS(ns, 'filter')
  filter.id = FILTER_ID
  filter.setAttribute('filterUnits', 'userSpaceOnUse')
  filter.setAttribute('primitiveUnits', 'userSpaceOnUse')
  filter.setAttribute('color-interpolation-filters', 'sRGB')
  // Still water everywhere the ring does not reach: 128 = no displacement.
  const flood = document.createElementNS(ns, 'feFlood')
  flood.setAttribute('flood-color', 'rgb(128, 128, 128)')
  flood.setAttribute('result', 'still')
  const map = document.createElementNS(ns, 'feImage')
  map.setAttribute('href', mapUrl)
  map.setAttribute('preserveAspectRatio', 'none')
  map.setAttribute('result', 'ring')
  const merge = document.createElementNS(ns, 'feMerge')
  merge.setAttribute('result', 'raw')
  for (const input of ['still', 'ring']) {
    const node = document.createElementNS(ns, 'feMergeNode')
    node.setAttribute('in', input)
    merge.append(node)
  }
  const smooth = document.createElementNS(ns, 'feGaussianBlur')
  smooth.setAttribute('in', 'raw')
  smooth.setAttribute('stdDeviation', String(MAP_SMOOTHING))
  smooth.setAttribute('result', 'map')
  const displace = document.createElementNS(ns, 'feDisplacementMap')
  displace.setAttribute('in', 'SourceGraphic')
  displace.setAttribute('in2', 'map')
  displace.setAttribute('xChannelSelector', 'R')
  displace.setAttribute('yChannelSelector', 'G')
  filter.append(flood, map, merge, smooth, displace)
  svg.append(filter)
  document.body.append(svg)
  nodes = { map, displace, filter }
  return nodes
}

/**
 * Sends one ripple across `target` from (originX, originY), in client coordinates. Returns a
 * function that stops it early.
 */
export function playLiquidRipple(target: HTMLElement, originX: number, originY: number) {
  const filter = ensureFilter()
  if (!filter || typeof requestAnimationFrame !== 'function') return () => {}

  const box = target.getBoundingClientRect()
  const cx = originX - box.left
  const cy = originY - box.top
  // Far enough to leave the farthest corner.
  const reach = Math.hypot(Math.max(cx, box.width - cx), Math.max(cy, box.height - cy)) + 60
  filter.filter.setAttribute('x', '0')
  filter.filter.setAttribute('y', '0')
  filter.filter.setAttribute('width', String(box.width))
  filter.filter.setAttribute('height', String(box.height))

  // The light on the wave front.
  const shine = document.createElement('span')
  shine.className = 'liquid-ripple-shine'
  shine.setAttribute('aria-hidden', 'true')
  shine.style.setProperty('--ripple-x', `${cx}px`)
  shine.style.setProperty('--ripple-y', `${cy}px`)
  target.append(shine)

  const start = performance.now()
  let frame = 0
  const stop = () => {
    cancelAnimationFrame(frame)
    target.style.removeProperty('filter')
    shine.remove()
  }

  const step = (now: number) => {
    const p = Math.min(1, (now - start) / DURATION_MS)
    // Fast at first, slowing as it spreads, as a real ripple does.
    const travel = 1 - Math.pow(1 - p, 2.2)
    const radius = 24 + (reach - 24) * travel
    const energy = Math.pow(1 - p, 1.6)
    filter.map.setAttribute('x', String(cx - radius))
    filter.map.setAttribute('y', String(cy - radius))
    filter.map.setAttribute('width', String(radius * 2))
    filter.map.setAttribute('height', String(radius * 2))
    filter.displace.setAttribute('scale', (MAX_SCALE * energy).toFixed(2))
    shine.style.setProperty('--ripple-r', `${radius.toFixed(1)}px`)
    shine.style.opacity = String(Math.min(1, p * 8) * energy)
    if (p < 1) {
      frame = requestAnimationFrame(step)
    } else {
      stop()
    }
  }

  target.style.filter = `url(#${FILTER_ID})`
  frame = requestAnimationFrame(step)
  return stop
}

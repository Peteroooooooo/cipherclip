// Displacement maps generated for the exact size and corner radius of each liquid surface.
//
// liquid-glass-react ships fixed bitmaps drawn for its demo capsule; stretched over a wide, short
// bar their edges sample from outside the element and let the sharp content beneath show
// through. These maps are computed from the rounded rectangle itself and every offset points
// inwards, so the filter only ever samples pixels that belong to the glass.
//
// Encoding (as SVG feDisplacementMap expects): red = x offset, green and blue = y offset,
// 128 = no shift, 0 / 255 = full shift left/up or right/down.

import type { LiquidMode } from '../../../app/types'
import { createPixelCanvas } from '../pixelCanvas'
import { createShaderMap } from './shaderMap'

// Big surfaces only need a coarse map; feImage stretches it back up.
const MAX_MAP_SIDE = 480

function smoothStep(edge0: number, edge1: number, x: number) {
  const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)))
  return t * t * (3 - 2 * t)
}

export interface LiquidMaps {
  /** Displacement map for feDisplacementMap. */
  map: string
  /** Rim mask (alpha = how much of the bent edge shows), used to keep the centre crisp. */
  mask: string
  /** The rounded rectangle itself, as a vector image at full size. */
  shape: string
}

/**
 * Chromium does not reliably re-apply clip-path to an element that has both a url() filter and
 * a backdrop-filter once it is transformed (the elastic pull): the square filter region then
 * shows through at the corners. Cutting the filter output to this shape keeps the corners empty.
 */
function createShapeImage(width: number, height: number, radius: number) {
  const r = Math.min(radius, width / 2, height / 2)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="${width}" height="${height}" rx="${r}" fill="#fff"/></svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

// Surfaces of the same size share their maps (every row's lens, for one): drawn once each.
const mapCache = new Map<string, LiquidMaps | null>()

export function createLiquidMap(mode: LiquidMode | 'lens', width: number, height: number, radius: number): LiquidMaps | null {
  const key = `${mode} ${width} ${height} ${radius}`
  if (!mapCache.has(key)) mapCache.set(key, drawLiquidMap(mode, width, height, radius))
  return mapCache.get(key) ?? null
}

function drawLiquidMap(mode: LiquidMode | 'lens', width: number, height: number, radius: number): LiquidMaps | null {
  if (width < 2 || height < 2) {
    return null
  }

  const scale = Math.min(1, MAX_MAP_SIDE / Math.max(width, height))
  const w = Math.max(2, Math.round(width * scale))
  const h = Math.max(2, Math.round(height * scale))
  const { canvas, context } = createPixelCanvas(w, h)
  const { canvas: maskCanvas, context: maskContext } = createPixelCanvas(w, h)
  if (!context || !maskContext) {
    return null
  }

  const halfW = w / 2
  const halfH = h / 2
  const r = Math.min(radius * scale, halfW, halfH)
  // Width of the bending rim: thin for "standard", wide and linear for "prominent".
  const band = mode === 'prominent' ? Math.max(4, Math.min(halfH, r * 1.6, 30 * scale)) : Math.max(3, Math.min(r, 16 * scale))

  const image = context.createImageData(w, h)
  const mask = maskContext.createImageData(w, h)
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const px = x + 0.5 - halfW
      const py = y + 0.5 - halfH
      let dx = 0
      let dy = 0
      let rim = 0

      if (mode === 'polar' || mode === 'lens') {
        // Lens: everything is pulled towards the centre, more strongly further out. The moving
        // lens also pulls gently in the middle, so what is under it looks magnified (but not
        // hard at the rim, which would sample past the centre and mirror the icon under it).
        const ux = px / halfW
        const uy = py / halfH
        const reach = Math.hypot(ux, uy)
        const strength = mode === 'lens' ? 0.3 + 0.35 * smoothStep(0.5, 1, reach) : smoothStep(0.35, 1, reach)
        dx = -ux * strength
        dy = -uy * strength
        rim = strength
      } else {
        // Signed distance to the rounded rectangle; `depth` is how far inside the edge we are.
        const qx = Math.abs(px) - (halfW - r)
        const qy = Math.abs(py) - (halfH - r)
        const depth = r - Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) - Math.min(Math.max(qx, qy), 0)
        if (depth < band) {
          let nx = 0
          let ny = 0
          if (qx > 0 && qy > 0) {
            const length = Math.hypot(qx, qy) || 1
            nx = (qx / length) * Math.sign(px)
            ny = (qy / length) * Math.sign(py)
          } else if (qx > qy) {
            nx = Math.sign(px)
          } else {
            ny = Math.sign(py)
          }
          const t = Math.max(0, Math.min(1, 1 - depth / band))
          const strength = mode === 'prominent' ? t : t * t
          dx = -nx * strength
          dy = -ny * strength
          rim = Math.min(1, t * 1.5)
        }
      }

      const index = (y * w + x) * 4
      image.data[index] = 128 + dx * 127
      image.data[index + 1] = 128 + dy * 127
      image.data[index + 2] = 128 + dy * 127
      image.data[index + 3] = 255
      mask.data[index] = 255
      mask.data[index + 1] = 255
      mask.data[index + 2] = 255
      mask.data[index + 3] = rim * 255
    }
  }

  context.putImageData(image, 0, 0)
  maskContext.putImageData(mask, 0, 0)
  const shaderMap = mode === 'shader' ? createShaderMap(width, height) : null
  return {
    map: shaderMap ?? canvas.toDataURL(),
    mask: maskCanvas.toDataURL(),
    shape: createShapeImage(width, height, radius),
  }
}

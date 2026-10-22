// "Shader" displacement map, generated per element size. Ported from liquid-glass-react
// (https://github.com/rdev/liquid-glass-react, MIT, Copyright 2025 Max Rovensky), which adapted
// it from https://github.com/shuding/liquid-glass.

function smoothStep(a: number, b: number, t: number) {
  const x = Math.max(0, Math.min(1, (t - a) / (b - a)))
  return x * x * (3 - 2 * x)
}

function roundedRectSdf(x: number, y: number, width: number, height: number, radius: number) {
  const qx = Math.abs(x) - width + radius
  const qy = Math.abs(y) - height + radius
  return Math.min(Math.max(qx, qy), 0) + Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) - radius
}

import { createPixelCanvas } from '../pixelCanvas'

/** Lens that pulls the backdrop towards the centre near the rounded edges. */
function liquidLens(u: number, v: number) {
  const ix = u - 0.5
  const iy = v - 0.5
  const distanceToEdge = roundedRectSdf(ix, iy, 0.3, 0.2, 0.6)
  const displacement = smoothStep(0.8, 0, distanceToEdge - 0.15)
  const scaled = smoothStep(0, 1, displacement)
  return { x: ix * scaled + 0.5, y: iy * scaled + 0.5 }
}

export function createShaderMap(width: number, height: number): string | null {
  const w = Math.max(1, Math.round(width))
  const h = Math.max(1, Math.round(height))
  const { canvas, context } = createPixelCanvas(w, h)
  if (!context) {
    return null
  }

  const raw = new Float32Array(w * h * 2)
  let maxScale = 0
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const pos = liquidLens(x / w, y / h)
      const dx = pos.x * w - x
      const dy = pos.y * h - y
      maxScale = Math.max(maxScale, Math.abs(dx), Math.abs(dy))
      const index = (y * w + x) * 2
      raw[index] = dx
      raw[index + 1] = dy
    }
  }
  maxScale = Math.max(maxScale, 1)

  const image = context.createImageData(w, h)
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const index = (y * w + x) * 2
      const edgeFactor = Math.min(1, Math.min(x, y, w - x - 1, h - y - 1) / 2)
      const r = (raw[index] * edgeFactor) / maxScale + 0.5
      const g = (raw[index + 1] * edgeFactor) / maxScale + 0.5
      const pixel = (y * w + x) * 4
      image.data[pixel] = Math.max(0, Math.min(255, r * 255))
      image.data[pixel + 1] = Math.max(0, Math.min(255, g * 255))
      image.data[pixel + 2] = Math.max(0, Math.min(255, g * 255))
      image.data[pixel + 3] = 255
    }
  }
  context.putImageData(image, 0, 0)
  return canvas.toDataURL()
}

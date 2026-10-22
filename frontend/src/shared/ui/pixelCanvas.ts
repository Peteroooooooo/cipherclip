/**
 * A canvas for pixels made in JS and read straight back as an image (displacement maps).
 * willReadFrequently keeps it in memory: a GPU canvas makes every toDataURL wait for a readback
 * from the GPU (measured: about half a second for all the panel's surfaces together, on the first
 * summon).
 */
export function createPixelCanvas(width: number, height: number) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  return { canvas, context: canvas.getContext('2d', { willReadFrequently: true }) }
}

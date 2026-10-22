/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, test } from 'vitest'

const cssPath = resolve(process.cwd(), 'src/index.css')
const css = readFileSync(cssPath, 'utf8')

describe('visual theme tokens', () => {
  test('defines the thin-glass material for both appearances', () => {
    expect(css).toContain('color-scheme: light dark;')
    // The theme (system / light / dark) is resolved in JS onto <html data-theme>.
    expect(css).toContain(":root[data-theme='dark'] {")
    expect(css).toContain('--window-tint:')
    expect(css).toContain('--layer-active:')
    expect(css).toContain('--rim-light:')
  })

  test('uses large window corners and keeps the shadow margin in sync with the backend', () => {
    expect(css).toContain('--window-radius: 24px;')
    // backend/app/window.py sizes the native window with WINDOW_SHADOW_MARGIN = 16 per side.
    expect(css).toContain('--shell-pad: 16px;')
  })

  test('keeps the desktop page transparent so the native backdrop shows through', () => {
    expect(css).toContain('html.is-desktop body {')
    expect(css).toMatch(/html\.is-desktop body \{\s*background: transparent;/)
  })

  test('never lets a leftover desktop snapshot cover the live compositor blur', () => {
    // Switching Snapshot -> Live keeps `has-backdrop` on <html>; every snapshot rule must
    // exclude `glass-live`, otherwise the frozen frame stays painted over the live glass.
    const snapshotSelectors = css.match(/^[^\n{]*\.has-backdrop[^\n{]*\{/gm) ?? []
    expect(snapshotSelectors.length).toBeGreaterThan(0)
    for (const selector of snapshotSelectors) {
      expect(selector).toContain(':not(.glass-live)')
    }
  })

  test('keeps liquid glass able to sample the page behind it', () => {
    // isolation or a blend mode inside .liquid makes it the backdrop root of .liquid-warp,
    // whose backdrop-filter then has nothing to blur or refract.
    const liquidBlock = css.slice(css.indexOf('/* ═══════════ LIQUID GLASS'), css.indexOf('/* ═══════════ PANEL'))
    expect(liquidBlock).toContain('.liquid-warp {')
    expect(liquidBlock).not.toMatch(/mix-blend-mode\s*:/)
    expect(liquidBlock).not.toMatch(/isolation\s*:/)
  })

  test('honours reduced motion', () => {
    expect(css).toContain('@media (prefers-reduced-motion: reduce)')
  })
})

/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, test } from 'vitest'

const cssPath = resolve(process.cwd(), 'src/index.css')
const css = readFileSync(cssPath, 'utf8')

describe('visual theme tokens', () => {
  test('uses cyan-tinted hover surfaces and cooler pinned hover states', () => {
    expect(css).toContain('--surface-hover: rgba(6, 31, 36, 0.82);')
    expect(css).toContain('--surface-active: rgba(8, 46, 54, 0.92);')
    expect(css).toContain('--border-hover: rgba(0, 240, 255, 0.3);')
    expect(css).toContain('--purple-hover: rgba(116, 92, 255, 0.16);')
    expect(css).toContain('--purple-active: rgba(122, 100, 255, 0.22);')
    expect(css).toContain('.search-box:hover {')
    expect(css).toContain('background: rgba(0, 240, 255, 0.08);')
  })
})

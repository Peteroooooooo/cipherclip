import { describe, expect, test } from 'vitest'
import { DEFAULT_APPEARANCE, GLASS_PRESETS, matchingPreset, normalizeAppearance } from './appearance'

describe('white and black points', () => {
  test('old tint, brightness and contrast become the same white and black points as the backend', () => {
    const smoke = normalizeAppearance({ tintGray: 130, tintOpacity: 10, backdropBrightness: 66 } as never)
    expect([smoke.whitePoint, smoke.blackPoint]).toEqual([164, 13])
    expect(matchingPreset(GLASS_PRESETS, smoke)?.id).toBe('smoke')
    expect(smoke).not.toHaveProperty('tintGray')

    // The look of the former Mist template, saved with the old tint parameters.
    const mist = normalizeAppearance({
      backdropBlur: 20,
      backdropSaturation: 110,
      rimLight: 0,
      edgeHighlight: 35,
      textTone: 'auto',
      textHalo: 35,
      secondaryTextOpacity: 64,
      tintGray: 110,
      tintOpacity: 22,
      backdropBrightness: 72,
      backdropContrast: 70,
    } as never)
    expect([mist.whitePoint, mist.blackPoint]).toEqual([146, 45])
    // Mist is no longer a template: the values are kept as they were and simply read as custom.
    expect(matchingPreset(GLASS_PRESETS, mist)).toBeNull()
    expect([mist.backdropBlur, mist.textHalo]).toEqual([20, 35])

    const dark = normalizeAppearance({ material: 'clear', theme: 'dark', tintOpacity: 32 } as never)
    expect([dark.whitePoint, dark.blackPoint, dark.rimLight]).toEqual([161, 8, 45])
  })

  test('black always stays below white', () => {
    const crossed = normalizeAppearance({ ...DEFAULT_APPEARANCE, whitePoint: 50, blackPoint: 200 })
    expect([crossed.whitePoint, crossed.blackPoint]).toEqual([50, 46])
  })
})

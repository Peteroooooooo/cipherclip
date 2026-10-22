import { createContext } from 'react'
import { DEFAULT_APPEARANCE } from '../../../app/appearance'
import type { AppearanceSettings } from '../../../app/types'

export type LiquidSettings = Pick<
  AppearanceSettings,
  | 'liquidEnabled'
  | 'liquidMode'
  | 'displacementScale'
  | 'aberrationIntensity'
  | 'elasticity'
  | 'frost'
  | 'liquidSaturation'
  | 'liquidShade'
  | 'animations'
> & {
  /** True when what is behind the page is composited by Windows (live glass), not painted in it. */
  translucentBackdrop: boolean
}

/** Liquid glass parameters from the appearance settings, read by every LiquidGlass surface. */
export const LiquidGlassContext = createContext<LiquidSettings>({ ...DEFAULT_APPEARANCE, translucentBackdrop: false })

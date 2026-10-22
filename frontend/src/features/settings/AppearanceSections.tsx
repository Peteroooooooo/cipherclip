import { ArrowCounterClockwise } from '@phosphor-icons/react'
import {
  BACKDROP_BLUR_MAX,
  GLASS_PRESETS,
  LIQUID_PRESETS,
  MIN_POINT_GAP,
  matchingPreset,
  resolveTextTone,
} from '../../app/appearance'
import type { AppearanceSettings, GlassSource, LiquidMode, TextTone } from '../../app/types'
import { ChoiceRow, PresetRow, SliderRow, ToggleRow } from './controls'
import { LiquidPreview } from './LiquidPreview'

export interface GlassInfo {
  /** Mode the native window is actually using; null outside the desktop app. */
  mode: GlassSource | null
  liveAvailable: boolean
  /** Live glass with real, adjustable filters (otherwise Windows' fixed blur). */
  filtered?: boolean
}

interface AppearanceSectionsProps {
  appearance: AppearanceSettings
  glassInfo: GlassInfo
  onChange: (patch: Partial<AppearanceSettings>) => void
  onReset: () => void
}

const percent = (value: number) => `${Math.round(value)}%`
const pixels = (value: number) => `${Math.round(value)} px`
const decimal = (digits: number) => (value: number) => value.toFixed(digits)

export function AppearanceSections({ appearance, glassInfo, onChange, onReset }: AppearanceSectionsProps) {
  const live = appearance.glassSource === 'live'
  // Live glass without the filter pipeline is Windows' own blur, whose strength is fixed.
  const liveFixed = live && glassInfo.liveAvailable && !glassInfo.filtered
  const liquid = appearance.liquidEnabled
  const sourceHint = glassInfo.liveAvailable
    ? live
      ? glassInfo.filtered
        ? 'The desktop behind the panel, blurred and filtered in real time'
        : "Windows' own live blur (fixed strength); this system cannot capture behind the panel"
      : 'A frosted snapshot taken when the panel opens; liquid edges bend it'
    : 'Live blur needs the native helper (desktop app only); using snapshots'
  const autoTone = resolveTextTone({ ...appearance, textTone: 'auto' }) === 'light' ? 'white' : 'black'

  return (
    <>
      <section aria-labelledby="appearance-heading" className="settings-section">
        <h2 id="appearance-heading">Appearance</h2>
        <div className="settings-grid">
          <SliderRow
            description="Roundness of the panel corners"
            format={pixels}
            label="Corner Radius"
            max={40}
            min={8}
            onChange={(cornerRadius) => onChange({ cornerRadius })}
            value={appearance.cornerRadius}
          />
          <ToggleRow
            checked={appearance.animations}
            description="Springs, reveal and elastic glass"
            label="Animations"
            onClick={() => onChange({ animations: !appearance.animations })}
          />
        </div>
      </section>

      <section aria-labelledby="window-glass-heading" className="settings-section">
        <h2 id="window-glass-heading">Window Glass</h2>
        <div className="settings-grid">
          <PresetRow
            activeId={matchingPreset(GLASS_PRESETS, appearance)?.id ?? null}
            label="Glass Template"
            onPick={(values) => onChange(values)}
            presets={GLASS_PRESETS}
          />
          <ChoiceRow<GlassSource>
            description={sourceHint}
            label="Glass Source"
            onChange={(glassSource) => onChange({ glassSource })}
            options={[
              { value: 'live', label: 'Live', disabled: !glassInfo.liveAvailable },
              { value: 'snapshot', label: 'Snapshot' },
            ]}
            value={glassInfo.liveAvailable ? appearance.glassSource : 'snapshot'}
          />
          <SliderRow
            description="How bright white on the desktop looks through the glass; lower is darker glass"
            label="Whites"
            max={255}
            min={MIN_POINT_GAP}
            onChange={(whitePoint) =>
              onChange({ whitePoint, blackPoint: Math.min(appearance.blackPoint, whitePoint - MIN_POINT_GAP) })
            }
            value={appearance.whitePoint}
          />
          <SliderRow
            description="How bright black on the desktop looks through the glass; higher is more haze"
            label="Blacks"
            max={255 - MIN_POINT_GAP}
            min={0}
            onChange={(blackPoint) =>
              onChange({ blackPoint, whitePoint: Math.max(appearance.whitePoint, blackPoint + MIN_POINT_GAP) })
            }
            value={appearance.blackPoint}
          />
          <SliderRow
            description={
              liveFixed
                ? "0 shows the desktop sharp; Windows' blur fades in and is full from 12 px"
                : live && glassInfo.filtered
                  ? 'Gaussian blur radius, like CSS blur(); 0 is perfectly clear'
                  : 'Frost of the desktop snapshot; 0 shows it sharp'
            }
            format={pixels}
            label="Backdrop Blur"
            max={BACKDROP_BLUR_MAX}
            min={0}
            onChange={(backdropBlur) => onChange({ backdropBlur })}
            value={appearance.backdropBlur}
          />
          <SliderRow
            description={liveFixed ? 'Set by Windows in live mode' : 'Colour strength of the backdrop'}
            disabled={liveFixed}
            format={percent}
            label="Backdrop Saturation"
            max={250}
            min={50}
            onChange={(backdropSaturation) => onChange({ backdropSaturation })}
            value={appearance.backdropSaturation}
          />
        </div>
      </section>

      <section aria-labelledby="edges-text-heading" className="settings-section">
        <h2 id="edges-text-heading">Edges &amp; Text</h2>
        <div className="settings-grid">
          <SliderRow
            description="Light catching the top-left and bottom-right corners"
            format={percent}
            label="Rim Light"
            max={100}
            min={0}
            onChange={(rimLight) => onChange({ rimLight })}
            value={appearance.rimLight}
          />
          <SliderRow
            description="Top sheen, top light line and a brighter outline"
            format={percent}
            label="Edge Highlight"
            max={100}
            min={0}
            onChange={(edgeHighlight) => onChange({ edgeHighlight })}
            value={appearance.edgeHighlight}
          />
          <ChoiceRow<TextTone>
            description={
              appearance.textTone === 'auto' ? `Auto picks ${autoTone} text for this glass` : 'Text and control colour'
            }
            label="Text"
            onChange={(textTone) => onChange({ textTone })}
            options={[
              { value: 'auto', label: 'Auto' },
              { value: 'light', label: 'White' },
              { value: 'dark', label: 'Black' },
            ]}
            value={appearance.textTone}
          />
          <SliderRow
            description="Soft glow behind the text over bright or busy windows"
            format={percent}
            label="Text Halo"
            max={100}
            min={0}
            onChange={(textHalo) => onChange({ textHalo })}
            value={appearance.textHalo}
          />
          <SliderRow
            description="Opacity of times, sources and hints"
            format={percent}
            label="Secondary Text"
            max={100}
            min={30}
            onChange={(secondaryTextOpacity) => onChange({ secondaryTextOpacity })}
            value={appearance.secondaryTextOpacity}
          />
        </div>
      </section>

      <section aria-labelledby="liquid-heading" className="settings-section">
        <h2 id="liquid-heading">Liquid Glass</h2>
        <LiquidPreview />
        <div className="settings-grid">
          <ToggleRow
            checked={liquid}
            description="Refracting edges on the search bar, filters and toasts"
            label="Liquid Effect"
            onClick={() => onChange({ liquidEnabled: !liquid })}
          />
          <PresetRow
            activeId={matchingPreset(LIQUID_PRESETS, appearance)?.id ?? null}
            disabled={!liquid}
            label="Liquid Template"
            onPick={(values) => onChange(values)}
            presets={LIQUID_PRESETS}
          />
          <ChoiceRow<LiquidMode>
            description="Shape of the bend at the edges"
            label="Refraction Mode"
            onChange={(liquidMode) => onChange({ liquidMode })}
            options={[
              { value: 'standard', label: 'Standard', disabled: !liquid },
              { value: 'polar', label: 'Polar', disabled: !liquid },
              { value: 'prominent', label: 'Prominent', disabled: !liquid },
              { value: 'shader', label: 'Shader', disabled: !liquid },
            ]}
            value={appearance.liquidMode}
          />
          <SliderRow
            description="Strength of the edge refraction"
            disabled={!liquid}
            label="Displacement"
            max={150}
            min={0}
            onChange={(displacementScale) => onChange({ displacementScale })}
            value={appearance.displacementScale}
          />
          <SliderRow
            description={
              glassInfo.mode === 'live'
                ? 'Needs Snapshot glass: over live glass the colour split turns grey, so it is off'
                : 'Colour fringing along the bent edge'
            }
            disabled={!liquid || glassInfo.mode === 'live'}
            format={decimal(1)}
            label="Chromatic Aberration"
            max={10}
            min={0}
            onChange={(aberrationIntensity) => onChange({ aberrationIntensity })}
            step={0.1}
            value={appearance.aberrationIntensity}
          />
          <SliderRow
            description="How far the glass stretches towards the pointer"
            disabled={!liquid || !appearance.animations}
            format={decimal(2)}
            label="Elasticity"
            max={0.5}
            min={0}
            onChange={(elasticity) => onChange({ elasticity })}
            step={0.01}
            value={appearance.elasticity}
          />
          <SliderRow
            description="Blur inside the liquid controls"
            format={decimal(2)}
            label="Frost"
            max={1}
            min={0}
            onChange={(frost) => onChange({ frost })}
            step={0.01}
            value={appearance.frost}
          />
          <SliderRow
            description="Colour strength seen through the controls"
            format={percent}
            label="Glass Saturation"
            max={250}
            min={50}
            onChange={(liquidSaturation) => onChange({ liquidSaturation })}
            value={appearance.liquidSaturation}
          />
          <SliderRow
            description="Darkens the controls; calmer glass over bright content"
            format={percent}
            label="Shade"
            max={50}
            min={0}
            onChange={(liquidShade) => onChange({ liquidShade })}
            value={appearance.liquidShade}
          />
        </div>
        <button className="ghost-button section-reset" onClick={onReset} type="button">
          <ArrowCounterClockwise size={14} weight="bold" />
          Reset Appearance
        </button>
      </section>
    </>
  )
}

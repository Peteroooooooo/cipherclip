import { MagnifyingGlass, PushPin } from '@phosphor-icons/react'
import { LiquidGlass } from '../../shared/ui/liquid/LiquidGlass'

// Stand-in clips that drift under the sample glass, so refraction, frost and saturation have
// something to act on (in live mode the real search bar floats over empty glass).
const SAMPLE_ROWS = [
  { tone: 'accent', title: 'Quarterly report draft', meta: 'Word · 2m ago' },
  { tone: 'success', title: 'git push -u origin main', meta: 'Terminal · 5m ago' },
  { tone: 'warning', title: 'Meeting moved to 3:30 PM', meta: 'Mail · 12m ago' },
  { tone: 'danger', title: 'https://example.com/design', meta: 'Chrome · 20m ago' },
  { tone: 'accent', title: '复制的中文段落示例', meta: 'Notes · 1h ago' },
] as const

function SampleRows() {
  return (
    <div className="liquid-preview-rows">
      {SAMPLE_ROWS.map((row) => (
        <div className="liquid-preview-row" key={row.title}>
          <span className={`liquid-preview-dot is-${row.tone}`} />
          <span className="liquid-preview-text">
            <strong>{row.title}</strong>
            <span>{row.meta}</span>
          </span>
        </div>
      ))}
    </div>
  )
}

/** Live sample of the liquid glass, rendered with the unsaved settings. */
export function LiquidPreview() {
  // A fragment, not a wrapper: the stage is sticky within the Liquid Glass section, so it stays
  // in view while the sliders below it are dragged.
  return (
    <>
      <p className="liquid-preview-hint">Preview · move the pointer near the glass to feel the elasticity</p>
      <div aria-hidden="true" className="liquid-preview-stage" data-testid="liquid-preview">
        <div className="liquid-preview-track">
          <SampleRows />
          <SampleRows />
        </div>
        <div className="liquid-preview-glass">
          <LiquidGlass className="liquid-preview-search">
            <MagnifyingGlass size={15} weight="bold" />
            <span>Search clips</span>
          </LiquidGlass>
          <LiquidGlass className="liquid-preview-button" interactive>
            <PushPin size={16} weight="fill" />
          </LiquidGlass>
        </div>
      </div>
    </>
  )
}

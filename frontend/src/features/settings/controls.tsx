import { useId, type CSSProperties } from 'react'
import { motion } from 'motion/react'
import { SPRING_SNAPPY } from '../../shared/ui/motionTokens'

export function Toggle({ checked, label, onClick }: { checked: boolean; label: string; onClick: () => void }) {
  return (
    <button aria-label={label} aria-pressed={checked} className={`toggle ${checked ? 'is-on' : ''}`} onClick={onClick} type="button">
      <motion.span className="toggle-knob" layout transition={SPRING_SNAPPY} />
    </button>
  )
}

export function ToggleRow({
  checked,
  description,
  label,
  onClick,
}: {
  checked: boolean
  description: string
  label: string
  onClick: () => void
}) {
  return (
    <div className="field-row">
      <div className="field-label">
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <Toggle checked={checked} label={label} onClick={onClick} />
    </div>
  )
}

/** A labelled range slider whose filled track follows the value. */
export function SliderRow({
  label,
  description,
  value,
  min,
  max,
  step = 1,
  disabled = false,
  format = (next) => String(next),
  onChange,
}: {
  label: string
  description: string
  value: number
  min: number
  max: number
  step?: number
  disabled?: boolean
  format?: (value: number) => string
  onChange: (value: number) => void
}) {
  const id = useId()
  const fill = max === min ? 0 : ((value - min) / (max - min)) * 100
  return (
    <div className={`field-row slider-row ${disabled ? 'is-disabled' : ''}`}>
      <div className="slider-head">
        <label className="field-label" htmlFor={id}>
          <strong>{label}</strong>
          <span>{description}</span>
        </label>
        <output className="slider-value" htmlFor={id}>
          {format(value)}
        </output>
      </div>
      <input
        className="glass-slider"
        disabled={disabled}
        id={id}
        max={max}
        min={min}
        onChange={(event) => onChange(Number(event.target.value))}
        step={step}
        style={{ '--fill': `${fill}%` } as CSSProperties}
        type="range"
        value={value}
      />
    </div>
  )
}

/**
 * Templates for a group of parameters. Picking one fills in every parameter of the group; the
 * row shows "Custom" once the values no longer match any template.
 */
export function PresetRow<T>({
  label,
  presets,
  activeId,
  disabled = false,
  onPick,
}: {
  label: string
  presets: { id: string; label: string; description: string; values: T }[]
  activeId: string | null
  disabled?: boolean
  onPick: (values: T) => void
}) {
  const active = presets.find((preset) => preset.id === activeId)
  return (
    <div className="field-row choice-row preset-row">
      <div className="field-label">
        <strong>{label}</strong>
        <span>{active ? active.description : 'Custom: your own values, edited below'}</span>
      </div>
      <div aria-label={label} className="choice-group" role="radiogroup">
        {presets.map((preset) => (
          <button
            aria-checked={preset.id === activeId}
            className={`choice ${preset.id === activeId ? 'is-selected' : ''}`}
            disabled={disabled}
            key={preset.id}
            onClick={() => onPick(preset.values)}
            role="radio"
            type="button"
          >
            {preset.label}
          </button>
        ))}
        {active ? null : (
          <span aria-checked="true" className="choice is-selected is-custom" role="radio">
            Custom
          </span>
        )}
      </div>
    </div>
  )
}

/** A small segmented control for picking one of a few options. */
export function ChoiceRow<T extends string>({
  label,
  description,
  value,
  options,
  onChange,
}: {
  label: string
  description: string
  value: T
  options: { value: T; label: string; disabled?: boolean }[]
  onChange: (value: T) => void
}) {
  return (
    <div className="field-row choice-row">
      <div className="field-label">
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <div aria-label={label} className="choice-group" role="radiogroup">
        {options.map((option) => (
          <button
            aria-checked={value === option.value}
            className={`choice ${value === option.value ? 'is-selected' : ''}`}
            disabled={option.disabled}
            key={option.value}
            onClick={() => onChange(option.value)}
            role="radio"
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

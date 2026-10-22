import { useId } from 'react'

/** Squircle app mark: a frosted clipboard sheet on a blue-violet gradient. */
export function AppLogo({ size = 22 }: { size?: number }) {
  const id = useId()
  const bg = `${id}-bg`
  const sheet = `${id}-sheet`

  return (
    <svg aria-hidden="true" height={size} viewBox="0 0 64 64" width={size}>
      <defs>
        <linearGradient id={bg} x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#5AC8FA" />
          <stop offset="0.55" stopColor="#0A84FF" />
          <stop offset="1" stopColor="#5E5CE6" />
        </linearGradient>
        <linearGradient id={sheet} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.98" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0.82" />
        </linearGradient>
      </defs>
      <path
        d="M32 2c17.6 0 22.4 0 26.2 3.8S62 14.4 62 32s0 22.4-3.8 26.2S49.6 62 32 62s-22.4 0-26.2-3.8S2 49.6 2 32s0-22.4 3.8-26.2S14.4 2 32 2z"
        fill={`url(#${bg})`}
      />
      <path d="M32 3.5c17 0 21.6 0 25.2 3.3" fill="none" opacity="0.35" stroke="#fff" strokeLinecap="round" strokeWidth="1.5" />
      <rect fill={`url(#${sheet})`} height="34" rx="6" width="28" x="18" y="17" />
      <rect fill="#0A84FF" height="7" opacity="0.9" rx="3.5" width="14" x="25" y="13" />
      <rect fill="#0A84FF" height="3" opacity="0.55" rx="1.5" width="16" x="24" y="29" />
      <rect fill="#0A84FF" height="3" opacity="0.4" rx="1.5" width="12" x="24" y="36" />
      <rect fill="#0A84FF" height="3" opacity="0.28" rx="1.5" width="14" x="24" y="43" />
    </svg>
  )
}

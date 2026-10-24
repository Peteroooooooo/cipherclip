/** The ClipDeck app icon (public/clipdeck-icon.svg, written by scripts/make-icon.py from the master
 * in assets/). As an <img>, its gradient and filter ids cannot clash with the page's. */
export function AppLogo({ size = 22 }: { size?: number }) {
  return <img alt="" aria-hidden="true" draggable={false} height={size} src="./clipdeck-icon.svg" width={size} />
}

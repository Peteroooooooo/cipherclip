import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import App from './App'
import { desktopApi, resetDesktopApiMock } from './app/pywebview'

describe('App shell', () => {
  beforeEach(() => {
    cleanup()
    resetDesktopApiMock()
    vi.restoreAllMocks()
  })

  test('renders quick panel sections and switches to settings', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    // The search bar stays folded into the magnifier until it is asked for.
    expect(screen.queryByRole('textbox', { name: 'Search clipboard history' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Search' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('button', { name: 'Clear' })).toBeInTheDocument()
    const alwaysOnTopButton = screen.getByRole('button', { name: 'Always on top' })
    const recordingButton = screen.getByRole('button', { name: 'Pause recording' })

    expect(alwaysOnTopButton).toHaveAttribute('aria-pressed', 'false')
    expect(alwaysOnTopButton.compareDocumentPosition(recordingButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'General' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Capture' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Shortcuts' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'History & Storage' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Data Management' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Recording' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Close to Tray' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Follow System Theme' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Record Text' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Record Rich Text' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Record Images' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Record Files' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('spinbutton', { name: 'History Limit' })).toHaveValue(25)
    expect(screen.queryByRole('spinbutton', { name: 'Text Clip Limit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('spinbutton', { name: 'Image Clip Limit' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Clear All History' })).toBeInTheDocument()
  })

  test('clears only recent history from the quick panel', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm')

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()
    expect(screen.getByText('Sprint recap: finish tray wiring, validate pywebview bridge, update README.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear' }))

    expect(confirmSpy).not.toHaveBeenCalled()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()
    expect(screen.getByText('Color token note: use warm paper background with rust accent and slate text.')).toBeInTheDocument()
    await vi.waitFor(() => {
      expect(screen.queryByText('Sprint recap: finish tray wiring, validate pywebview bridge, update README.')).not.toBeInTheDocument()
      expect(screen.queryByText('ssh deploy@staging-box')).not.toBeInTheDocument()
    })
  })

  test('shows no toast for copy but surfaces feedback for clearing', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    const [copyButton] = screen.getAllByRole('button', { name: 'Copy' })
    await user.click(copyButton)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear' }))
    expect(await screen.findByRole('status')).toHaveTextContent('已清除未固定记录')
  })

  test('offers undo after deleting a record', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    const initialCount = document.querySelectorAll('[data-record-id]').length

    const [deleteButton] = screen.getAllByRole('button', { name: 'Delete' })
    await user.click(deleteButton)
    await user.click(await screen.findByRole('button', { name: '撤销' }))

    await vi.waitFor(() => {
      expect(document.querySelectorAll('[data-record-id]')).toHaveLength(initialCount)
    })
  })

  test('copy button delegates to the desktop copy action', async () => {
    const user = userEvent.setup()
    const copyRecordSpy = vi.spyOn(desktopApi, 'copyRecord')

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    const [copyButton] = screen.getAllByRole('button', { name: 'Copy' })
    await user.click(copyButton)

    expect(copyRecordSpy).toHaveBeenCalledTimes(1)
  })

  test('does not scroll cards into view while hovering with the mouse', async () => {
    const user = userEvent.setup()
    const scrollIntoViewSpy = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoViewSpy,
    })

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.hover(screen.getByRole('button', { name: 'ssh deploy@staging-box from Windows Terminal' }))

    expect(scrollIntoViewSpy).not.toHaveBeenCalled()
  })

  test('still scrolls the active card into view during keyboard navigation', async () => {
    const user = userEvent.setup()
    const scrollIntoViewSpy = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoViewSpy,
    })

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.keyboard('{ArrowDown}')

    expect(scrollIntoViewSpy).toHaveBeenCalled()
  })

  test('clears all history from settings data management', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    const [clearHistoryButton] = await screen.findAllByRole('button', { name: 'Clear All History' })
    await user.click(clearHistoryButton)
    const [cancelButton] = screen.getAllByRole('button', { name: 'Cancel' })
    await user.click(cancelButton)

    const [emptyState] = await screen.findAllByText('No clips yet. Copy something to get started.')
    expect(emptyState).toBeInTheDocument()
  })

  test('does not clear all history when confirmation is cancelled', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    const [clearHistoryButton] = await screen.findAllByRole('button', { name: 'Clear All History' })
    await user.click(clearHistoryButton)
    const [cancelButton] = screen.getAllByRole('button', { name: 'Cancel' })
    await user.click(cancelButton)

    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()
  })

  test('shows the quick panel and filters records by search query', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Search' }))
    const search = screen.getByRole('textbox', { name: 'Search clipboard history' })
    expect(search).toHaveFocus()
    await user.type(search, 'Windows Terminal')

    const cards = document.querySelectorAll('[data-record-id]')
    expect(cards).toHaveLength(1)
    expect(within(cards[0] as HTMLElement).getByText('ssh deploy@staging-box')).toBeInTheDocument()
  })

  test('typing anywhere opens the search with that text, and Esc clears and folds it', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    const initialCount = document.querySelectorAll('[data-record-id]').length

    await user.keyboard('ssh')
    const search = screen.getByRole('textbox', { name: 'Search clipboard history' })
    expect(search).toHaveValue('ssh')
    expect(search).toHaveFocus()
    await vi.waitFor(() => expect(document.querySelectorAll('[data-record-id]')).toHaveLength(1))

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('textbox', { name: 'Search clipboard history' })).not.toBeInTheDocument()
    await vi.waitFor(() => expect(document.querySelectorAll('[data-record-id]')).toHaveLength(initialCount))
  })

  test('an empty search folds back on blur, one with text stays open', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    const searchButton = screen.getByRole('button', { name: 'Search' })

    await user.click(searchButton)
    await user.type(screen.getByRole('textbox', { name: 'Search clipboard history' }), 'git')
    await user.click(document.querySelector('.panel-scroll')!)
    await new Promise((resolve) => setTimeout(resolve, 200))
    expect(searchButton).toHaveAttribute('aria-expanded', 'true')

    await user.click(screen.getByRole('button', { name: 'Clear search' }))
    await user.click(document.querySelector('.panel-scroll')!)
    await vi.waitFor(() => expect(searchButton).toHaveAttribute('aria-expanded', 'false'))
  })

  test('the window edge glows while searching; pin and recording each get their own cue', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    const glow = document.querySelector('.edge-glow')!
    expect(glow).not.toHaveClass('is-active')

    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(glow).toHaveClass('is-active')
    await user.keyboard('{Escape}')
    expect(glow).not.toHaveClass('is-active')

    // Pinning does not light the window edge (its ripple is checked in a real browser: jsdom has
    // neither canvas nor Element.animate).
    await user.click(screen.getByRole('button', { name: 'Always on top' }))
    expect(glow).not.toHaveClass('is-active')

    await user.click(screen.getByRole('button', { name: 'Pause recording' }))
    expect(document.querySelector('.rec-ripple')).toBeNull()
    await user.click(await screen.findByRole('button', { name: 'Resume recording' }))
    await vi.waitFor(() => expect(document.querySelector('.rec-ripple')).not.toBeNull())
  })

  test('does not autofocus the search box after returning from settings', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Back' }))

    expect(await screen.findByRole('button', { name: 'Search' })).toHaveAttribute('aria-expanded', 'false')
    expect(document.querySelector('.search-box')).not.toHaveFocus()
  })

  test('uses a customized delete shortcut in the quick panel', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    const deleteShortcutInput = screen.getByDisplayValue('Delete')
    await user.clear(deleteShortcutInput)
    await user.type(deleteShortcutInput, 'Backspace')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()
    const initialCards = document.querySelectorAll('[data-record-id]')

    await user.keyboard('{ArrowDown}{Backspace}')

    await vi.waitFor(() => {
      expect(document.querySelectorAll('[data-record-id]')).toHaveLength(initialCards.length - 1)
    })
  })

  test('shows a browse control for storage path selection', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(screen.getByRole('button', { name: 'Browse' })).toBeInTheDocument()
  })

  test('updates the storage path draft after browsing for a new folder', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(screen.getByText('%LOCALAPPDATA%\\ClipDeck\\data')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Browse' }))

    expect(screen.getByText('%LOCALAPPDATA%\\ClipDeck\\selected-data')).toBeInTheDocument()
  })

  test('renders storage path as a stacked preview block with a separate browse action', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    const storagePathBlock = screen.getByTestId('storage-path-value')
    const storagePathStack = screen.getByTestId('storage-path-stack')
    const browseButton = screen.getByRole('button', { name: 'Browse' })

    expect(storagePathBlock).toHaveTextContent('%LOCALAPPDATA%\\ClipDeck\\data')
    expect(storagePathStack).toContainElement(storagePathBlock)
    expect(storagePathStack).toContainElement(browseButton)
    expect(storagePathBlock.compareDocumentPosition(browseButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  test('persists a customized history limit after saving settings', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    const historyLimitInput = screen.getByRole('spinbutton', { name: 'History Limit' })
    await user.clear(historyLimitInput)
    await user.type(historyLimitInput, '12')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(screen.getByRole('spinbutton', { name: 'History Limit' })).toHaveValue(12)
  })

  test('uses a custom vertical stepper for the history limit control', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    const historyLimitInput = screen.getByRole('spinbutton', { name: 'History Limit' })
    expect(historyLimitInput).toHaveValue(25)

    await user.click(screen.getByRole('button', { name: 'Increase history limit' }))

    expect(historyLimitInput).toHaveValue(26)
    expect(screen.getByRole('button', { name: 'Decrease history limit' })).toBeInTheDocument()
  })

  test('previews appearance edits live and reverts them on cancel', async () => {
    const user = userEvent.setup()
    const previewSpy = vi.spyOn(desktopApi, 'previewAppearance')

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    // The Dark Glass template is the default; Auto text picks white on it.
    expect(document.documentElement.dataset.theme).toBe('dark')
    // White 164 and black 13 are one 40.78% tint of grey 31.88.
    expect(document.documentElement.style.getPropertyValue('--tint-alpha')).toBe('0.4078')
    expect(document.documentElement.style.getPropertyValue('--tint-gray')).toBe('31.88')

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByRole('heading', { name: 'Liquid Glass' })).toBeInTheDocument()
    const glassTemplates = screen.getByRole('radiogroup', { name: 'Glass Template' })
    expect(within(glassTemplates).getByRole('radio', { name: 'Dark Glass' })).toHaveAttribute('aria-checked', 'true')
    // Only the two looks that really differ: dark and light.
    expect(within(glassTemplates).getAllByRole('radio')).toHaveLength(2)

    // Every parameter is editable; leaving all templates marks the glass as Custom.
    expect(screen.queryByRole('slider', { name: /Backdrop Brightness/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('slider', { name: /Tint/ })).not.toBeInTheDocument()
    fireEvent.change(screen.getByRole('slider', { name: /Blacks/ }), { target: { value: '40' } })
    fireEvent.change(screen.getByRole('slider', { name: /Text Halo/ }), { target: { value: '45' } })
    await vi.waitFor(() => expect(document.documentElement.style.getPropertyValue('--tint-gray')).toBe('77.86'))
    expect(document.documentElement.style.getPropertyValue('--tint-alpha')).toBe('0.5137')

    // Dragging white below black pushes black down with it.
    fireEvent.change(screen.getByRole('slider', { name: /Whites/ }), { target: { value: '30' } })
    await vi.waitFor(() => expect(screen.getByRole('slider', { name: /Blacks/ })).toHaveValue('26'))
    fireEvent.change(screen.getByRole('slider', { name: /Whites/ }), { target: { value: '164' } })
    fireEvent.change(screen.getByRole('slider', { name: /Blacks/ }), { target: { value: '40' } })
    expect(document.documentElement.style.getPropertyValue('--text-halo')).toContain('rgba(0, 0, 0, 0.270)')
    expect(within(glassTemplates).getByRole('radio', { name: 'Custom' })).toBeInTheDocument()

    // A template fills in every glass parameter, including the ones that used to be hidden.
    await user.click(within(glassTemplates).getByRole('radio', { name: 'Light Glass' }))
    await vi.waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'))
    expect(document.documentElement.style.getPropertyValue('--tint-gray')).toBe('255')
    expect(document.documentElement.style.getPropertyValue('--tint-alpha')).toBe('0.3216')
    expect(screen.getByRole('slider', { name: /Backdrop Blur/ })).toHaveValue('16')
    expect(screen.getByRole('slider', { name: /Backdrop Blur/ })).toHaveAttribute('max', '20')
    expect(screen.queryByRole('slider', { name: /Backdrop Contrast/ })).not.toBeInTheDocument()
    expect(within(glassTemplates).queryByRole('radio', { name: 'Custom' })).not.toBeInTheDocument()

    await user.click(within(glassTemplates).getByRole('radio', { name: 'Dark Glass' }))
    await vi.waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'))

    // The text colour can still be forced.
    await user.click(screen.getByRole('radio', { name: 'Black' }))
    await vi.waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'))

    const radius = screen.getByRole('slider', { name: /Corner Radius/ })
    fireEvent.change(radius, { target: { value: '32' } })
    await vi.waitFor(() => expect(document.documentElement.style.getPropertyValue('--window-radius')).toBe('32px'))
    await vi.waitFor(() => expect(previewSpy).toHaveBeenCalled())

    // Liquid settings are previewed on sample glass inside the settings page itself.
    const preview = screen.getByTestId('liquid-preview')
    expect(preview.querySelectorAll('.liquid.is-liquid')).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: 'Liquid Effect' }))
    await vi.waitFor(() => expect(preview.querySelectorAll('.liquid.is-plain')).toHaveLength(2))

    const [cancelButton] = screen.getAllByRole('button', { name: 'Cancel' })
    await user.click(cancelButton)

    await vi.waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe('dark')
      expect(document.documentElement.style.getPropertyValue('--tint-gray')).toBe('31.88')
      expect(document.documentElement.style.getPropertyValue('--tint-alpha')).toBe('0.4078')
      expect(document.documentElement.style.getPropertyValue('--window-radius')).toBe('24px')
    })
  })

  test('saves appearance settings', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Settings' }))
    await user.click(await screen.findByRole('button', { name: 'Liquid Effect' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    expect(document.querySelector('.search-glass')).toHaveClass('is-plain')
  })

  test('Delete edits the search text instead of deleting the highlighted clip', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    const initialCount = document.querySelectorAll('[data-record-id]').length
    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(screen.getByPlaceholderText('Search clips')).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    await user.keyboard('{Delete}')

    expect(document.querySelectorAll('[data-record-id]')).toHaveLength(initialCount)
  })

  test('Restore Defaults only changes the unsaved shortcut draft', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Settings' }))
    const toggleInput = screen.getByDisplayValue('Alt + Space')
    await user.clear(toggleInput)
    await user.type(toggleInput, 'Ctrl + K')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Settings' }))
    await user.click(await screen.findByRole('button', { name: 'Restore Defaults' }))
    expect(await screen.findByDisplayValue('Alt + Space')).toBeInTheDocument()

    const [cancelButton] = screen.getAllByRole('button', { name: 'Cancel' })
    await user.click(cancelButton)
    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByDisplayValue('Ctrl + K')).toBeInTheDocument()
  })

  test('toggles the always-on-top toolbar pin button', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ClipDeck' })).toBeInTheDocument()

    const alwaysOnTopButton = screen.getByRole('button', { name: 'Always on top' })
    expect(alwaysOnTopButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(alwaysOnTopButton)

    expect(alwaysOnTopButton).toHaveAttribute('aria-pressed', 'true')
  })
})

import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import App from './App'
import { resetDesktopApiMock } from './app/pywebview'

describe('App shell', () => {
  beforeEach(() => {
    cleanup()
    resetDesktopApiMock()
    vi.restoreAllMocks()
  })

  test('renders quick panel sections and switches to settings', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Search clipboard history' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Clear' })).toBeInTheDocument()

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

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()
    expect(screen.getByText('Sprint recap: finish tray wiring, validate pywebview bridge, update README.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear' }))

    expect(confirmSpy).not.toHaveBeenCalled()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()
    expect(screen.getByText('Color token note: use warm paper background with rust accent and slate text.')).toBeInTheDocument()
    expect(screen.queryByText('Sprint recap: finish tray wiring, validate pywebview bridge, update README.')).not.toBeInTheDocument()
    expect(screen.queryByText('ssh deploy@staging-box')).not.toBeInTheDocument()
  })

  test('does not show toast notifications for copy and clear actions', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    const [copyButton] = screen.getAllByRole('button', { name: 'Copy' })
    await user.click(copyButton)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  test('copy button keeps the panel visible for repeated selection', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    const [copyButton] = screen.getAllByRole('button', { name: 'Copy' })
    await user.click(copyButton)

    expect(screen.getByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Search clipboard history' })).toBeInTheDocument()
  })

  test('does not scroll cards into view while hovering with the mouse', async () => {
    const user = userEvent.setup()
    const scrollIntoViewSpy = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoViewSpy,
    })

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.hover(screen.getByRole('button', { name: 'ssh deploy@staging-box from Git Bash' }))

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

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.keyboard('{ArrowDown}')

    expect(scrollIntoViewSpy).toHaveBeenCalled()
  })

  test('clears all history from settings data management', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()
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

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()
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

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()

    const search = screen.getByRole('textbox', { name: 'Search clipboard history' })
    await user.clear(search)
    await user.type(search, 'Git Bash')

    const cards = document.querySelectorAll('[data-record-id]')
    expect(cards).toHaveLength(1)
    expect(within(cards[0] as HTMLElement).getByText('ssh deploy@staging-box')).toBeInTheDocument()
  })

  test('does not autofocus the search box after returning from settings', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Back' }))

    const search = await screen.findByRole('textbox', { name: 'Search clipboard history' })
    expect(search).not.toHaveFocus()
  })

  test('uses a customized delete shortcut in the quick panel', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    const deleteShortcutInput = screen.getByDisplayValue('Delete')
    await user.clear(deleteShortcutInput)
    await user.type(deleteShortcutInput, 'Backspace')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()
    expect(screen.getByText('Build review notes for the quick panel and tray wiring.')).toBeInTheDocument()
    const initialCards = document.querySelectorAll('[data-record-id]')

    await user.keyboard('{ArrowDown}{Backspace}')

    const remainingCards = document.querySelectorAll('[data-record-id]')
    expect(remainingCards).toHaveLength(initialCards.length - 1)
  })

  test('shows a browse control for storage path selection', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(screen.getByRole('button', { name: 'Browse' })).toBeInTheDocument()
  })

  test('updates the storage path draft after browsing for a new folder', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(screen.getByText('%LOCALAPPDATA%\\CipherClip\\data')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Browse' }))

    expect(screen.getByText('%LOCALAPPDATA%\\CipherClip\\selected-data')).toBeInTheDocument()
  })

  test('renders storage path as a stacked preview block with a separate browse action', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    const storagePathBlock = screen.getByTestId('storage-path-value')
    const storagePathStack = screen.getByTestId('storage-path-stack')
    const browseButton = screen.getByRole('button', { name: 'Browse' })

    expect(storagePathBlock).toHaveTextContent('%LOCALAPPDATA%\\CipherClip\\data')
    expect(storagePathStack).toContainElement(storagePathBlock)
    expect(storagePathStack).toContainElement(browseButton)
    expect(storagePathBlock.compareDocumentPosition(browseButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  test('persists a customized history limit after saving settings', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    const historyLimitInput = screen.getByRole('spinbutton', { name: 'History Limit' })
    await user.clear(historyLimitInput)
    await user.type(historyLimitInput, '12')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(screen.getByRole('spinbutton', { name: 'History Limit' })).toHaveValue(12)
  })

  test('uses a custom vertical stepper for the history limit control', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'CipherClip' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))

    const historyLimitInput = screen.getByRole('spinbutton', { name: 'History Limit' })
    expect(historyLimitInput).toHaveValue(25)

    await user.click(screen.getByRole('button', { name: 'Increase history limit' }))

    expect(historyLimitInput).toHaveValue(26)
    expect(screen.getByRole('button', { name: 'Decrease history limit' })).toBeInTheDocument()
  })
})

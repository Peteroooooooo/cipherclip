import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, test, vi } from 'vitest'
import { HistoryCard } from './HistoryCard'

describe('HistoryCard', () => {
  test('calls callbacks for pin and delete actions', async () => {
    const user = userEvent.setup()
    const onActivate = vi.fn()
    const onPinToggle = vi.fn()
    const onDelete = vi.fn()

    render(
      <HistoryCard
        isActive={false}
        isPinned={false}
        onActivate={onActivate}
        onCopy={vi.fn()}
        onDelete={onDelete}
        onPinToggle={onPinToggle}
        record={{
          id: 'rich-1',
          type: 'rich_text',
          summary: 'Meeting summary with bullet formatting',
          detail: 'Meeting summary with bullet formatting',
          meta: 'Rich text · 2.1 KB',
          sourceApp: 'Word',
          sourceGlyph: 'W',
          pinned: false,
          createdAt: '2026-03-11T08:30:00',
          updatedAt: '2026-03-11T08:30:00',
          contentHash: 'hash-rich-1',
          plainText: 'Meeting summary with bullet formatting',
          richText: '<p>Meeting summary with bullet formatting</p>',
          imagePath: null,
          imageWidth: null,
          imageHeight: null,
          filePaths: [],
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Pin' }))
    await user.click(screen.getByRole('button', { name: 'Delete' }))

    expect(onPinToggle).toHaveBeenCalledWith('rich-1')
    expect(onDelete).toHaveBeenCalledWith('rich-1')
  })

  test('renders an image thumbnail when the record contains a saved preview path', () => {
    render(
      <HistoryCard
        isActive={false}
        isPinned={false}
        onActivate={vi.fn()}
        onCopy={vi.fn()}
        onDelete={vi.fn()}
        onPinToggle={vi.fn()}
        record={{
          id: 'image-1',
          type: 'image',
          summary: 'Screenshot capture with 1440 x 900 preview ready to paste.',
          detail: 'Screenshot capture with 1440 x 900 preview ready to paste.',
          meta: 'Image · 1440 x 900',
          sourceApp: 'Snipping Tool',
          sourceGlyph: 'ST',
          pinned: false,
          createdAt: '2026-03-11T08:30:00',
          updatedAt: '2026-03-11T08:30:00',
          contentHash: 'hash-image-1',
          plainText: null,
          richText: null,
          imagePath: 'C:/temp/image.png',
          imageWidth: 1440,
          imageHeight: 900,
          filePaths: [],
        }}
      />,
    )

    expect(screen.getByRole('img', { name: 'Screenshot capture with 1440 x 900 preview ready to paste.' })).toHaveAttribute(
      'src',
      'C:/temp/image.png',
    )
  })

  test('shows the source app icon when there is one, and the glyph if it fails to load', () => {
    const { container } = render(
      <HistoryCard
        isActive={false}
        isPinned={false}
        onActivate={vi.fn()}
        onCopy={vi.fn()}
        onDelete={vi.fn()}
        onPinToggle={vi.fn()}
        record={{
          id: 'text-2',
          type: 'text',
          summary: 'Copied from VS Code',
          detail: 'Copied from VS Code',
          meta: 'Text',
          sourceApp: 'Visual Studio Code',
          sourceGlyph: 'VS',
          sourceIcon: 'file:///C:/data/icons/code.png',
          pinned: false,
          createdAt: '2026-10-22T08:30:00',
          updatedAt: '2026-10-22T08:30:00',
          contentHash: 'hash-text-2',
          plainText: 'Copied from VS Code',
          richText: null,
          imagePath: null,
          imageWidth: null,
          imageHeight: null,
          filePaths: [],
        }}
      />,
    )

    const icon = container.querySelector('.record-app-icon')!
    expect(icon).toHaveAttribute('src', 'file:///C:/data/icons/code.png')
    expect(screen.queryByText('VS')).not.toBeInTheDocument()

    fireEvent.error(icon)
    expect(screen.getByText('VS')).toBeInTheDocument()
  })

  test('renders the source app glyph for non-image records', () => {
    render(
      <HistoryCard
        isActive={false}
        isPinned={false}
        onActivate={vi.fn()}
        onCopy={vi.fn()}
        onDelete={vi.fn()}
        onPinToggle={vi.fn()}
        record={{
          id: 'text-1',
          type: 'text',
          summary: 'Copied terminal output',
          detail: 'Copied terminal output',
          meta: 'Text',
          sourceApp: 'WindowsTerminal',
          sourceGlyph: 'WT',
          pinned: false,
          createdAt: '2026-03-11T08:30:00',
          updatedAt: '2026-03-11T08:30:00',
          contentHash: 'hash-text-1',
          plainText: 'Copied terminal output',
          richText: null,
          imagePath: null,
          imageWidth: null,
          imageHeight: null,
          filePaths: [],
        }}
      />,
    )

    expect(screen.getByText('WT')).toBeInTheDocument()
  })
})

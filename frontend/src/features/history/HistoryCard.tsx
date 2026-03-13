import { useState } from 'react'
import { Copy, Pin, Trash2, Image as ImageIcon, FileText, Type, AlignLeft } from 'lucide-react'
import type { HistoryRecord } from '../../app/types'
import { timeAgo } from '../../shared/utils/timeAgo'

/* ── Type-specific avatar icon mapping ── */
function TypeAvatar({ type, glyph }: { type: HistoryRecord['type']; glyph: string }) {
  const classMap: Record<string, string> = {
    text: 'is-text',
    rich_text: 'is-rich-text',
    image: 'is-image',
    file: 'is-file',
  }

  const iconMap: Record<string, React.ReactNode> = {
    text: <Type size={15} strokeWidth={2.2} />,
    rich_text: <AlignLeft size={15} strokeWidth={2.2} />,
    image: <ImageIcon size={15} strokeWidth={2.2} />,
    file: <FileText size={15} strokeWidth={2.2} />,
  }

  return (
    <span className={`record-avatar ${classMap[type] ?? ''}`} aria-hidden="true">
      {iconMap[type] ?? glyph}
    </span>
  )
}

function PreviewAvatar({ record }: { record: HistoryRecord }) {
  const [imgError, setImgError] = useState(false)

  if (record.type === 'image' && record.imagePath && !imgError) {
    return (
      <img
        alt={record.summary}
        className="record-preview-image"
        height={32}
        src={record.imagePath}
        width={32}
        onError={() => setImgError(true)}
      />
    )
  }

  return <TypeAvatar glyph={record.sourceGlyph} type={record.type} />
}



interface HistoryCardProps {
  record: HistoryRecord
  isActive: boolean
  isPinned: boolean
  onActivate: () => void
  onDelete: (recordId: string) => void
  onPinToggle: (recordId: string) => void
  onCopy: (recordId: string) => void
  onPlainTextPaste?: (recordId: string) => void
  onPrimaryAction?: (recordId: string) => void
}

export function HistoryCard({
  record,
  isActive,
  isPinned,
  onActivate,
  onDelete,
  onPinToggle,
  onCopy,
  onPlainTextPaste,
  onPrimaryAction,
}: HistoryCardProps) {
  return (
    <article
      className={`panel-card ${isPinned ? 'is-pinned' : ''}`}
      data-active={isActive}
      data-record-id={record.id}
    >
      <button
        aria-label={`${record.summary} from ${record.sourceApp}`}
        className="panel-card-main"
        onClick={() => {
          onActivate()
          onPrimaryAction?.(record.id)
        }}
        type="button"
      >
        <PreviewAvatar record={record} />

        <span className="record-copy">
          <span className="record-summary">{record.summary}</span>
          <span className="record-meta">
            <span>{record.sourceApp}</span>
            <span className="meta-dot">·</span>
            <span className="record-time">{timeAgo(record.updatedAt)}</span>
          </span>
        </span>
      </button>

      <div className="card-actions">
        <button
          aria-label="Copy"
          className="action-button"
          onClick={() => onCopy(record.id)}
          title="Copy"
          type="button"
        >
          <Copy size={14} />
        </button>
        {record.type === 'rich_text' && onPlainTextPaste && (
          <button
            aria-label="Paste as plain text"
            className="action-button is-plain-text"
            onClick={() => onPlainTextPaste(record.id)}
            title="纯文本粘贴"
            type="button"
          >
            <Type size={13} />
          </button>
        )}
        <button
          aria-label={record.pinned ? 'Unpin' : 'Pin'}
          className={`action-button is-pin ${record.pinned ? 'is-pinned' : ''}`}
          onClick={() => onPinToggle(record.id)}
          title={record.pinned ? 'Unpin' : 'Pin'}
          type="button"
        >
          <Pin size={14} />
        </button>
        <button
          aria-label="Delete"
          className="action-button is-danger"
          onClick={() => onDelete(record.id)}
          title="Delete"
          type="button"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  )
}

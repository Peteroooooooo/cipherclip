import { X } from 'lucide-react'
import type { ToastMessage } from '../../app/types'

interface ToastHostProps {
  toast: ToastMessage | null
  onAction: () => void
  onDismiss: () => void
}

export function ToastHost({ toast, onAction, onDismiss }: ToastHostProps) {
  if (!toast) {
    return null
  }

  return (
    <div aria-live="polite" className="toast-host" role="status">
      <div className={`toast is-${toast.tone}`}>
        <div className="toast-copy">
          <p className="toast-title">{toast.title}</p>
          <p className="toast-text">{toast.message}</p>
        </div>

        <div className="toast-actions">
          {toast.actionLabel ? (
            <button className="ghost-button" onClick={onAction} type="button">
              {toast.actionLabel}
            </button>
          ) : null}
          <button aria-label="Dismiss" className="icon-button" onClick={onDismiss} type="button">
            <X size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

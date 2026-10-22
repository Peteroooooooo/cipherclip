import { useEffect } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { X } from '@phosphor-icons/react'
import type { ToastMessage } from '../../app/types'
import { LiquidGlass } from './liquid/LiquidGlass'
import { SPRING_SMOOTH } from './motionTokens'

const AUTO_DISMISS_MS = 4000

interface ToastHostProps {
  toast: ToastMessage | null
  onAction: () => void
  onDismiss: () => void
}

export function ToastHost({ toast, onAction, onDismiss }: ToastHostProps) {
  const toastId = toast?.id

  useEffect(() => {
    if (!toastId) {
      return
    }
    const timer = window.setTimeout(onDismiss, AUTO_DISMISS_MS)
    return () => window.clearTimeout(timer)
  }, [toastId, onDismiss])

  return (
    <div aria-live="polite" className="toast-host">
      {/* "wait": the old toast leaves before the next arrives, so two messages never overlap. */}
      <AnimatePresence mode="wait">
        {toast ? (
          // Opacity + translate only: scaling a backdrop-filtered layer forces a re-blur every frame.
          <motion.div
            animate={{ opacity: 1, y: 0, transition: SPRING_SMOOTH }}
            className="toast-slot"
            exit={{ opacity: 0, y: 6, transition: { duration: 0.12, ease: 'easeOut' } }}
            initial={{ opacity: 0, y: 14 }}
            key={toast.id}
            role="status"
          >
            {/* Floats over the list, so its liquid edge bends the rows passing underneath. */}
            <LiquidGlass className={`toast is-${toast.tone}`} cornerRadius={22}>
              <span className="toast-dot" aria-hidden="true" />
              <div className="toast-copy">
                <p className="toast-title">{toast.title}</p>
                <p className="toast-text">{toast.message}</p>
              </div>
              {toast.actionLabel ? (
                <button className="toast-action" onClick={onAction} type="button">
                  {toast.actionLabel}
                </button>
              ) : null}
              <button aria-label="Dismiss" className="toast-close" onClick={onDismiss} type="button">
                <X size={14} weight="bold" />
              </button>
            </LiquidGlass>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}

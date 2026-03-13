/**
 * Format a timestamp string into a human-readable relative time.
 * e.g. "刚才", "3 分钟前", "2 小时前", "昨天", "3 天前"
 */
export function timeAgo(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHour < 24) return `${diffHour}h ago`
  if (diffDay === 1) return 'Yesterday'
  if (diffDay < 30) return `${diffDay}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

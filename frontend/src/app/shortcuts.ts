type KeyboardEventLike = Pick<KeyboardEvent, 'key' | 'altKey' | 'ctrlKey' | 'metaKey' | 'shiftKey'>

function normalizeKey(value: string) {
  const trimmed = value.trim().toLowerCase()
  if (trimmed === ' ') {
    return 'space'
  }
  if (trimmed === 'esc') {
    return 'escape'
  }
  if (trimmed === 'return') {
    return 'enter'
  }
  if (trimmed === 'spacebar') {
    return 'space'
  }
  return trimmed
}

export function matchesShortcut(event: KeyboardEventLike, binding: string) {
  const tokens = binding
    .split('+')
    .map((token) => normalizeKey(token))
    .filter(Boolean)

  if (!tokens.length) {
    return false
  }

  let expectsAlt = false
  let expectsCtrl = false
  let expectsMeta = false
  let expectsShift = false
  let targetKey: string | null = null

  for (const token of tokens) {
    if (token === 'alt') {
      expectsAlt = true
      continue
    }
    if (token === 'ctrl' || token === 'control') {
      expectsCtrl = true
      continue
    }
    if (token === 'meta' || token === 'win') {
      expectsMeta = true
      continue
    }
    if (token === 'shift') {
      expectsShift = true
      continue
    }
    targetKey = token
  }

  if (!targetKey) {
    return false
  }

  return (
    normalizeKey(event.key) === targetKey &&
    event.altKey === expectsAlt &&
    event.ctrlKey === expectsCtrl &&
    event.metaKey === expectsMeta &&
    event.shiftKey === expectsShift
  )
}

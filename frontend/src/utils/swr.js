import { session } from '@/data/session'

function fullKey(key) {
  return `onechat:swr:${session.user.name}:${key}`
}

export function recall(key) {
  try {
    const value = sessionStorage.getItem(fullKey(key))
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

export function remember(key, value) {
  try {
    sessionStorage.setItem(fullKey(key), JSON.stringify(value))
  } catch {
    return
  }
}

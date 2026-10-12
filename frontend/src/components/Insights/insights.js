import { dayjs } from 'frappe-ui'
import { translate as __ } from '@/translation'

export function waitTime(seconds) {
  if (seconds === null || seconds === undefined) return null

  const value = Math.round(Number(seconds) || 0)
  if (value < 60) return __('{0}s').format(value)

  const minutes = Math.round(value / 60)
  if (minutes < 60) return __('{0}m').format(minutes)

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return minutes % 60 ? __('{0}h {1}m').format(hours, minutes % 60) : __('{0}h').format(hours)

  const days = Math.floor(hours / 24)
  return hours % 24 ? __('{0}d {1}h').format(days, hours % 24) : __('{0}d').format(days)
}

export function money(value, currency = 'USD') {
  if (value === null || value === undefined) return '—'
  const amount = Number(value) || 0
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      minimumFractionDigits: amount && Math.abs(amount) < 1 ? 3 : 2,
      maximumFractionDigits: amount && Math.abs(amount) < 1 ? 4 : 2,
    }).format(amount)
  } catch {
    return `${amount.toFixed(2)} ${currency}`
  }
}

export function change(now, before) {
  if (now === null || now === undefined || !before) return null

  return Math.round(((now - before) / before) * 100)
}

export function share(part, whole) {
  return whole ? Math.round((part * 100) / whole) : null
}

export function percentText(value) {
  return value === null || value === undefined ? '—' : `${Math.round(value)}%`
}

export function withLabels(rows, hourly) {
  return (rows || []).map((row) => ({ ...row, label: dayjs(row.at).format(hourly ? 'ddd h A' : 'D MMM') }))
}

export function kpi(title, value, extra = {}) {
  return { title, value: value ?? null, compact: true, ...extra }
}

export function trend(rows, key) {
  const values = (rows || []).map((row) => row[key] || 0)
  return values.length > 1 && values.some(Boolean) ? { data: values, type: 'bar' } : undefined
}

export const SOURCES = {
  Agent: 'Agents',
  Bot: 'Chatbot flows',
  'Auto reply': 'Auto replies',
  'Away message': 'Away messages',
  Notification: 'Notifications',
  Broadcast: 'Broadcasts',
  Other: 'Other',
}

export const OUTCOMES = {
  Completed: 'Finished',
  Waiting: 'Waiting for a reply',
  Running: 'Running',
  Stopped: 'Stopped or taken over',
  Expired: 'No reply',
  Failed: 'Failed',
}

export const DAYS = {
  Mon: 'Mon',
  Tue: 'Tue',
  Wed: 'Wed',
  Thu: 'Thu',
  Fri: 'Fri',
  Sat: 'Sat',
  Sun: 'Sun',
}

export const BANDS = ['Under 5 min', '5–15 min', '15–60 min', '1–4 hours', '4–24 hours', 'Over a day']

export const CONTENT_TYPES = {
  text: 'Text',
  image: 'Photo',
  video: 'Video',
  audio: 'Voice',
  document: 'Document',
  sticker: 'Sticker',
  location: 'Location',
  contacts: 'Contact card',
  contact: 'Contact card',
  button: 'Button tap',
  interactive: 'Menu choice',
  flow: 'Form response',
  order: 'Order',
  reaction: 'Reaction',
}

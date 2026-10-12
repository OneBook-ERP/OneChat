import { dayjs } from 'frappe-ui'
import { translate as __ } from '@/translation'

export function timeAgo(value) {
  if (!value) return ''

  return dayjs(value).fromNow()
}

export function shortTime(value) {
  if (!value) return ''

  const date = dayjs(value)
  const now = dayjs()

  if (date.isSame(now, 'day')) return date.format('h:mm a')
  if (date.isSame(now.subtract(1, 'day'), 'day')) return __('Yesterday')
  if (date.isAfter(now.subtract(6, 'day'))) return date.format('ddd')

  return date.format('D MMM YY')
}

export function dayLabel(value) {
  const date = dayjs(value)
  const now = dayjs()

  if (date.isSame(now, 'day')) return __('Today')
  if (date.isSame(now.subtract(1, 'day'), 'day')) return __('Yesterday')

  return date.format(date.isSame(now, 'year') ? 'dddd, D MMMM' : 'D MMMM YYYY')
}

export function clock(value) {
  return value ? dayjs(value).format('h:mm a') : ''
}

export function formatDate(value) {
  return value ? dayjs(value).format('D MMM YYYY') : ''
}

export function formatDateTime(value) {
  return value ? dayjs(value).format('D MMM YYYY, h:mm a') : ''
}

export function formatNumber(value) {
  return new Intl.NumberFormat().format(Number(value) || 0)
}

export function countLabel(value) {
  const count = Number(value) || 0

  return count > 99 ? '99+' : String(count)
}

export function formatMoney(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(Number(value) || 0)
}

export function plainText(html) {
  return String(html || '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function errorMessage(error) {
  const text = error?.messages?.[0] || error?.message || ''

  return plainText(text) || __('Something went wrong. Please try again.')
}

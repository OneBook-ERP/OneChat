import { translate as __ } from '@/translation'

export const MEDIA_ICONS = {
  image: 'lucide-image',
  video: 'lucide-film',
  audio: 'lucide-audio-lines',
  document: 'lucide-file-text',
}

export function mediaTabs() {
  return [
    { label: __('All'), value: 'all' },
    { label: __('Images'), value: 'image' },
    { label: __('Videos'), value: 'video' },
    { label: __('Audio'), value: 'audio' },
    { label: __('Documents'), value: 'document' },
  ]
}

export function mediaTypeLabel(value) {
  return { image: __('Image'), video: __('Video'), audio: __('Audio'), document: __('Document') }[value] || ''
}

export function fileSize(bytes) {
  const value = Number(bytes) || 0
  if (!value) return ''
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  if (value >= 1024) return `${Math.round(value / 1024)} KB`

  return `${value} B`
}

export function fileName(url) {
  const path = String(url || '').split('?')[0]

  return decodeURIComponent(path.slice(path.lastIndexOf('/') + 1))
}

export function extension(url) {
  const name = fileName(url)
  const dot = name.lastIndexOf('.')

  return dot > 0 ? name.slice(dot + 1).toUpperCase() : ''
}

export function titleFromFile(name) {
  const dot = name.lastIndexOf('.')
  const base = dot > 0 ? name.slice(0, dot) : name

  return base.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim() || name
}

export function absoluteUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//.test(url)) return url

  return window.location.origin + url
}

export function splitTags(value) {
  return String(value || '')
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)
}

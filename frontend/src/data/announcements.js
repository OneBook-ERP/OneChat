import { computed, reactive } from 'vue'
import { call } from 'frappe-ui'
import { session } from '@/data/session'

const DISMISSED_KEY = 'onechat-dismissed-announcements'
const TYPES = ['card', 'image', 'video', 'html']

export const announcements = reactive({
  items: [],
  dismissed: readDismissed(),
  loaded: false,
})

function storageKey() {
  return `${DISMISSED_KEY}:${session.user.name}`
}

function readDismissed() {
  try {
    return JSON.parse(localStorage.getItem(storageKey()) || '[]')
  } catch {
    return []
  }
}

function writeDismissed() {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(announcements.dismissed.slice(-200)))
  } catch {
    return
  }
}

function live(item, now = Date.now()) {
  if (!item?.id || !TYPES.includes(item.type || 'card')) return false
  if (!item.title && !item.media?.src && !item.html) return false
  if (item.starts_at && new Date(item.starts_at).getTime() > now) return false
  if (item.ends_at && new Date(item.ends_at).getTime() < now) return false
  return true
}

const API = 'onechat.workspace.announcements.'

async function fetchAnnouncements() {
  return call(`${API}announcements`)
}

export function embedOf(src) {
  if (!src) return null
  const youtube = src.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{11})/)
  if (youtube) {
    return {
      provider: 'youtube',
      thumb: `https://i.ytimg.com/vi/${youtube[1]}/hqdefault.jpg`,
      url: (autoplay) => `https://www.youtube-nocookie.com/embed/${youtube[1]}?rel=0&playsinline=1${autoplay ? '&autoplay=1' : ''}`,
    }
  }
  const vimeo = src.match(/vimeo\.com\/(?:video\/)?(\d+)/)
  if (vimeo) {
    return {
      provider: 'vimeo',
      thumb: null,
      url: (autoplay) => `https://player.vimeo.com/video/${vimeo[1]}${autoplay ? '?autoplay=1' : ''}`,
    }
  }
  return null
}

export function htmlDocument(html) {
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><base target="_blank"><style>html,body{margin:0;overflow:hidden}img,video{max-width:100%}</style></head><body>${
    html || ''
  }</body></html>`
}

export const visibleAnnouncements = computed(() =>
  announcements.items.filter((item) => live(item) && !(item.dismissible !== false && announcements.dismissed.includes(item.id))),
)

export async function loadAnnouncements() {
  try {
    const items = await fetchAnnouncements()
    announcements.items = Array.isArray(items) ? items.map((item) => ({ type: 'card', ...item })) : []
  } catch {
    announcements.items = []
  } finally {
    announcements.loaded = true
  }
}

export function dismissAnnouncement(id) {
  if (announcements.dismissed.includes(id)) return
  announcements.dismissed = [...announcements.dismissed, id]
  writeDismissed()
}

import { computed, reactive } from 'vue'
import { call } from 'frappe-ui'
import { session } from '@/data/session'

const DISMISSED_KEY = 'onechat-dismissed-announcements'
const PREVIEW_PARAM = 'preview_announcement'
const TYPES = ['card', 'image', 'video', 'html']

const PREVIEW = [
  {
    id: 'preview-video',
    type: 'video',
    label: 'Sponsored',
    title: 'Sell more on WhatsApp',
    body: 'A two-minute tour of catalogs, carts and payment links.',
    media: { src: 'https://www.youtube.com/watch?v=aqz-KE-bpKQ' },
    action: { label: 'Learn more', url: 'https://onebook.app' },
  },
  {
    id: 'preview-image',
    type: 'image',
    label: 'Ad',
    title: 'Festive offer: 20% off annual plans',
    media: { src: 'https://picsum.photos/seed/onechat/800/400', aspect: '2/1' },
    action: { label: 'Claim offer', url: 'https://onebook.app' },
  },
  {
    id: 'preview-html',
    type: 'html',
    title: 'Live HTML banner',
    height: 120,
    expanded_height: 360,
    html: '<style>body{margin:0;font:600 15px system-ui;display:grid;place-items:center;height:100vh;color:#fff;background:linear-gradient(135deg,#1f8a5b,#2563eb)}small{display:block;font-weight:400;opacity:.85}</style><div style="text-align:center">New: Customer 360<small>Every order, chat and note in one place</small></div>',
  },
  {
    id: 'preview-card',
    type: 'card',
    theme: 'warning',
    title: 'Scheduled maintenance',
    body: 'OneChat will be unavailable on Sunday from 2:00 to 2:30 am.',
  },
]

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

function previewing() {
  try {
    return new URLSearchParams(window.location.search).has(PREVIEW_PARAM)
  } catch {
    return false
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
    const items = previewing() ? PREVIEW : await fetchAnnouncements()
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

import { reactive, watch } from 'vue'
import { call } from 'frappe-ui'
import { session } from '@/data/session'
import { translate as __ } from '@/translation'

const METHOD = 'onechat.workspace.notifications.'
const CLAIM_PREFIX = 'onechat-alerted-'
const CLAIM_TTL = 60000

export const TONES = [
  { value: 'chime', label: 'Chime' },
  { value: 'pop', label: 'Pop' },
  { value: 'ding', label: 'Ding' },
  { value: 'soft', label: 'Soft' },
]

export const EVENTS = [
  {
    key: 'new_chat',
    label: 'New chats in my inbox',
    description: 'A customer starts or reopens a chat that is unassigned or assigned to you',
  },
  { key: 'my_messages', label: 'Messages in my chats', description: 'New messages in chats assigned to you' },
  { key: 'mentions', label: '@mentions', description: 'A teammate mentions you in an internal note' },
  { key: 'assigned', label: 'Chats assigned to me', description: 'Someone or a rule assigns a chat to you' },
  { key: 'reminders', label: 'Reminders and snoozes', description: 'A follow-up is due or a snoozed chat comes back' },
  { key: 'payments', label: 'Payments received', description: 'A customer pays a request in a chat assigned to you or one you sent' },
  { key: 'all_messages', label: 'All new messages', description: 'Every incoming message, whoever it is assigned to', admin: true },
]

const SHAPES = {
  chime: [
    { type: 'sine', freq: 880, at: 0, length: 0.18 },
    { type: 'sine', freq: 1320, at: 0.12, length: 0.3 },
  ],
  pop: [
    { type: 'sine', freq: 520, at: 0, length: 0.08 },
    { type: 'sine', freq: 780, at: 0.06, length: 0.1 },
  ],
  ding: [{ type: 'sine', freq: 1046, at: 0, length: 0.55 }],
  soft: [
    { type: 'triangle', freq: 523, at: 0, length: 0.22 },
    { type: 'triangle', freq: 659, at: 0.16, length: 0.3 },
  ],
}

export const notifications = reactive({
  loaded: false,
  settings: {
    desktop: 1,
    events: { new_chat: 1, my_messages: 1, mentions: 1, assigned: 1, reminders: 1, payments: 1, all_messages: 0 },
    sound: 1,
    tone: 'chime',
    volume: 70,
    quiet: 0,
    quiet_from: '21:00',
    quiet_to: '08:00',
    tab_badge: 1,
    feed_scope: 'onechat',
  },
  permission: supported() ? Notification.permission : 'unsupported',
})

let audio = null

function supported() {
  return typeof window !== 'undefined' && 'Notification' in window
}

function context() {
  const Context = window.AudioContext || window.webkitAudioContext
  if (!Context) return null
  if (!audio) audio = new Context()
  if (audio.state === 'suspended') audio.resume().catch(() => {})
  return audio
}

function unlockAudio() {
  context()
  window.removeEventListener('pointerdown', unlockAudio)
  window.removeEventListener('keydown', unlockAudio)
}

export async function loadNotificationSettings() {
  try {
    Object.assign(notifications.settings, await call(`${METHOD}get`))
  } catch {
    return
  } finally {
    notifications.loaded = true
  }
}

export async function saveNotificationSettings(patch) {
  const previous = JSON.parse(JSON.stringify(notifications.settings))
  Object.assign(notifications.settings, patch)
  try {
    Object.assign(notifications.settings, await call(`${METHOD}save`, { values: JSON.stringify(notifications.settings) }))
  } catch (error) {
    Object.assign(notifications.settings, previous)
    throw error
  }
}

export async function requestPermission() {
  if (!supported()) return 'unsupported'
  notifications.permission = await Notification.requestPermission()
  return notifications.permission
}

export function playTone(tone = notifications.settings.tone, volume = notifications.settings.volume) {
  const ctx = context()
  if (!ctx) return
  const gain = Math.max(0, Math.min(1, volume / 100)) * 0.35
  const start = ctx.currentTime + 0.01
  for (const note of SHAPES[tone] || SHAPES.chime) {
    const oscillator = ctx.createOscillator()
    const envelope = ctx.createGain()
    oscillator.type = note.type
    oscillator.frequency.value = note.freq
    envelope.gain.setValueAtTime(0.0001, start + note.at)
    envelope.gain.exponentialRampToValueAtTime(Math.max(gain, 0.0002), start + note.at + 0.015)
    envelope.gain.exponentialRampToValueAtTime(0.0001, start + note.at + note.length)
    oscillator.connect(envelope).connect(ctx.destination)
    oscillator.start(start + note.at)
    oscillator.stop(start + note.at + note.length + 0.05)
  }
}

function minutes(value) {
  const [hours, mins] = String(value || '00:00')
    .split(':')
    .map(Number)
  return hours * 60 + mins
}

export function inQuietHours(settings = notifications.settings, date = new Date()) {
  if (!settings.quiet) return false
  const now = date.getHours() * 60 + date.getMinutes()
  const from = minutes(settings.quiet_from)
  const to = minutes(settings.quiet_to)
  if (from === to) return false
  return from < to ? now >= from && now < to : now >= from || now < to
}

function claim(key) {
  try {
    const now = Date.now()
    const seen = Number(localStorage.getItem(CLAIM_PREFIX + key) || 0)
    if (now - seen < CLAIM_TTL) return false
    localStorage.setItem(CLAIM_PREFIX + key, String(now))
    for (let index = localStorage.length - 1; index >= 0; index -= 1) {
      const name = localStorage.key(index)
      if (name?.startsWith(CLAIM_PREFIX) && now - Number(localStorage.getItem(name) || 0) > CLAIM_TTL) localStorage.removeItem(name)
    }
  } catch {
    return true
  }
  return true
}

function icon() {
  return document.querySelector('link[rel="icon"]')?.href || undefined
}

function showDesktop({ key, title, body, onOpen }) {
  if (!supported() || notifications.permission !== 'granted') return
  try {
    const popup = new Notification(title, { body, tag: key, icon: icon(), silent: true })
    popup.onclick = () => {
      window.focus()
      onOpen?.()
      popup.close()
    }
  } catch {
    return
  }
}

export function alertUser({ key, kind, title, body, onOpen, activeHere = false }) {
  const settings = notifications.settings
  if (!notifications.loaded || !settings.events[kind]) return
  if (activeHere && document.visibilityState === 'visible') return
  if (inQuietHours(settings)) return
  if (!claim(key)) return

  if (settings.sound) playTone()
  if (settings.desktop && document.visibilityState !== 'visible') showDesktop({ key, title, body, onOpen })
}

export function sendTest() {
  playTone()
  showDesktop({
    key: `test-${Date.now()}`,
    title: __('OneChat notifications are on'),
    body: __('This is how new messages will appear.'),
  })
}

export function classify(data, me = session.user.name) {
  const contact = data?.contact
  if (!contact) return null
  const message = data.message
  const incoming = message && message.type === 'Incoming' && message.content_type !== 'reaction'
  const mine = contact.assigned_to === me
  const events = notifications.settings.events

  if (data.assigned && mine && data.assigned_by !== me && events.assigned) return 'assigned'
  if (!incoming) return null
  if (data.new_chat && (mine || !contact.assigned_to) && events.new_chat) return 'new_chat'
  if (mine && events.my_messages) return 'my_messages'
  if (session.user.is_admin && events.all_messages) return 'all_messages'
  return null
}

let badgeStarted = false

export function startTabBadge(count) {
  if (badgeStarted) return
  badgeStarted = true

  const apply = () => {
    const value = notifications.settings.tab_badge ? count() : 0
    const base = document.title.replace(/^\(\d+\+?\) /, '')
    const next = value ? `(${value > 99 ? '99+' : value}) ${base}` : base
    if (document.title !== next) document.title = next
  }

  watch([count, () => notifications.settings.tab_badge], apply, { immediate: true })

  const head = document.querySelector('head')
  if (head) new MutationObserver(apply).observe(head, { subtree: true, childList: true, characterData: true })
}

export function startNotifications() {
  window.addEventListener('pointerdown', unlockAudio)
  window.addEventListener('keydown', unlockAudio)
  if (supported()) {
    document.addEventListener('visibilitychange', () => (notifications.permission = Notification.permission))
  }
  loadNotificationSettings()
}

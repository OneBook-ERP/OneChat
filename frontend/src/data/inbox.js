import { computed, reactive } from 'vue'
import { FileUploadHandler, call, createResource, dayjs, debounce, toast } from 'frappe-ui'
import { session } from '@/data/session'
import { alertUser, classify, notifications, startNotifications, startTabBadge } from '@/data/notifications'
import { subscribeDoctype, useSocket } from '@/data/socket'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const METHOD = 'onechat.inbox.conversations.'
const PAGE = 30

const CHANNEL_KEY = 'onechat:inbox-channel'

export const STATUSES = {
  open: 'Open',
  pending: 'Pending',
  resolved: 'Resolved',
}

const LABELS = {
  image: 'Photo',
  video: 'Video',
  audio: 'Voice message',
  document: 'Document',
  location: 'Location',
  contact: 'Contact card',
  flow: 'Form response',
  interactive: 'Interactive message',
  product: 'Product',
  product_list: 'Products',
  order: 'Order',
  order_details: 'Payment request',
  order_status: 'Order update',
  story_reply: 'Replied to your story',
  story_mention: 'Mentioned you in their story',
  share: 'Shared a post',
  comment: 'Commented on your post',
  comment_reply: 'Replied to a comment',
}

export const REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🙏']

export const LABEL_COLORS = ['gray', 'blue', 'green', 'amber', 'red', 'violet']

export const LABEL_DOTS = {
  gray: 'bg-surface-gray-5',
  blue: 'bg-surface-blue-7',
  green: 'bg-surface-green-7',
  amber: 'bg-surface-amber-7',
  red: 'bg-surface-red-7',
  violet: 'bg-surface-violet-7',
}

function savedChannel() {
  try {
    return localStorage.getItem(CHANNEL_KEY) || null
  } catch {
    return null
  }
}

export const inbox = reactive({
  view: 'all',
  link: null,
  status: null,
  label: null,
  channel: savedChannel(),
  focus: null,
  search: '',
  rows: [],
  loading: false,
  loaded: false,
  error: '',
  connected: false,
  hasMore: false,
  active: null,
  threads: {},
  details: {},
  hiddenNumbers: [],
  hiddenTeams: [],
})

export const counts = createResource({
  url: 'onechat.inbox.conversations.counts',
  makeParams: () => ({ channel: inbox.channel || null }),
  cache: ['onechat-inbox-counts', session.user.name],
  onSuccess: (data) => {
    if (inbox.channel && (data?.channels || []).length <= 1) setChannel(null)
  },
  initialData: { unread: 0, mine: 0, mine_unread: 0, open: 0, pending: 0 },
})

export const agents = createResource({
  url: 'onechat.inbox.conversations.agents',
  cache: 'onechat-inbox-agents',
})

export function agentOf(user) {
  return (agents.data || []).find((row) => row.name === user) || null
}

export function agentName(user) {
  return agentOf(user)?.full_name || user
}

export const quickReplies = createResource({
  url: 'onechat.inbox.conversations.quick_replies',
  cache: 'onechat-quick-replies',
  initialData: [],
})

export const labels = createResource({
  url: 'onechat.inbox.conversations.labels',
  cache: 'onechat-labels',
  initialData: [],
  auto: session.user.name !== 'Guest',
})

export function labelMeta(name) {
  return (labels.data || []).find((row) => row.name === name) || { name, label_name: name, color: 'gray' }
}

export const unreadTotal = computed(() => counts.data?.unread || 0)

export const inboxCounts = computed(() => ({
  Unread: counts.data?.unread || 0,
  'Assigned to me': counts.data?.mine_unread || 0,
  Open: counts.data?.open || 0,
  Pending: counts.data?.pending || 0,
  Overdue: counts.data?.overdue || 0,
  'Follow-ups': counts.data?.followups || 0,
  Snoozed: counts.data?.snoozed || 0,
}))

let request = 0
let sequence = 0
let started = false

const refreshCounts = debounce(() => counts.reload(), 400)

function stamp(row) {
  return row.last_message_at || ''
}

function sortRows() {
  inbox.rows.sort((a, b) => (stamp(a) < stamp(b) ? 1 : stamp(a) > stamp(b) ? -1 : 0))
}

export function isOverdue(row) {
  return Boolean(row?.sla_due_at) && !dayjs(row.sla_due_at).isAfter(dayjs())
}

export function isSnoozed(row) {
  return Boolean(row?.snoozed_until) && dayjs(row.snoozed_until).isAfter(dayjs())
}

function snoozeFits(row) {
  if (inbox.search || inbox.view === 'followups') return true
  return inbox.view === 'snoozed' ? isSnoozed(row) : !isSnoozed(row)
}

function visible(row) {
  if (!snoozeFits(row)) return false
  if (row.whatsapp_account && inbox.hiddenNumbers.includes(row.whatsapp_account)) return false
  if (row.team && inbox.hiddenTeams.includes(row.team)) return false
  if (inbox.view === 'unread' && !(row.unread_count > 0)) return false
  if (inbox.view === 'overdue' && !isOverdue(row)) return false
  if (inbox.view === 'mine' && row.assigned_to !== session.user.name) return false
  if (inbox.link && !(row.linked || [row.reference_doctype]).includes(inbox.link)) return false
  if (inbox.status && (row.conversation_status || 'Open') !== STATUSES[inbox.status]) return false
  if (inbox.label && !(row.labels || []).includes(inbox.label)) return false
  if (inbox.channel && (row.channel || 'WhatsApp') !== inbox.channel) return false
  if (!inbox.search) return true

  const query = inbox.search.toLowerCase()
  return [row.contact_name, row.mobile_no, row.email, row.instagram_username].some((value) =>
    String(value || '')
      .toLowerCase()
      .includes(query),
  )
}

export function findRow(contact) {
  return inbox.rows.find((row) => row.name === contact) || null
}

function listKey() {
  if (inbox.search) return null
  return `onechat:inbox:${session.user.name}:${[inbox.view, inbox.link, inbox.status, inbox.label, inbox.channel].join('|')}`
}

function readList(key) {
  try {
    const value = key && sessionStorage.getItem(key)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

function writeList(key, rows) {
  try {
    if (key) sessionStorage.setItem(key, JSON.stringify(rows))
  } catch {
    return
  }
}

export async function loadConversations(reset = true) {
  const token = ++request
  const key = reset ? listKey() : null
  inbox.loading = true
  inbox.error = ''

  const cached = readList(key)
  if (cached?.length) {
    inbox.rows = cached
    inbox.loaded = true
  }

  try {
    const rows = await call(`${METHOD}conversations`, {
      view: inbox.view,
      link: inbox.link,
      status: inbox.status,
      label: inbox.label,
      channel: inbox.channel,
      search: inbox.search || null,
      start: reset ? 0 : inbox.rows.length,
      limit: PAGE,
    })
    if (token !== request) return

    if (reset) {
      inbox.rows = rows
      writeList(key, rows)
    } else {
      const known = new Set(inbox.rows.map((row) => row.name))
      inbox.rows.push(...rows.filter((row) => !known.has(row.name)))
    }
    inbox.hasMore = rows.length === PAGE
    inbox.loaded = true
  } catch (error) {
    if (token === request) inbox.error = errorMessage(error)
  } finally {
    if (token === request) inbox.loading = false
  }
}

export function loadMoreConversations() {
  if (inbox.loading || !inbox.hasMore) return
  return loadConversations(false)
}

export function setFilters({ view = 'all', link = null, status = null, label = null, search = inbox.search }) {
  const same = inbox.view === view && inbox.link === link && inbox.status === status && inbox.label === label && inbox.search === search
  if (inbox.loaded && same) return

  inbox.view = view
  inbox.link = link
  inbox.status = status
  inbox.label = label
  inbox.search = search
  inbox.rows = []
  inbox.loaded = false
  return loadConversations()
}

function rememberChannel(channel) {
  try {
    if (channel) localStorage.setItem(CHANNEL_KEY, channel)
    else localStorage.removeItem(CHANNEL_KEY)
  } catch {
    return
  }
}

export function setChannel(channel = null) {
  if (inbox.channel === channel) return
  inbox.channel = channel
  rememberChannel(channel)
  inbox.rows = []
  inbox.loaded = false
  counts.reload()
  return loadConversations()
}

export function isInstagram(contact) {
  return contact?.channel === 'Instagram'
}

export function upsertContact(contact) {
  if (!contact?.name) return

  const row = findRow(contact.name)
  if (row) {
    Object.assign(row, contact)
    if (!snoozeFits(row) && inbox.active !== row.name) inbox.rows = inbox.rows.filter((item) => item.name !== row.name)
  } else if (visible(contact)) inbox.rows.push({ ...contact })

  if (inbox.details[contact.name]) Object.assign(inbox.details[contact.name], contact)
  sortRows()
}

export function ensureThread(contact) {
  if (!inbox.threads[contact]) {
    inbox.threads[contact] = { messages: [], hasMore: false, loading: false, older: false, loaded: false }
  }

  return inbox.threads[contact]
}

export async function loadThread(contact) {
  const state = ensureThread(contact)
  state.loading = true

  try {
    const data = await call(`${METHOD}messages`, { contact })
    const pending = state.messages.filter((message) => message.pending)
    state.messages = [...data.messages, ...pending]
    state.hasMore = data.has_more
    state.loaded = true
  } finally {
    state.loading = false
  }
}

export async function loadOlder(contact) {
  const state = ensureThread(contact)
  if (state.older || !state.hasMore) return

  const oldest = state.messages.find((message) => !message.pending && message.kind !== 'note')
  if (!oldest) return

  state.older = true
  try {
    const data = await call(`${METHOD}messages`, { contact, before: oldest.creation })
    const known = new Set(state.messages.map(itemKey))
    state.messages.unshift(...data.messages.filter((message) => !known.has(itemKey(message))))
    state.hasMore = data.has_more
  } finally {
    state.older = false
  }
}

export async function loadDetails(contact) {
  const data = await call(`${METHOD}conversation`, { contact })
  inbox.details[contact] = data

  const row = findRow(contact)
  if (row) {
    for (const key of Object.keys(row)) {
      if (key in data) row[key] = data[key]
    }
  }

  return data
}

export function itemKey(item) {
  return `${item.kind === 'note' ? 'note' : 'message'}-${item.name}`
}

function insertMessage(state, message) {
  const existing = state.messages.find((row) => itemKey(row) === itemKey(message))
  if (existing) return Object.assign(existing, message)

  const index = state.messages.findIndex((row) => row.pending)
  if (index === -1) state.messages.push(message)
  else state.messages.splice(index, 0, message)
}

function applyReaction(state, reaction) {
  if (!reaction.message) return

  const target = state.messages.find((row) => row.message_id && row.message_id === reaction.reply_to_message_id)
  if (target && !(target.reactions || []).includes(reaction.message)) {
    target.reactions = [...(target.reactions || []), reaction.message]
  }
}

function pageVisible() {
  return document.visibilityState === 'visible'
}

export function addMessage(contact, message) {
  const state = inbox.threads[contact]

  if (message.content_type === 'reaction') {
    if (state) applyReaction(state, message)
    return
  }

  if (state?.loaded) insertMessage(state, message)
  if (message.type === 'Incoming' && inbox.active === contact && pageVisible()) markRead(contact)
}

function touchRow(contact, message) {
  const row = findRow(contact)
  if (!row) return

  Object.assign(row, {
    last_message: previewText(message),
    last_message_at: message.creation,
    last_message_type: 'Outgoing',
  })
  if (row.conversation_status === 'Resolved') {
    upsertContact({ name: contact, conversation_status: 'Open' })
    refreshCounts()
  }
  sortRows()
}

function settle(contact, local, row) {
  const state = ensureThread(contact)
  const index = state.messages.findIndex((message) => message.name === local.name)
  const exists = state.messages.some((message) => message.name === row.name)

  if (index === -1) {
    if (!exists) insertMessage(state, row)
    return
  }

  if (exists) state.messages.splice(index, 1)
  else state.messages.splice(index, 1, row)
}

async function deliver(contact, local) {
  local.status = 'pending'
  local.error = null

  try {
    const row = await call(`${METHOD}send`, {
      contact,
      message: local.payload.message || null,
      attach: local.payload.attach || null,
      content_type: local.payload.content_type || 'text',
      reply_to: local.payload.reply?.name || null,
    })
    settle(contact, local, row)
    touchRow(contact, row)
    return row
  } catch (error) {
    local.status = 'failed'
    local.error = errorMessage(error)
  }
}

export function sendMessage(contact, payload) {
  const state = ensureThread(contact)
  const reply = payload.reply
  const local = reactive({
    name: `pending-${++sequence}`,
    pending: true,
    type: 'Outgoing',
    status: 'pending',
    content_type: payload.content_type || 'text',
    message_type: 'Manual',
    message: payload.message || '',
    attach: payload.attach || null,
    is_reply: reply ? 1 : 0,
    reply: reply ? { name: reply.name, type: reply.type, content_type: reply.content_type, text: previewText(reply) } : null,
    reactions: [],
    owner: session.user.name,
    creation: dayjs().format('YYYY-MM-DD HH:mm:ss.SSS'),
    payload,
  })

  state.messages.push(local)
  return deliver(contact, local)
}

export function retryMessage(contact, message) {
  if (message.pending && message.status === 'failed') return deliver(contact, message)
}

export function discardMessage(contact, message) {
  const state = ensureThread(contact)
  state.messages = state.messages.filter((row) => row.name !== message.name)
}

export async function sendTemplate(contact, template, parameters) {
  const row = await call(`${METHOD}send_template`, {
    contact,
    template,
    parameters: parameters?.length ? JSON.stringify(parameters) : null,
  })

  if (row) {
    insertMessage(ensureThread(contact), row)
    touchRow(contact, row)
  }

  return row
}

export async function react(message, emoji) {
  const before = message.reactions || []
  if (before.includes(emoji)) return

  message.reactions = [...before, emoji]
  try {
    await call(`${METHOD}react`, { message: message.name, emoji })
  } catch (error) {
    message.reactions = before
    throw error
  }
}

export function markRead(contact) {
  const row = findRow(contact)
  const detail = inbox.details[contact]
  if (!((row?.unread_count || 0) > 0 || (detail?.unread_count || 0) > 0)) return

  if (row) row.unread_count = 0
  if (detail) detail.unread_count = 0

  call(`${METHOD}mark_read`, { contact })
    .then(refreshCounts)
    .catch(() => {})
}

export async function assign(contact, user) {
  await call(`${METHOD}assign`, { contact, user: user || null })
  upsertContact({ name: contact, assigned_to: user || null })
  refreshCounts()
}

export function statusOf(contact) {
  return contact?.conversation_status || 'Open'
}

export const resolveRules = createResource({ url: `${METHOD}resolve_rules` })

export async function loadResolveRules() {
  await resolveRules.fetch()
  return (
    resolveRules.data || {
      require_reason: false,
      require_note: false,
      reasons: [],
      when_waiting: 'Allow',
      only_owner: false,
      is_admin: false,
    }
  )
}

export function resolveNeedsDialog(rules, waiting) {
  return (
    rules.require_reason ||
    rules.require_note ||
    (waiting && rules.when_waiting === 'Ask to confirm') ||
    (waiting && rules.when_waiting === 'Block' && rules.is_admin)
  )
}

export async function setStatus(contact, status, extra = {}) {
  const current = inbox.details[contact] || findRow(contact)
  const previous = statusOf(current)

  upsertContact({ name: contact, conversation_status: status })
  try {
    await call(`${METHOD}set_status`, { contact, status, ...extra })
  } catch (error) {
    upsertContact({ name: contact, conversation_status: previous })
    throw error
  } finally {
    refreshCounts()
  }
}

export const composerRequest = reactive({ contact: null, text: '', stamp: 0 })

export function insertIntoComposer(contact, text) {
  Object.assign(composerRequest, { contact, text: String(text || ''), stamp: composerRequest.stamp + 1 })
}

export function fillQuickReply(message, contact) {
  const name = String(contact?.contact_name || contact?.mobile_no || '').trim()
  const values = {
    name,
    first_name: name.split(/\s+/)[0] || '',
    agent: session.user.full_name || session.user.name || '',
  }

  return String(message || '').replace(/\{\{\s*(name|first_name|agent)\s*\}\}/g, (match, key) => values[key])
}

export function setActive(contact) {
  inbox.active = contact || null
}

const ALERT_TITLES = {
  assigned: 'Chat assigned to you',
  new_chat: 'New chat from {0}',
}

function notify(data) {
  const kind = classify(data)
  if (!kind) return
  const contact = data.contact
  const name = contact.contact_name || contact.mobile_no || contact.name
  alertUser({
    key: data.message ? `message-${data.message.name}` : `${kind}-${contact.name}-${contact.assigned_to}`,
    kind,
    title: ALERT_TITLES[kind] ? __(ALERT_TITLES[kind]).format(name) : name,
    body: data.message ? previewText(data.message) : name,
    activeHere: inbox.active === contact.name,
    onOpen: () => openConversation(contact.name),
  })
}

function forget(contact) {
  inbox.rows = inbox.rows.filter((row) => row.name !== contact)
  delete inbox.details[contact]
  delete inbox.threads[contact]
  refreshCounts()
  if (inbox.active !== contact) return
  toast(__('This conversation is now assigned to someone else'), { description: __('You no longer have access to it.') })
  import('@/router').then(({ default: router }) => router.replace({ name: 'Inbox' }))
}

function onInbox(data) {
  if (data?.removed) return forget(data.removed)
  if (!data?.contact) return

  upsertContact(data.contact)
  if (data.message) addMessage(data.contact.name, data.message)
  if (data.message?.type === 'Incoming') followups.version += 1
  refreshCounts()
  notify(data)
}

function placeNote(state, note) {
  const existing = state.messages.find((row) => row.kind === 'note' && row.name === note.name)
  if (existing) return Object.assign(existing, note)

  const oldest = state.messages.find((row) => !row.pending && row.kind !== 'note')
  if (state.hasMore && oldest && note.creation < oldest.creation) return

  let index = state.messages.findIndex((row) => row.pending || row.creation > note.creation)
  if (index === -1) index = state.messages.length
  state.messages.splice(index, 0, note)
}

function applyNote(contact, note, deleted = false) {
  const state = inbox.threads[contact]
  const detail = inbox.details[contact]

  if (deleted) {
    if (state) state.messages = state.messages.filter((row) => !(row.kind === 'note' && row.name === note.name))
    if (detail?.notes) detail.notes = detail.notes.filter((row) => row.name !== note.name)
    return
  }

  if (state?.loaded) placeNote(state, note)
  if (detail) {
    const notes = (detail.notes || []).filter((row) => row.name !== note.name)
    detail.notes = [note, ...notes].sort((a, b) => (a.creation < b.creation ? 1 : -1))
  }
}

export async function saveNote(contact, content, name = null, mentions = []) {
  const note = await call(`${METHOD}save_note`, { contact, content, name, mentions: JSON.stringify(mentions) })
  applyNote(contact, note)
  return note
}

export async function deleteNote(contact, note) {
  await call(`${METHOD}delete_note`, { name: note.name })
  applyNote(contact, note, true)
}

export function canEditNote(note) {
  return note.owner === session.user.name || !!session.user.is_admin
}

async function reveal(contact, kind, name) {
  const state = ensureThread(contact)
  const found = () => state.messages.some((row) => (row.kind === 'note' ? 'note' : 'message') === kind && row.name === name)

  if (!state.loaded) await loadThread(contact)
  while (!found() && state.hasMore) {
    const count = state.messages.length
    await loadOlder(contact)
    if (state.messages.length === count) break
  }

  if (found()) inbox.focus = { contact, kind, name, at: Date.now() }
  return found()
}

export function revealNote(contact, name) {
  return reveal(contact, 'note', name)
}

export function revealMessage(contact, name) {
  return reveal(contact, 'message', name)
}

export function searchThread(contact, query) {
  return call(`${METHOD}search_thread`, { contact, query })
}

function patchLabels(contact, names) {
  for (const row of [findRow(contact), inbox.details[contact]]) {
    if (row) row.labels = names
  }
}

export async function setLabels(contact, names) {
  const current = inbox.details[contact] || findRow(contact)
  const previous = [...(current?.labels || [])]

  patchLabels(contact, names)
  try {
    await call(`${METHOD}set_labels`, { contact, labels: JSON.stringify(names) })
  } catch (error) {
    patchLabels(contact, previous)
    throw error
  }
}

function replaceLabel(from, to) {
  for (const row of [...inbox.rows, ...Object.values(inbox.details)]) {
    if (!row.labels?.includes(from)) continue
    row.labels = to ? row.labels.map((label) => (label === from ? to : label)) : row.labels.filter((label) => label !== from)
  }
}

function onLabels(data) {
  if (data?.renamed) replaceLabel(data.renamed[0], data.renamed[1])
  if (data?.deleted) replaceLabel(data.deleted, null)
  labels.reload()
}

function onNote(data) {
  if (data?.contact && data.note) applyNote(data.contact, data.note, data.deleted)
}

function onStatus(data) {
  const message = inbox.threads[data?.contact]?.messages.find((row) => row.name === data.message)
  if (!message) return

  message.status = data.status
  message.error_message = data.error_message || null
}

function onReconnect() {
  refreshCounts()
  if (!inbox.connected) {
    inbox.connected = true
    return
  }

  if (inbox.loaded) loadConversations()
  if (inbox.active && inbox.threads[inbox.active]?.loaded) loadThread(inbox.active).catch(() => {})
}

function openConversation(contact) {
  import('@/router').then(({ default: router }) => router.push({ name: 'Inbox', params: { contact } }))
}

function onMention({ contact, contact_name, author, text, note }) {
  alertUser({
    key: `mention-${note || contact}-${text}`,
    kind: 'mentions',
    title: __('{0} mentioned you').format(author),
    body: `${contact_name}: ${text}`,
    onOpen: () => openConversation(contact),
  })
  if (!notifications.settings.events.mentions) return
  toast(__('{0} mentioned you').format(author), {
    description: `${contact_name}: ${text}`,
    duration: 10000,
    action: { label: __('Open'), onClick: () => openConversation(contact) },
  })
}

function onPayment({ contact, contact_name, amount, document, text }) {
  alertUser({
    key: `payment-${document}-${amount}`,
    kind: 'payments',
    title: __('Payment received'),
    body: text,
    onOpen: () => openConversation(contact),
  })
  if (!notifications.settings.events.payments) return
  toast.success(__('{0} paid by {1}').format(amount, contact_name), {
    description: __('For {0}').format(document),
    duration: 15000,
    action: { label: __('Open'), onClick: () => openConversation(contact) },
  })
}

const FOLLOWUPS = 'onechat.inbox.followups.'

export const followups = reactive({ version: 0 })

export async function snooze(contact, until) {
  const value = await call(`${FOLLOWUPS}snooze`, { contact, until })
  upsertContact({ name: contact, snoozed_until: value, snoozed_by: session.user.name })
  refreshCounts()
  return value
}

export async function unsnooze(contact) {
  await call(`${FOLLOWUPS}unsnooze`, { contact })
  upsertContact({ name: contact, snoozed_until: null, snoozed_by: null })
  refreshCounts()
}

export function contactReminders(contact) {
  return call(`${FOLLOWUPS}reminders`, { contact })
}

export async function addReminder(contact, { remindAt, onlyIfNoReply = true, note = '' }) {
  const row = await call(`${FOLLOWUPS}add_reminder`, { contact, remind_at: remindAt, only_if_no_reply: onlyIfNoReply ? 1 : 0, note })
  followups.version += 1
  refreshCounts()
  return row
}

export async function cancelReminder(name) {
  const row = await call(`${FOLLOWUPS}cancel_reminder`, { name })
  followups.version += 1
  refreshCounts()
  return row
}

function onAvailability({ availability }) {
  if (!availability || session.user.availability === availability) return
  session.user.availability = availability
  toast(availability === 'Away' ? __('You are now Away') : __('You are now Available'), {
    description:
      availability === 'Away' ? __('Your working hours have ended or you are on leave.') : __('Your working hours have started.'),
  })
}

function onReminder({ contact, contact_name, kind, text }) {
  const title =
    kind === 'snooze'
      ? __('{0} is back').format(contact_name)
      : kind === 'sla'
      ? __('Reply overdue: {0}').format(contact_name)
      : __('Follow up with {0}').format(contact_name)
  alertUser({ key: `reminder-${contact}-${kind}-${text}`, kind: 'reminders', title, body: text, onOpen: () => openConversation(contact) })
  followups.version += 1
  refreshCounts()
  if (!notifications.settings.events.reminders) return
  toast(title, {
    description: text,
    duration: 15000,
    action: { label: __('Open'), onClick: () => openConversation(contact) },
  })
}

export async function bulkUpdate(contacts, action, value = null, extra = {}) {
  const done = await call(`${METHOD}bulk_update`, { contacts: JSON.stringify(contacts), action, value, ...extra })
  await loadConversations(true)
  refreshCounts()
  return done
}

export function startInbox() {
  if (started) return
  started = true

  subscribeDoctype('OneChat Contact')
  const socket = useSocket()
  inbox.connected = socket.connected
  socket.on('onechat_inbox', onInbox)
  socket.on('onechat_message_status', onStatus)
  socket.on('onechat_note', onNote)
  socket.on('onechat_labels', onLabels)
  socket.on('onechat_mention', onMention)
  socket.on('onechat_reminder', onReminder)
  socket.on('onechat_payment', onPayment)
  socket.on('onechat_availability', onAvailability)
  socket.on('connect', onReconnect)

  document.addEventListener('visibilitychange', () => {
    if (pageVisible() && inbox.active) markRead(inbox.active)
  })

  counts.fetch()
  startNotifications()
  startTabBadge(() => unreadTotal.value)
}

export function previewText(message) {
  if (!message) return ''
  if (message.text) return message.text
  if (message.message_type === 'Template') {
    return __('Template: {0}').format(message.template_name || message.template || '')
  }

  const text = plainMessage(message.message)
  if (text) return text

  return LABELS[message.content_type] ? __(LABELS[message.content_type]) : ''
}

export function messageBody(message) {
  if (message?.message_type === 'Template') return message.template_body || message.message || ''
  return message?.message || ''
}

export async function copyMessage(message) {
  try {
    await navigator.clipboard.writeText(plainMessage(messageBody(message)))
    toast.success(__('Copied'))
  } catch {
    toast.error(__('Could not copy the text'))
  }
}

export function contentLabel(type) {
  return LABELS[type] ? __(LABELS[type]) : ''
}

export function plainMessage(value) {
  const text = String(value || '')
  if (!/<[a-z][\s\S]*>/i.test(text)) return text.trim()

  const html = text.replace(/<br\s*\/?>/gi, '\n').replace(/<\/(p|div|li)>/gi, '\n')
  return (new DOMParser().parseFromString(html, 'text/html').body.textContent || '').trim()
}

function escapeHtml(text) {
  const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
  return text.replace(/[&<>"']/g, (char) => entities[char])
}

const EDGE = '(?=[\\s.,!?:;)]|$)'

export function richText(value) {
  return escapeHtml(plainMessage(value))
    .replace(/```([\s\S]+?)```/g, '<code class="rounded-1 bg-surface-gray-3 px-1 font-mono text-sm">$1</code>')
    .replace(new RegExp(`(^|[\\s(])\\*([^*\\n]+)\\*${EDGE}`, 'g'), '$1<strong>$2</strong>')
    .replace(new RegExp(`(^|[\\s(])_([^_\\n]+)_${EDGE}`, 'g'), '$1<em>$2</em>')
    .replace(new RegExp(`(^|[\\s(])~([^~\\n]+)~${EDGE}`, 'g'), '$1<s>$2</s>')
    .replace(
      /(https?:\/\/[^\s<]+[^\s<.,!?:;)])/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">$1</a>',
    )
}

export function contentTypeFor(file) {
  const kind = String(file?.type || '').split('/')[0]
  return ['image', 'video', 'audio'].includes(kind) ? kind : 'document'
}

export function fileName(url) {
  const tail =
    String(url || '')
      .split('?')[0]
      .split('/')
      .pop() || ''

  try {
    return decodeURIComponent(tail)
  } catch {
    return tail
  }
}

export function replyWindowOpen(messages, contact, hasMore, at = Date.now(), hours = 24) {
  const cutoff = dayjs(at).subtract(hours, 'hour')
  const incoming = [...messages].reverse().find((message) => message.kind !== 'note' && message.type === 'Incoming')
  const stamps = [incoming?.creation, contact?.last_message_type === 'Incoming' ? contact.last_message_at : null]

  if (stamps.some((value) => value && dayjs(value).isAfter(cutoff))) return true

  const oldest = messages.find((message) => !message.pending && message.kind !== 'note')
  return !incoming && hasMore && !!oldest && dayjs(oldest.creation).isAfter(cutoff)
}

export function uploadFile(file, { contact, onProgress } = {}) {
  const handler = new FileUploadHandler()
  let cancel = null
  handler.on('progress', ({ uploaded, total }) => onProgress?.(Math.round((uploaded / total) * 100)))

  const promise = new Promise((resolve, reject) => {
    cancel = () => reject(Object.assign(new Error('aborted'), { aborted: true }))
    handler
      .upload(file, {
        upload_endpoint: '/api/method/onechat.whatsapp.message.upload_whatsapp_attachment',
        private: false,
        ...(contact ? { doctype: 'OneChat Contact', docname: contact } : {}),
      })
      .then(resolve)
      .catch((error) => reject(new Error(error?.message || __('The file could not be uploaded.'))))
  })

  promise.abort = () => cancel?.()
  return promise
}

export function deskUrl(doctype, name) {
  return `/app/${doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(name)}`
}

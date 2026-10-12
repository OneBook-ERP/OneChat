import { call } from 'frappe-ui'

const METHOD = 'onechat.inbox.customer.'

export const TIMELINE_KINDS = [
  { value: 'conversation', label: 'Chats', icon: 'lucide-messages-square', tile: 'bg-surface-blue-2 text-ink-blue-7' },
  { value: 'record', label: 'Orders & payments', icon: 'lucide-package', tile: 'bg-surface-green-2 text-ink-green-7' },
  { value: 'note', label: 'Notes', icon: 'lucide-notebook-pen', tile: 'bg-surface-amber-2 text-ink-amber-7' },
  { value: 'campaign', label: 'Campaigns', icon: 'lucide-megaphone', tile: 'bg-surface-violet-2 text-ink-violet-7' },
  { value: 'form', label: 'Forms', icon: 'lucide-clipboard-check', tile: 'bg-surface-cyan-2 text-ink-cyan-7' },
  { value: 'flow', label: 'Chatbot', icon: 'lucide-bot', tile: 'bg-surface-gray-2 text-ink-gray-7' },
  { value: 'link', label: 'Chat links', icon: 'lucide-link', tile: 'bg-surface-gray-2 text-ink-gray-7' },
  { value: 'consent', label: 'Consent', icon: 'lucide-bell-off', tile: 'bg-surface-red-2 text-ink-red-7' },
]

export function kindMeta(kind) {
  return TIMELINE_KINDS.find((row) => row.value === kind) || TIMELINE_KINDS[0]
}

export function customerProfile(contact) {
  return call(`${METHOD}profile`, { contact })
}

export function customerTimeline(contact, { before = null, kinds = null, limit = 30 } = {}) {
  return call(`${METHOD}timeline`, {
    contact,
    before: before || undefined,
    kinds: kinds ? JSON.stringify(kinds) : undefined,
    limit,
  })
}

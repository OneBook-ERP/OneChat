import { onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'

const GO_TO = {
  i: { route: '/inbox' },
  c: { route: '/contacts' },
  m: { route: '/campaigns', admin: true },
  a: { route: '/automation', admin: true },
}

export const SHORTCUTS = [
  { keys: ['mod', 'K'], label: 'Search everything', group: 'Anywhere' },
  { keys: ['mod', 'B'], label: 'Show or hide the sidebar', group: 'Anywhere' },
  { keys: ['mod', '/'], label: 'This list', group: 'Anywhere' },
  { keys: ['mod', 'alt', 'I'], label: 'Inbox', group: 'Go to' },
  { keys: ['mod', 'alt', 'C'], label: 'Contacts', group: 'Go to' },
  { keys: ['mod', 'alt', 'M'], label: 'Campaigns', group: 'Go to', admin: true },
  { keys: ['mod', 'alt', 'A'], label: 'Automation', group: 'Go to', admin: true },
  { keys: ['alt', 'R'], label: 'Resolve or reopen the conversation', group: 'Inbox' },
  { keys: ['alt', '↑'], label: 'Previous conversation', group: 'Inbox' },
  { keys: ['alt', '↓'], label: 'Next conversation', group: 'Inbox' },
]

export function useShortcuts() {
  const router = useRouter()
  const ui = useUI()

  function keyOf(event) {
    if (event.code?.startsWith('Key')) return event.code.slice(3).toLowerCase()
    if (event.code === 'Slash') return '/'

    return (event.key || '').toLowerCase()
  }

  function onKeydown(event) {
    if (!event.metaKey && !event.ctrlKey) return

    const key = keyOf(event)

    if (!event.altKey && !event.shiftKey) {
      if (key === 'k') {
        event.preventDefault()
        ui.searchDialog = !ui.searchDialog
      }

      if (key === 'b') {
        event.preventDefault()
        ui.toggleSidebar()
      }

      if (key === '/') {
        event.preventDefault()
        ui.openSettings('shortcuts')
      }

      return
    }

    const target = event.altKey && !event.shiftKey && GO_TO[key]
    if (!target || (target.admin && !session.user.is_admin)) return

    event.preventDefault()
    router.push(target.route)
  }

  onMounted(() => document.addEventListener('keydown', onKeydown))

  onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
}

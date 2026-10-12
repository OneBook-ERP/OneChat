import { call, useColorScheme } from 'frappe-ui'
import { session } from '@/data/session'

const DESK = { light: 'Light', dark: 'Dark', system: 'Automatic' }

export function useDeskTheme() {
  const { colorScheme, setColorScheme } = useColorScheme()

  function apply(value) {
    if (value && DESK[value] && value !== colorScheme.value) setColorScheme(value)
  }

  async function change(value) {
    if (!DESK[value]) return
    setColorScheme(value)
    session.user.theme = value
    await call('frappe.core.doctype.user.user.switch_theme', { theme: DESK[value] })
  }

  async function pull() {
    try {
      const value = await call('onechat.workspace.session.theme')
      session.user.theme = value
      apply(value)
    } catch {
      return
    }
  }

  return { colorScheme, apply, change, pull }
}

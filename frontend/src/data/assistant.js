import { reactive } from 'vue'
import { call, createResource } from 'frappe-ui'
import { session } from '@/data/session'

const API = 'onechat.assistant.api.'

export const assistantStatus = createResource({
  url: `${API}status`,
  cache: ['onechat-assistant-status', session.user.name],
  auto: session.user.name !== 'Guest',
})

export const assistantThreads = reactive({})

export function assistantThread(contact) {
  if (!assistantThreads[contact]) assistantThreads[contact] = { turns: [], chat: null, loaded: false }
  return assistantThreads[contact]
}

export function askAssistant(contact, question, sessionName, page) {
  return call(`${API}ask`, {
    contact: contact || undefined,
    question,
    session: sessionName || undefined,
    page: page ? JSON.stringify(page) : undefined,
  })
}

export async function loadAssistantHistory(scope, contact) {
  const thread = assistantThread(scope)
  if (thread.loaded || thread.turns.length) return
  thread.loaded = true
  const result = await call(`${API}history`, { contact: contact || undefined })
  if (thread.turns.length) return
  thread.turns = result.turns || []
  thread.chat = result.session || null
}

export function forgetAssistant(contact) {
  return call(`${API}forget`, { contact: contact || undefined })
}

export const assistantLauncher = reactive({ open: false })

export function canChange(access) {
  return Array.isArray(access) && (access.includes('write') || access.includes('create'))
}

export function confirmAssistant(sessionName, approve) {
  return call(`${API}confirm`, { session: sessionName, approve: approve ? 1 : 0 })
}

export function assistantSettings() {
  return call(`${API}get_settings`)
}

export function saveAssistantSettings(values) {
  return call(`${API}save_settings`, { ...values, roles: JSON.stringify(values.roles || []) })
}

export async function signInToSite(integration) {
  const url = await call('onechat.integrations.oauth.agent_start', {
    integration,
    next_path: window.location.pathname + window.location.search,
  })
  window.location.href = url
}

export async function signOutOfSite(integration) {
  await call('onechat.integrations.oauth.agent_sign_out', { integration })
  await assistantStatus.reload()
}

export function toolLabel(name) {
  const base = String(name || '')
    .split('__')
    .pop()
  return base.replace(/_/g, ' ').replace(/^\w/, (char) => char.toUpperCase())
}

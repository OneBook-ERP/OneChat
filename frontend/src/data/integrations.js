import { computed } from 'vue'
import { call, createResource } from 'frappe-ui'
import { session } from '@/data/session'

export const integrations = createResource({
  url: 'onechat.integrations.api.available',
  cache: ['onechat-integrations', session.user.name],
  initialData: { integrations: [], auto_link: true, create_customer_on_win: false },
  auto: session.user.name !== 'Guest',
})

export const activeIntegrations = computed(() => (integrations.data?.integrations || []).filter((row) => row.enabled))

export const hasPurchases = computed(() => activeIntegrations.value.some((row) => row.purchases))

export const hasRecords = computed(() => activeIntegrations.value.some((row) => row.records))

export const linkTypes = computed(() =>
  activeIntegrations.value.flatMap((row) =>
    row.link_doctypes.map((link) => ({ ...link, integration: row.name, deskUrl: row.desk_url || '' })),
  ),
)

export const linkApps = computed(() => activeIntegrations.value.filter((row) => row.link_doctypes?.length))

export function linkMeta(doctype) {
  return (
    linkTypes.value.find((row) => row.doctype === doctype) || {
      doctype,
      label: doctype,
      icon: 'lucide-link',
      theme: 'gray',
    }
  )
}

export function recordUrl(doctype, name) {
  const meta = linkTypes.value.find((row) => row.doctype === doctype)
  const path = meta?.route
    ? meta.route.replace('{name}', encodeURIComponent(name))
    : `/app/${doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(name)}`
  return `${meta?.deskUrl || ''}${path}`
}

export const oauthReturn = (() => {
  try {
    const query = new URLSearchParams(window.location.search)
    if (query.get('settings') !== 'integrations') return null
    return { integration: query.get('integration') || '', connected: query.get('connected') || '', error: query.get('oauth_error') || '' }
  } catch {
    return null
  }
})()

export function startOAuth(integration, values) {
  return call('onechat.integrations.oauth.start', {
    integration,
    url: values.url,
    client_id: values.client_id,
    client_secret: values.client_secret || undefined,
  })
}

export async function signOut(integration) {
  const result = await call('onechat.integrations.remote_setup.sign_out', { integration })
  await integrations.reload()
  return result
}

export function connectionSettings(integration) {
  return call('onechat.integrations.remote_setup.settings', { integration })
}

export async function saveConnection(integration, values) {
  const result = await call('onechat.integrations.remote_setup.save', {
    integration,
    mode: values.mode,
    url: values.url,
    api_key: values.api_key,
    api_secret: values.api_secret,
  })
  await integrations.reload()
  return result
}

export function testConnection(integration) {
  return call('onechat.integrations.remote_setup.test', { integration })
}

export function setupIntegrationRole(integration) {
  return call('onechat.integrations.remote_setup.setup_role', { integration })
}

export function syncConnectionWebhooks(integration) {
  return call('onechat.integrations.remote_setup.sync_webhooks', { integration })
}

export async function setIntegration(name, enabled) {
  integrations.setData(await call('onechat.integrations.api.set_enabled', { name, enabled: enabled ? 1 : 0 }))
}

export async function setCreateCustomerOnWin(enabled) {
  integrations.setData(await call('onechat.integrations.api.set_create_customer_on_win', { enabled: enabled ? 1 : 0 }))
}

export async function setAutoLink(enabled) {
  integrations.setData(await call('onechat.integrations.api.set_auto_link', { enabled: enabled ? 1 : 0 }))
}

export function contactIntegrations(contact) {
  return call('onechat.integrations.api.contact', { contact })
}

export function linkContact(contact, doctype, name, integration) {
  return call('onechat.integrations.api.link', { contact, doctype, name, integration })
}

export function makePrimaryLink(contact, integration) {
  return call('onechat.integrations.api.make_primary', { contact, integration })
}

export function unlinkRecord(contact, doctype, name) {
  return call('onechat.integrations.api.unlink_record', { contact, doctype, name })
}

export function makeMainLink(contact, doctype, name) {
  return call('onechat.integrations.api.make_main', { contact, doctype, name })
}

export function recordChats(doctype, name) {
  return call('onechat.workspace.desk.chats', { doctype, name })
}

export function installCrmButton() {
  return call('onechat.integrations.frappe_crm.install_chat_button')
}

export function autoLinkContact(contact) {
  return call('onechat.integrations.api.auto_link', { contact })
}

export function runAction(contact, action, payload) {
  return call('onechat.integrations.api.run_action', {
    contact,
    integration: action.integration,
    action: action.key,
    payload: payload ? JSON.stringify(payload) : undefined,
  })
}

export function runRowAction(contact, integration, action, row) {
  return call('onechat.integrations.api.run_row_action', {
    contact,
    integration,
    key: action.key,
    doctype: row.doctype,
    name: row.name,
  })
}

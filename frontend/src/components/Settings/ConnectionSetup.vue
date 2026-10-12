<template>
  <ResponsiveDialog v-model:open="open" :title="__('Connect {0}').format(label)" size="2xl">
    <template #default>
      <div v-if="!loaded" class="flex flex-col gap-3">
        <Skeleton class="h-20 w-full" />
        <Skeleton class="h-40 w-full" />
      </div>

      <div v-else class="flex flex-col gap-5">
        <div>
          <p class="mb-2 text-sm font-medium text-ink-gray-8">{{ __('Where is your {0}?').format(label) }}</p>
          <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <button
              v-for="option in options"
              :key="option.value"
              type="button"
              class="flex items-start gap-3 rounded-5 border p-3 text-left transition-colors"
              :class="
                form.mode === option.value ? 'border-outline-gray-5 bg-surface-gray-1' : 'border-outline-gray-2 hover:bg-surface-gray-1'
              "
              :aria-pressed="form.mode === option.value"
              @click="form.mode = option.value"
            >
              <span class="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border border-outline-gray-4">
                <span v-if="form.mode === option.value" class="size-2 rounded-full bg-surface-gray-8" />
              </span>
              <span class="min-w-0">
                <span class="flex items-center gap-2">
                  <span :class="option.icon" class="size-4 text-ink-gray-6" aria-hidden="true" />
                  <span class="text-base font-medium text-ink-gray-8">{{ option.label }}</span>
                </span>
                <span class="mt-1 block text-sm text-ink-gray-5">{{ option.description }}</span>
              </span>
            </button>
          </div>
        </div>

        <div v-if="integration === 'crm'" class="flex items-start gap-2 rounded-4 bg-surface-blue-1 p-3 text-sm text-ink-blue-7">
          <span class="lucide-messages-square mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span v-if="form.mode === THIS_SITE">
            {{
              __(
                "Frappe CRM's WhatsApp tab and the OneChat inbox show the same chats. Nothing is copied: messages sent from either app appear in both, and chats are matched to the lead or deal automatically.",
              )
            }}
          </span>
          <span v-else>
            {{
              __(
                'Keep WhatsApp turned off in Frappe CRM on that site, or the same chats arrive in both apps. OneChat handles WhatsApp and links each chat to its lead or deal.',
              )
            }}
          </span>
        </div>

        <template v-if="form.mode === THIS_SITE">
          <div v-if="state.installed_here" class="flex items-start gap-2 rounded-4 bg-surface-green-1 p-3 text-sm text-ink-green-7">
            <span class="lucide-circle-check mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {{ __('{0} is installed on this site. Everything works without any extra setup.').format(label) }}
          </div>
          <div v-else class="rounded-4 bg-surface-gray-1 p-3">
            <p class="text-sm font-medium text-ink-gray-8">{{ __('{0} is not installed on this site').format(label) }}</p>
            <p class="mt-1 text-sm text-ink-gray-6">{{ __('Install it with these commands, or choose Another site.') }}</p>
            <ScrollArea orientation="horizontal" class="mt-2 rounded-3 bg-surface-base">
              <pre class="px-2.5 py-2 font-mono text-xs text-ink-gray-8">{{ installCommand }}</pre>
            </ScrollArea>
          </div>
        </template>

        <template v-else>
          <div class="flex flex-col gap-3">
            <FormControl
              v-model="form.url"
              :label="__('{0} site address').format(label)"
              placeholder="https://erp.example.com"
              :description="__('The address you open {0} at.').format(label)"
            />
            <div class="flex flex-col gap-1.5">
              <FormLabel :label="__('Connect with')" />
              <TabButtons
                v-model="form.auth"
                class="self-start"
                :options="[
                  { label: __('Sign in (recommended)'), value: OAUTH },
                  { label: __('API key'), value: API_KEY },
                ]"
              />
            </div>
          </div>

          <template v-if="form.auth === OAUTH">
            <div
              v-if="state.signed_in && state.auth_method === OAUTH"
              class="flex items-center justify-between gap-3 rounded-4 bg-surface-green-1 p-3"
            >
              <p class="flex min-w-0 items-center gap-2 text-sm text-ink-green-7">
                <span class="lucide-shield-check size-4 shrink-0" aria-hidden="true" />
                <TruncatedText
                  class="truncate"
                  :text="state.oauth_user ? __('Signed in as {0}').format(state.oauth_user) : __('Signed in')"
                />
              </p>
              <Button
                size="sm"
                variant="subtle"
                :loading="busy === 'sign_out'"
                :label="__('Sign out')"
                @click="run('sign_out', () => signOut(integration))"
              />
            </div>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FormControl v-model="form.client_id" type="text" :label="__('Client ID')" autocomplete="off" />
              <Password
                v-model="form.client_secret"
                :label="__('Client secret')"
                autocomplete="new-password"
                :placeholder="state.has_client_secret ? __('Saved. Leave blank to keep it.') : __('Optional')"
              />
            </div>

            <div class="rounded-4 border border-outline-gray-2 p-3">
              <p class="text-sm font-medium text-ink-gray-8">{{ __('Redirect URL') }}</p>
              <div class="mt-2 flex items-center gap-2">
                <TruncatedText
                  as="code"
                  class="min-w-0 flex-1 truncate rounded-3 bg-surface-gray-2 px-2 py-1.5 text-xs text-ink-gray-8"
                  :text="state.redirect_uri"
                />
                <Button size="sm" variant="subtle" icon="lucide-copy" :label="__('Copy')" @click="copy(state.redirect_uri)" />
              </div>
            </div>

            <details class="group rounded-4 border border-outline-gray-2 px-3 py-2.5" open>
              <summary class="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-ink-gray-8">
                {{ __('How do I get a client ID?') }}
                <span class="lucide-chevron-down size-4 text-ink-gray-5 transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <ol class="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-ink-gray-6">
                <li>{{ __('On your {0} site, open OAuth Client and click New.').format(label) }}</li>
                <li>{{ __('Name it OneChat, paste the Redirect URL above into Redirect URIs and Default Redirect URI.') }}</li>
                <li>{{ __('Set Grant Type to Authorization Code and Response Type to Code, then save.') }}</li>
                <li>
                  {{
                    __('Copy the Client ID and Client Secret here and click Sign in. Sign in with a user that has the roles {0}.').format(
                      state.roles || __('it needs'),
                    )
                  }}
                </li>
              </ol>
            </details>
          </template>

          <div v-else class="flex flex-col gap-3">
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Password v-model="form.api_key" :label="__('API key')" autocomplete="off" />
              <Password
                v-model="form.api_secret"
                :label="__('API secret')"
                autocomplete="new-password"
                :placeholder="state.has_secret ? __('Saved. Leave blank to keep it.') : ''"
              />
            </div>
          </div>

          <details v-if="form.auth === API_KEY" class="group rounded-4 border border-outline-gray-2 px-3 py-2.5">
            <summary class="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-ink-gray-8">
              {{ __('How do I get an API key?') }}
              <span class="lucide-chevron-down size-4 text-ink-gray-5 transition-transform group-open:rotate-180" aria-hidden="true" />
            </summary>
            <ol class="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-ink-gray-6">
              <li>
                {{
                  __('On your {0} site, open the User list and create a user for OneChat, for example onechat@yourcompany.com.').format(
                    label,
                  )
                }}
              </li>
              <li>
                {{
                  __('Give it the roles {0}. Add System Manager so OneChat can set up webhooks for you.').format(
                    state.roles || __('it needs'),
                  )
                }}
              </li>
              <li>{{ __('Open the user, go to Settings → API Access and click Generate Keys.') }}</li>
              <li>{{ __('Copy the API key and the API secret shown once, and paste them here.') }}</li>
            </ol>
          </details>

          <div v-if="state.status || state.webhooks" class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-3 text-sm">
            <p v-if="state.status" class="flex items-start gap-2" :class="connected ? 'text-ink-green-7' : 'text-ink-red-6'">
              <span :class="connected ? 'lucide-circle-check' : 'lucide-circle-x'" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <span>
                {{ state.status }}
                <span v-if="state.checked_at" class="text-ink-gray-5"> · {{ timeAgo(state.checked_at) }}</span>
              </span>
            </p>
            <p v-if="state.webhooks" class="flex items-start gap-2 text-ink-gray-6">
              <span class="lucide-webhook mt-0.5 size-4 shrink-0" aria-hidden="true" />{{ state.webhooks }}
            </p>
            <p v-if="form.mode === ANOTHER_SITE" class="flex items-start gap-2" :class="eventTone">
              <span
                :class="state.last_event_at ? 'lucide-radio' : 'lucide-circle-dashed'"
                class="mt-0.5 size-4 shrink-0"
                aria-hidden="true"
              />
              {{
                state.last_event_at
                  ? __('Last event from {0} {1}: {2}').format(label, timeAgo(state.last_event_at), state.last_event)
                  : __('No events received from {0} yet').format(label)
              }}
            </p>
          </div>

          <div v-if="form.mode === ANOTHER_SITE && state.ready" class="flex flex-col gap-2 rounded-4 border border-outline-gray-2 p-3">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <p class="flex items-center gap-1 text-sm font-medium text-ink-gray-8">
                  {{ __('Least-privilege role') }}
                  <InfoHint
                    :title="state.role"
                    :text="
                      __(
                        'Creates a {0} role on {1} with only the access OneChat needs, and gives it to the connected user. Afterwards you can remove broader roles like System Manager from that user. Access: {2}.',
                      ).format(state.role, label, accessText)
                    "
                  />
                </p>
                <p class="mt-0.5 text-sm text-ink-gray-6">
                  {{
                    state.role_status || __('Create a {0} role on {1} so the connected user needs nothing more.').format(state.role, label)
                  }}
                </p>
              </div>
              <Button
                size="sm"
                variant="subtle"
                icon-left="lucide-shield-check"
                :loading="busy === 'role'"
                :label="state.role_status ? __('Update role') : __('Create role')"
                @click="run('role', () => setupIntegrationRole(integration))"
              />
            </div>
          </div>

          <div class="rounded-4 border border-outline-gray-2 p-3">
            <p class="text-sm font-medium text-ink-gray-8">{{ __('Webhook address') }}</p>
            <p class="mt-1 text-sm text-ink-gray-6">
              {{
                __(
                  '{0} tells OneChat when records change through webhooks, so flows can start from them. OneChat adds them for you. If it cannot, add a webhook in {0} with this address, a JSON body and a secret.',
                ).format(label)
              }}
            </p>
            <div class="mt-2 flex items-center gap-2">
              <TruncatedText
                as="code"
                class="min-w-0 flex-1 truncate rounded-3 bg-surface-gray-2 px-2 py-1.5 text-xs text-ink-gray-8"
                :text="state.webhook_url"
              />
              <Button size="sm" variant="subtle" icon="lucide-copy" :label="__('Copy')" @click="copy(state.webhook_url)" />
            </div>
          </div>
        </template>

        <div
          v-if="form.mode === ANOTHER_SITE ? state.ready : state.installed_here"
          class="flex items-start justify-between gap-4 rounded-4 border border-outline-gray-2 p-3"
        >
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink-gray-8">{{ __('Auto-link new contacts') }}</p>
            <p class="mt-0.5 text-sm text-ink-gray-5">
              {{ __('When a new number messages you, link it to the {0} record with that phone number.').format(label) }}
            </p>
          </div>
          <Switch
            :model-value="!!integrations.data?.auto_link"
            :disabled="busy === 'auto_link'"
            :aria-label="__('Auto-link new contacts')"
            @update:model-value="toggleAutoLink"
          />
        </div>

        <div
          v-if="integration === 'crm' && erpnextOn && (form.mode === ANOTHER_SITE ? state.ready : state.installed_here)"
          class="flex items-start justify-between gap-4 rounded-4 border border-outline-gray-2 p-3"
        >
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink-gray-8">{{ __('Create ERPNext customer when a deal is won') }}</p>
            <p class="mt-0.5 text-sm text-ink-gray-5">
              {{
                __(
                  'Won deals always link the chat to the ERPNext customer with the same phone number. Turn this on to create the customer when none exists.',
                )
              }}
            </p>
          </div>
          <Switch
            :model-value="!!integrations.data?.create_customer_on_win"
            :disabled="busy === 'won_customer'"
            :aria-label="__('Create ERPNext customer when a deal is won')"
            @update:model-value="toggleWonCustomer"
          />
        </div>

        <div
          v-if="integration === 'crm' && form.mode === ANOTHER_SITE && state.ready"
          class="flex items-start justify-between gap-4 rounded-4 border border-outline-gray-2 p-3"
        >
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink-gray-8">{{ __('WhatsApp button in Frappe CRM') }}</p>
            <p class="mt-0.5 text-sm text-ink-gray-5">
              {{
                __(
                  'Adds a Chat on WhatsApp button to CRM leads and deals. It opens the conversation here in OneChat. Needs a System Manager sign-in on the CRM site.',
                )
              }}
            </p>
          </div>
          <Button
            size="sm"
            variant="subtle"
            icon-left="lucide-plus"
            class="shrink-0"
            :label="__('Add to CRM')"
            :loading="busy === 'crm_button'"
            @click="addCrmButton"
          />
        </div>

        <ErrorMessage :message="error" />
      </div>
    </template>

    <template #actions>
      <div class="flex w-full flex-wrap items-center justify-between gap-2">
        <div class="flex flex-wrap gap-2">
          <Button
            v-if="form.mode === ANOTHER_SITE && state.ready"
            variant="subtle"
            icon-left="lucide-activity"
            :loading="busy === 'test'"
            :label="__('Test connection')"
            @click="run('test', () => testConnection(integration))"
          />
          <Button
            v-if="form.mode === ANOTHER_SITE && state.ready"
            variant="subtle"
            icon-left="lucide-refresh-cw"
            :loading="busy === 'sync'"
            :label="__('Refresh webhooks')"
            @click="run('sync', () => syncConnectionWebhooks(integration))"
          />
        </div>
        <div class="flex flex-wrap gap-2">
          <Button v-if="enabled" variant="ghost" theme="red" :label="__('Disconnect')" @click="emit('disconnect')" />
          <Button
            v-if="form.mode === ANOTHER_SITE && form.auth === OAUTH"
            variant="solid"
            icon-left="lucide-log-in"
            :loading="busy === 'oauth'"
            :disabled="!form.url || !form.client_id"
            :label="state.signed_in && state.auth_method === OAUTH ? __('Sign in again') : __('Sign in with {0}').format(label)"
            @click="signIn"
          />
          <Button
            v-else
            variant="solid"
            :loading="busy === 'save'"
            :disabled="form.mode === THIS_SITE && !state.installed_here"
            :label="enabled ? __('Save') : __('Save and connect')"
            @click="save"
          />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, FormLabel, Password, ScrollArea, Skeleton, Switch, TabButtons, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import {
  activeIntegrations,
  connectionSettings,
  integrations,
  saveConnection,
  setAutoLink,
  setCreateCustomerOnWin,
  installCrmButton,
  signOut,
  startOAuth,
  setupIntegrationRole,
  syncConnectionWebhooks,
  testConnection,
} from '@/data/integrations'
import InfoHint from '@/components/Common/InfoHint.vue'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const THIS_SITE = 'This site'
const RIGHTS = { r: 'read', w: 'write', c: 'create', d: 'delete', s: 'submit' }
const ANOTHER_SITE = 'Another site'
const OAUTH = 'OAuth'
const API_KEY = 'API key'

const erpnextOn = computed(() => activeIntegrations.value.some((row) => row.name === 'erpnext'))

const props = defineProps({
  integration: { type: String, default: '' },
  label: { type: String, default: '' },
  enabled: { type: Boolean, default: false },
})

const emit = defineEmits(['disconnect'])

const open = defineModel('open', { type: Boolean, default: false })

const loaded = ref(false)
const busy = ref('')
const error = ref('')
const state = ref({})
const form = reactive({ mode: THIS_SITE, url: '', auth: OAUTH, client_id: '', client_secret: '', api_key: '', api_secret: '' })

const options = computed(() => [
  {
    value: THIS_SITE,
    icon: 'lucide-server',
    label: __('On this site'),
    description: state.value.installed_here
      ? __('{0} is installed next to OneChat.').format(props.label)
      : __('{0} is installed next to OneChat. It is not installed here yet.').format(props.label),
  },
  {
    value: ANOTHER_SITE,
    icon: 'lucide-globe',
    label: __('On another site'),
    description: __('Connect to a separate {0} by signing in to it.').format(props.label),
  },
])

const connected = computed(() => !!state.value.connected)

const eventTone = computed(() => {
  const at = state.value.last_event_at
  if (!at) return 'text-ink-gray-5'
  return Date.now() - new Date(at).getTime() < 7 * 24 * 3600 * 1000 ? 'text-ink-green-7' : 'text-ink-amber-6'
})

const accessText = computed(() =>
  (state.value.access || []).map((row) => `${row.doctype} (${[...row.rights].map((letter) => __(RIGHTS[letter])).join(', ')})`).join('; '),
)

const installCommand = computed(() => `bench get-app ${state.value.app}\nbench --site <site> install-app ${state.value.app}`)

function apply(result) {
  state.value = result || {}
  form.mode = state.value.mode || THIS_SITE
  form.url = state.value.url || ''
  form.api_key = state.value.api_key || ''
  form.api_secret = ''
  form.client_id = state.value.client_id || ''
  form.client_secret = ''
  form.auth = state.value.auth_method === API_KEY && state.value.api_key ? API_KEY : OAUTH
}

async function signIn() {
  busy.value = 'oauth'
  error.value = ''
  try {
    window.location.href = await startOAuth(props.integration, form)
  } catch (err) {
    error.value = errorMessage(err)
    busy.value = ''
  }
}

async function load() {
  loaded.value = false
  error.value = ''
  try {
    apply(await connectionSettings(props.integration))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loaded.value = true
  }
}

async function run(kind, work) {
  busy.value = kind
  error.value = ''
  try {
    state.value = await work()
  } catch (err) {
    error.value = errorMessage(err)
    await load()
  } finally {
    busy.value = ''
  }
}

async function save() {
  busy.value = 'save'
  error.value = ''
  try {
    apply(await saveConnection(props.integration, { ...form }))
    toast.success(__('{0} connected').format(props.label))
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
    try {
      state.value = await connectionSettings(props.integration)
    } catch {
      state.value = { ...state.value }
    }
  } finally {
    busy.value = ''
  }
}

async function addCrmButton() {
  busy.value = 'crm_button'
  error.value = ''
  try {
    toast.success(await installCrmButton())
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = ''
  }
}

async function toggleWonCustomer(value) {
  busy.value = 'won_customer'
  error.value = ''
  try {
    await setCreateCustomerOnWin(value)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = ''
  }
}

async function toggleAutoLink(value) {
  busy.value = 'auto_link'
  error.value = ''
  try {
    await setAutoLink(value)
    toast.success(value ? __('Auto-linking on') : __('Auto-linking off'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = ''
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(__('Copied'))
  } catch {
    toast.error(__('Could not copy'))
  }
}

watch(open, (value) => value && props.integration && load(), { immediate: true })
</script>

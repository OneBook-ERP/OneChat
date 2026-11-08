<template>
  <SettingsHeader>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Automation') }}</h2>
        <p class="mt-1 text-base text-ink-gray-6">
          {{ __('The user that flows, the AI, payment receipts and catalog orders run as when no one is signed in') }}
        </p>
      </div>
      <Button variant="solid" :label="__('Save')" :loading="saving" :disabled="loading || !dirty" @click="save" />
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <div v-if="loading" class="flex flex-col gap-3 pt-6">
      <Skeleton v-for="row in 3" :key="row" class="h-12 w-full" />
    </div>

    <template v-else>
      <div class="divide-y divide-outline-gray-1 pt-6">
        <SettingsRow
          :title="__('Run flows and AI as')"
          :description="__('Records they create or change show this user. Use a user made for this, with only the roles it needs.')"
        >
          <Select v-model="form.user" class="w-72" :options="userOptions" />
        </SettingsRow>
      </div>

      <div v-if="notice" class="mt-4 flex items-start gap-2.5 rounded-4 bg-surface-amber-1 p-3 text-sm text-ink-amber-8">
        <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>{{ notice }}</p>
      </div>

      <div v-if="form.sites.length" class="flex flex-col gap-3 pt-8">
        <div>
          <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Connected sites') }}</h3>
          <p class="mt-1 text-sm text-ink-gray-6">
            {{ __('The API key and secret of the automation user on each site. Leave empty to use the connection’s own login.') }}
          </p>
        </div>
        <div v-for="site in form.sites" :key="site.key" class="flex flex-col gap-3 rounded-4 border border-outline-gray-2 p-4">
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink-gray-8">{{ site.label }}</p>
            <p class="truncate text-sm text-ink-gray-5">{{ site.url }}</p>
          </div>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Password v-model="site.api_key" :label="__('API key')" autocomplete="off" />
            <Password
              v-model="site.api_secret"
              :label="__('API secret')"
              autocomplete="new-password"
              :placeholder="site.has_secret ? __('Saved. Leave blank to keep it.') : ''"
            />
          </div>
        </div>
      </div>

      <div class="flex flex-col gap-3 pt-8 pb-6">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Check access') }}</h3>
            <p class="mt-1 text-sm text-ink-gray-6">
              {{ __('What the saved user can do for the integrations that are on.') }}
            </p>
          </div>
          <Button :label="__('Check access')" :loading="checking" :disabled="dirty || !saved.user" @click="check" />
        </div>

        <div v-if="access" class="rounded-4 border border-outline-gray-2">
          <div
            v-for="row in access.local"
            :key="`${row.doctype}-${row.action}`"
            class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-3 py-2 last:border-b-0"
          >
            <span class="text-sm text-ink-gray-8">{{ __(row.doctype) }} · {{ actionLabel(row.action) }}</span>
            <Badge variant="subtle" :theme="row.ok ? 'green' : 'red'" :label="row.ok ? __('Allowed') : __('Missing')" />
          </div>
          <div
            v-for="site in access.sites"
            :key="site.label"
            class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-3 py-2 last:border-b-0"
          >
            <span class="text-sm text-ink-gray-8">{{ site.label }}</span>
            <span v-if="site.ok" class="text-sm text-ink-gray-6">
              {{ site.user ? __('Signs in as {0}').format(site.user) : __('Uses the connection’s login') }}
            </span>
            <span v-else class="min-w-0 truncate text-sm text-ink-red-7" :title="site.error">{{ site.error }}</span>
          </div>
        </div>

        <p v-if="missing" class="text-sm text-ink-gray-6">
          {{
            __('Give {0} roles that allow the missing items, then check again. Steps that need them fail until then.').format(saved.user)
          }}
        </p>
      </div>
    </template>
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Badge, Button, ErrorMessage, Password, Select, SettingsBody, SettingsHeader, SettingsRow, Skeleton, call, toast } from 'frappe-ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const API = 'onechat.workspace.automation'
const ACTIONS = { read: 'read', write: 'edit', create: 'create', submit: 'submit' }

const loading = ref(true)
const saving = ref(false)
const checking = ref(false)
const error = ref('')
const users = ref([])
const access = ref(null)
const saved = reactive({ user: '', sites: '' })
const form = reactive({ user: '', sites: [] })

const userOptions = computed(() => [{ label: __('Nobody (old behaviour)'), value: '' }, ...users.value])

const siteState = computed(() => JSON.stringify(form.sites.map((site) => [site.key, site.api_key, site.api_secret])))

const dirty = computed(() => form.user !== saved.user || siteState.value !== saved.sites)

const notice = computed(() => {
  if (!form.user)
    return __('No user picked. Flows started by customers run as Guest, and orders, payments and workflow steps run as Administrator.')
  if (form.user === 'Administrator')
    return __('Administrator can do everything. A user made for automation, with only the roles it needs, is safer.')
  return ''
})

const missing = computed(() => (access.value?.local || []).some((row) => !row.ok))

function actionLabel(action) {
  return __(ACTIONS[action] || action)
}

function apply(data) {
  users.value = data.users || []
  form.user = data.user || ''
  form.sites = (data.sites || []).map((site) => ({ ...site, api_secret: '' }))
  saved.user = form.user
  saved.sites = siteState.value
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    apply(await call(`${API}.get_settings`))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const sites = form.sites.map(({ key, api_key, api_secret }) => ({ key, api_key, api_secret }))
    apply(await call(`${API}.save_settings`, { user: form.user, sites: JSON.stringify(sites) }))
    access.value = null
    toast.success(__('Automation settings saved'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

async function check() {
  checking.value = true
  error.value = ''
  try {
    access.value = await call(`${API}.check_access`)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    checking.value = false
  }
}

onMounted(load)
</script>

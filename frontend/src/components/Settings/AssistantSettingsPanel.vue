<template>
  <template v-if="!dialog">
    <SettingsHeader :title="__('Assistant')" :description="__('Let agents ask about a customer and draft replies, using an AI provider')">
      <template #actions>
        <Button variant="solid" :loading="saving" :disabled="loading" :label="__('Save')" @click="save" />
      </template>
    </SettingsHeader>
  </template>

  <component :is="dialog ? 'div' : SettingsBody">
    <div v-if="loading" class="flex flex-col gap-3 pt-4">
      <Skeleton v-for="row in 4" :key="row" class="h-12 w-full" />
    </div>

    <div v-else class="flex flex-col gap-6 pt-4">
      <ErrorMessage :message="error" />

      <div class="divide-y divide-outline-gray-1">
        <SettingsRow
          :title="__('Enable the assistant')"
          :description="__('Shows the assistant in each chat’s side panel for people with access below.')"
        >
          <Switch v-model="form.enabled" />
        </SettingsRow>
      </div>

      <div v-if="!form.sites.length" class="flex items-start gap-2.5 rounded-4 bg-surface-amber-1 p-3 text-sm text-ink-amber-8">
        <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div class="flex flex-col gap-1.5">
          <p>
            {{
              __(
                'ERPNext and Frappe CRM aren’t connected. The assistant can still help with chats, but not with orders, invoices or leads.',
              )
            }}
          </p>
          <Button
            class="self-start"
            size="sm"
            variant="subtle"
            icon-left="lucide-plug"
            :label="__('Open integrations')"
            @click="ui.openSettings('integrations')"
          />
        </div>
      </div>

      <div class="flex flex-col gap-3">
        <div class="flex flex-col gap-1.5">
          <div class="flex items-center justify-between gap-3">
            <FormLabel :label="__('AI providers')" />
            <Tooltip
              v-if="form.sites.length"
              :text="__('The assistant reads and changes records on {0}, with each agent’s own permissions.').format(form.sites.join(', '))"
            >
              <span
                class="inline-flex min-w-0 max-w-[65%] cursor-default items-center gap-1 rounded-full bg-surface-green-1 px-2 py-0.5 text-xs text-ink-green-7"
              >
                <span class="lucide-circle-check size-3 shrink-0" aria-hidden="true" />
                <span class="truncate">{{ __('Connected to {0}').format(form.sites[0]) }}</span>
                <span v-if="form.sites.length > 1" class="shrink-0 tabular-nums">+{{ form.sites.length - 1 }}</span>
              </span>
            </Tooltip>
          </div>
          <p v-if="!form.providers.length" class="rounded-4 bg-surface-gray-1 px-3 py-2.5 text-sm text-ink-gray-6">
            {{ __('No AI provider yet. Add one, then pick the model the assistant uses.') }}
          </p>
        </div>

        <div
          v-for="provider in form.providers"
          :key="provider.name"
          class="flex flex-col gap-2.5 rounded-4 border border-outline-gray-2 p-3"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-ink-gray-8">{{ provider.name }}</p>
              <p class="truncate text-sm text-ink-gray-5">{{ provider.api_base || provider.litellm_provider }}</p>
            </div>
            <div class="flex items-center gap-1">
              <Badge
                variant="subtle"
                :theme="provider.has_key ? 'green' : 'orange'"
                :label="provider.has_key ? __('Key saved') : __('No key')"
              />
              <Button size="sm" variant="ghost" :label="__('Change key')" @click="editKey(provider)" />
              <Button size="sm" variant="ghost" icon="lucide-trash-2" :label="__('Remove')" @click="removeProvider(provider)" />
            </div>
          </div>
          <div v-if="keyEdit.name === provider.name" class="flex items-end gap-2">
            <Password v-model="keyEdit.value" class="min-w-0 flex-1" :label="__('New API key')" autocomplete="new-password" />
            <Button variant="solid" :label="__('Save key')" :loading="keyEdit.saving" @click="saveKey" />
          </div>
          <div class="flex flex-wrap gap-x-4 gap-y-1.5">
            <label
              v-for="model in provider.models"
              :key="model.name"
              class="flex cursor-pointer items-center gap-1.5 text-sm text-ink-gray-7"
            >
              <Checkbox :model-value="!!model.enabled" @update:model-value="(value) => toggleModel(model, value)" />
              {{ model.label }}
            </label>
          </div>
        </div>

        <Button class="self-start" icon-left="lucide-plus" :label="__('Add provider')" @click="adding = true" />
        <ProviderSetupDialog v-model:open="adding" :presets="form.presets" @added="applyState" />

        <FormControl
          v-if="modelOptions.length > 1"
          v-model="form.model"
          type="select"
          :label="__('Assistant model')"
          :options="modelOptions"
          :description="__('The model agents talk to in the Assistant panel.')"
        />
        <div v-if="modelOptions.length > 1" class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormControl
            v-model="form.bot_model"
            type="select"
            :label="__('Customer bot model')"
            :options="botModelOptions"
            :description="__('Used by the AI agent step in flows. A fast, cheap model works well here.')"
          />
          <FormControl
            v-model="form.bot_daily_limit"
            type="number"
            :label="__('AI replies per day')"
            :description="__('Across all chats. After that, chats go to the team until tomorrow.')"
          />
        </div>
        <FormControl
          v-model="form.max_tokens"
          type="number"
          :label="__('Max tokens per reply')"
          :description="
            __('The longest answer the AI can write, from 1,024 to 64,000. Higher allows longer answers and costs more when used.')
          "
        />
        <div v-if="form.agent_sites.length" class="flex items-start justify-between gap-4 rounded-4 border border-outline-gray-2 p-3">
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink-gray-8">{{ __('Agents sign in to other sites themselves') }}</p>
            <p class="mt-0.5 text-sm text-ink-gray-6">
              {{
                __(
                  'When ERPNext or CRM is on another site, each agent signs in there once from the Assistant panel, so they only see and change what their own account allows. Turn off to let everyone use the account that connected the site.',
                )
              }}
            </p>
          </div>
          <Switch v-model="form.agent_signin" />
        </div>
      </div>

      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between gap-2">
          <div>
            <p class="text-base font-medium text-ink-gray-8">{{ __('Access by role') }}</p>
            <p class="mt-0.5 text-sm text-ink-gray-5">
              {{
                __(
                  'Read looks records up. Write updates and submits existing records and sends payment links. Create makes new records. Write and create always wait for the agent to confirm. Code, database queries and deleting are never allowed.',
                )
              }}
            </p>
          </div>
          <Button
            icon-left="lucide-plus"
            :label="__('Add role')"
            @click="form.roles.push({ role: '', read: true, write: false, create: false })"
          />
        </div>
        <p v-if="!form.roles.length" class="rounded-4 bg-surface-gray-1 px-3 py-2.5 text-sm text-ink-gray-6">
          {{ __('No roles added: OneChat admins can read, write and create, everyone else can only read.') }}
        </p>
        <div v-if="form.roles.length" class="hidden items-center gap-2 text-xs font-medium text-ink-gray-5 sm:flex">
          <span class="min-w-0 flex-1">{{ __('Role') }}</span>
          <span v-for="right in RIGHTS" :key="right.key" class="w-16 text-center">{{ right.label }}</span>
          <span class="w-8" />
        </div>
        <div v-for="(row, index) in form.roles" :key="index" class="flex flex-wrap items-center gap-2 sm:flex-nowrap">
          <LinkField v-model="row.role" class="min-w-0 flex-1 basis-full sm:basis-auto" doctype="Role" :placeholder="__('Search role')" />
          <label
            v-for="right in RIGHTS"
            :key="right.key"
            class="flex w-16 items-center justify-center gap-1.5 text-sm text-ink-gray-7"
            :title="right.hint"
          >
            <Checkbox
              :model-value="!!row[right.key]"
              :disabled="right.key === 'read' && (row.write || row.create)"
              @update:model-value="(value) => setRight(row, right.key, value)"
            />
            <span class="sm:hidden">{{ right.label }}</span>
          </label>
          <Button variant="ghost" icon="lucide-x" :label="__('Remove')" @click="form.roles.splice(index, 1)" />
        </div>
      </div>

      <p class="text-sm text-ink-gray-5">
        {{
          __(
            'Questions, the customer’s recent chat and the records the assistant looks up are sent to the chosen AI provider. Each agent only sees data their own ERPNext permissions allow.',
          )
        }}
      </p>
    </div>
    <div v-if="dialog && !loading" class="flex justify-end gap-2 pt-5">
      <Button variant="solid" :loading="saving" :label="__('Save')" @click="save" />
    </div>
  </component>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Badge,
  Button,
  Checkbox,
  ErrorMessage,
  FormControl,
  FormLabel,
  Password,
  SettingsBody,
  SettingsHeader,
  SettingsRow,
  Skeleton,
  Switch,
  Tooltip,
  call,
  toast,
} from 'frappe-ui'
import LinkField from '@/components/Common/LinkField.vue'
import ProviderSetupDialog from './ProviderSetupDialog.vue'
import { assistantSettings, assistantStatus, saveAssistantSettings } from '@/data/assistant'
import { integrations } from '@/data/integrations'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ dialog: { type: Boolean, default: false } })
const emit = defineEmits(['saved'])

const RIGHTS = [
  { key: 'read', label: __('Read'), hint: __('Look up records and totals') },
  { key: 'write', label: __('Write'), hint: __('Update and submit existing records, send payment links') },
  { key: 'create', label: __('Create'), hint: __('Create new records') },
]

function setRight(row, key, value) {
  row[key] = !!value
  if (value && key !== 'read') row.read = true
}

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const ui = useUI()

const SETUP = 'onechat.assistant.setup'
const adding = ref(false)
const keyEdit = reactive({ name: '', value: '', saving: false })

const form = reactive({
  enabled: false,
  model: '',
  bot_model: '',
  bot_daily_limit: 500,
  max_tokens: 16000,
  agent_signin: true,
  agent_sites: [],
  roles: [],
  sites: [],
  providers: [],
  presets: [],
})

const modelOptions = computed(() => [
  { label: __('Pick a model'), value: '' },
  ...form.providers
    .filter((provider) => provider.enabled)
    .flatMap((provider) =>
      provider.models.filter((model) => model.enabled).map((model) => ({ label: `${model.label} · ${provider.name}`, value: model.name })),
    ),
])

const botModelOptions = computed(() => [{ label: __('Same as the assistant model'), value: '' }, ...modelOptions.value.slice(1)])

function applyState(state) {
  form.providers = state.providers || []
  form.presets = state.presets || []
  if (!form.model || !modelOptions.value.some((option) => option.value === form.model)) {
    form.model = modelOptions.value[1]?.value || ''
  }
  if (form.bot_model && !botModelOptions.value.some((option) => option.value === form.bot_model)) {
    form.bot_model = ''
  }
}

function apply(data) {
  Object.assign(form, {
    enabled: !!data.enabled,
    model: data.model || '',
    bot_model: data.bot_model || '',
    bot_daily_limit: data.bot_daily_limit || 500,
    max_tokens: data.max_tokens,
    agent_signin: !!data.agent_signin,
    agent_sites: data.agent_sites || [],
    roles: (data.roles || []).map((row) => ({ ...row })),
    sites: data.sites || [],
  })
  applyState(data)
}

async function run(action) {
  error.value = ''
  try {
    applyState(await action())
  } catch (err) {
    error.value = errorMessage(err)
  }
}

function toggleModel(model, value) {
  run(() => call(`${SETUP}.set_model_enabled`, { name: model.name, enabled: value ? 1 : 0 }))
}

function editKey(provider) {
  Object.assign(keyEdit, { name: keyEdit.name === provider.name ? '' : provider.name, value: '' })
}

async function saveKey() {
  keyEdit.saving = true
  await run(() => call(`${SETUP}.update_key`, { name: keyEdit.name, api_key: keyEdit.value }))
  keyEdit.saving = false
  if (!error.value) Object.assign(keyEdit, { name: '', value: '' })
}

function removeProvider(provider) {
  ui.confirm({
    title: __('Remove {0}?').format(provider.name),
    message: __('Its saved key and models are deleted. The assistant stops working if it uses one of them.'),
    action: __('Remove'),
    theme: 'red',
    onConfirm: () => run(() => call(`${SETUP}.remove_provider`, { name: provider.name })),
  })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    apply(await assistantSettings())
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
    apply(
      await saveAssistantSettings({
        enabled: form.enabled ? 1 : 0,
        agent_signin: form.agent_signin ? 1 : 0,
        model: form.model,
        bot_model: form.bot_model,
        bot_daily_limit: Number(form.bot_daily_limit) || 500,
        max_tokens: Number(form.max_tokens) || 16000,
        roles: form.roles.filter((row) => row.role),
      }),
    )
    assistantStatus.reload()
    integrations.reload()
    toast.success(__('Assistant settings saved'))
    emit('saved')
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <template v-if="!dialog">
    <SettingsHeader
      :title="__('Assistant')"
      :description="__('Let agents ask about a customer and draft replies, using Frappe Assistant Core and an AI provider')"
    >
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
          <p>{{ __('Frappe Assistant Core is not installed. Install it on the site that has your ERPNext or CRM data:') }}</p>
          <ScrollArea orientation="horizontal" class="rounded-3 bg-surface-base">
            <pre class="px-2.5 py-2 font-mono text-xs text-ink-gray-8">{{ installCommand }}</pre>
          </ScrollArea>
          <p class="text-ink-gray-6">
            {{
              __(
                'FAC on another site is found through your ERPNext or Frappe CRM connection. Connect that site with Sign in (OAuth) and install FAC there.',
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
            <FormLabel :label="__('AI provider')" />
            <Tooltip
              v-if="form.sites.length"
              :text="
                __('Frappe Assistant Core is installed on {0}. It gives the AI its tools to read and change records.').format(
                  form.sites.join(', '),
                )
              "
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
          <TabButtons
            v-model="form.provider"
            class="self-start"
            :options="[
              { label: 'Claude', value: 'Claude' },
              { label: 'OpenAI', value: 'OpenAI' },
              { label: __('Other'), value: 'Other' },
            ]"
          />
        </div>
        <template v-if="form.provider === 'Claude'">
          <Password
            v-model="form.anthropic_key"
            :label="__('Claude API key')"
            :placeholder="form.has_anthropic_key ? __('Saved. Leave blank to keep it.') : 'sk-ant-…'"
            :description="__('From console.anthropic.com → API keys.')"
          />
          <FormControl
            v-model="form.claude_model"
            type="text"
            :label="__('Claude model')"
            :placeholder="form.defaults.claude_model"
            :description="__('Leave empty to use {0}.').format(form.defaults.claude_model)"
          />
        </template>
        <template v-else-if="form.provider === 'Other'">
          <div class="flex flex-col gap-1.5">
            <FormLabel :label="__('Provider')" />
            <div class="flex flex-wrap gap-1.5">
              <Button
                v-for="preset in PRESETS"
                :key="preset.name"
                size="sm"
                :variant="form.other_url === preset.url ? 'solid' : 'subtle'"
                :label="preset.name"
                @click="usePreset(preset)"
              />
            </div>
            <p class="text-sm text-ink-gray-5">
              {{ __('Any provider with an OpenAI-compatible API works. Pick one to fill in its address, or enter your own.') }}
            </p>
          </div>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormControl v-model="form.other_name" type="text" :label="__('Name')" placeholder="Gemini" />
            <FormControl
              v-model="form.other_model"
              type="text"
              :label="__('Model')"
              :placeholder="presetOf(form.other_url)?.model || 'model-name'"
            />
          </div>
          <FormControl
            v-model="form.other_url"
            type="text"
            :label="__('API address')"
            placeholder="https://generativelanguage.googleapis.com/v1beta/openai/"
            :description="__('The OpenAI-compatible base URL from the provider\'s docs.')"
          />
          <Password
            v-model="form.other_key"
            :label="__('API key')"
            :placeholder="form.has_other_key ? __('Saved. Leave blank to keep it.') : ''"
            :description="presetOf(form.other_url)?.keyHelp || __('From your provider\'s dashboard.')"
          />
        </template>
        <template v-else>
          <Password
            v-model="form.openai_key"
            :label="__('OpenAI API key')"
            :placeholder="form.has_openai_key ? __('Saved. Leave blank to keep it.') : 'sk-…'"
            :description="__('From platform.openai.com → API keys.')"
          />
          <FormControl
            v-model="form.openai_model"
            type="text"
            :label="__('OpenAI model')"
            :placeholder="form.defaults.openai_model"
            :description="__('Leave empty to use {0}.').format(form.defaults.openai_model)"
          />
        </template>
        <FormControl
          v-model="form.max_tokens"
          type="number"
          :label="__('Max tokens per reply')"
          :description="
            __('The longest answer the AI can write, from 1,024 to 64,000. Higher allows longer answers and costs more when used.')
          "
        />
        <div class="flex items-start justify-between gap-4 rounded-4 border border-outline-gray-2 p-3">
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink-gray-8">{{ __('Agents sign in to other sites themselves') }}</p>
            <p class="mt-0.5 text-sm text-ink-gray-6">
              {{
                __(
                  'When FAC runs on another site, each agent signs in there once from the Assistant panel, so they only see and change what their own account allows. Turn off to let everyone use the account that connected the site.',
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
                  'Read looks records up. Write updates, submits and runs workflows on existing records. Create makes new records and dashboards. Write and create always wait for the agent to confirm. Code, database queries and deleting are never allowed.',
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
import { onMounted, reactive, ref } from 'vue'
import {
  Button,
  Checkbox,
  ErrorMessage,
  FormControl,
  FormLabel,
  Password,
  ScrollArea,
  SettingsBody,
  SettingsHeader,
  SettingsRow,
  Skeleton,
  Switch,
  TabButtons,
  Tooltip,
  toast,
} from 'frappe-ui'
import LinkField from '@/components/Common/LinkField.vue'
import { assistantSettings, assistantStatus, saveAssistantSettings } from '@/data/assistant'
import { integrations } from '@/data/integrations'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ dialog: { type: Boolean, default: false } })
const emit = defineEmits(['saved'])

const RIGHTS = [
  { key: 'read', label: __('Read'), hint: __('Look up records, reports and files') },
  { key: 'write', label: __('Write'), hint: __('Update, submit and run workflows on existing records') },
  { key: 'create', label: __('Create'), hint: __('Create new records and dashboards') },
]

function setRight(row, key, value) {
  row[key] = !!value
  if (value && key !== 'read') row.read = true
}

const installCommand =
  'bench get-app https://github.com/buildswithpaul/Frappe_Assistant_Core\nbench --site <site> install-app frappe_assistant_core'

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const ui = useUI()

const form = reactive({
  enabled: false,
  provider: 'Claude',
  openai_model: '',
  claude_model: '',
  max_tokens: 16000,
  agent_signin: true,
  defaults: { claude_model: 'claude-opus-5', openai_model: 'gpt-5' },
  anthropic_key: '',
  openai_key: '',
  has_anthropic_key: false,
  has_openai_key: false,
  roles: [],
  sites: [],
  other_name: '',
  other_url: '',
  other_model: '',
  other_key: '',
  has_other_key: false,
})

const PRESETS = [
  {
    name: 'Gemini',
    url: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    model: 'gemini-2.5-flash',
    keyHelp: 'From aistudio.google.com → Get API key.',
  },
  { name: 'OpenRouter', url: 'https://openrouter.ai/api/v1', model: 'google/gemini-2.5-flash', keyHelp: 'From openrouter.ai → Keys.' },
  { name: 'Groq', url: 'https://api.groq.com/openai/v1', model: 'llama-3.3-70b-versatile', keyHelp: 'From console.groq.com → API keys.' },
  { name: 'Mistral', url: 'https://api.mistral.ai/v1', model: 'mistral-large-latest', keyHelp: 'From console.mistral.ai → API keys.' },
  { name: 'DeepSeek', url: 'https://api.deepseek.com/v1', model: 'deepseek-chat', keyHelp: 'From platform.deepseek.com → API keys.' },
  {
    name: 'Ollama',
    url: 'http://localhost:11434/v1',
    model: 'llama3.1',
    keyHelp: 'Ollama ignores the key. Enter any text, such as ollama.',
  },
]

function presetOf(url) {
  return PRESETS.find((preset) => preset.url === url)
}

function usePreset(preset) {
  form.other_name = preset.name
  form.other_url = preset.url
  if (!form.other_model) form.other_model = preset.model
}

function apply(data) {
  Object.assign(form, {
    ...data,
    anthropic_key: '',
    openai_key: '',
    other_key: '',
    roles: (data.roles || []).map((row) => ({ ...row })),
    sites: data.sites || [],
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
        provider: form.provider,
        openai_model: form.openai_model,
        claude_model: form.claude_model,
        max_tokens: Number(form.max_tokens) || 16000,
        anthropic_key: form.anthropic_key || undefined,
        openai_key: form.openai_key || undefined,
        other_name: form.other_name,
        other_url: form.other_url,
        other_model: form.other_model,
        other_key: form.other_key || undefined,
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

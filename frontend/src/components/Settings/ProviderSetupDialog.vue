<template>
  <ResponsiveDialog v-model:open="open" :title="title" size="xl">
    <template #default>
      <div v-if="!preset" class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <button
          v-for="item in presets"
          :key="item.id"
          type="button"
          class="flex flex-col items-start gap-1 rounded-4 border border-outline-gray-2 p-3 text-left hover:bg-surface-gray-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-4"
          @click="pick(item)"
        >
          <span class="flex w-full items-center justify-between gap-2">
            <span class="text-base font-medium text-ink-gray-8">{{ item.name || __('Custom') }}</span>
            <Badge v-if="item.configured" theme="green" variant="subtle" size="sm" :label="__('Added')" />
          </span>
          <span class="text-sm text-ink-gray-6">{{ item.tagline }}</span>
        </button>
      </div>

      <div v-else class="flex flex-col gap-4">
        <p class="text-sm text-ink-gray-6">{{ preset.blurb }}</p>

        <div v-if="preset.custom" class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormControl v-model="form.name" type="text" :label="__('Name')" placeholder="Ollama" />
          <FormControl v-model="form.api_base" type="text" :label="__('API address')" placeholder="http://localhost:11434/v1" />
        </div>

        <Password v-model="form.api_key" :label="__('API key')" autocomplete="new-password" :placeholder="keyPlaceholder" />

        <details v-if="preset.key_steps.length" class="group rounded-4 border border-outline-gray-2 px-3 py-2.5">
          <summary class="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-ink-gray-8">
            {{ __('How do I get a key?') }}
            <span class="lucide-chevron-down size-4 text-ink-gray-5 transition-transform group-open:rotate-180" aria-hidden="true" />
          </summary>
          <ol class="mt-2 list-decimal space-y-1 pl-5 text-sm text-ink-gray-6">
            <li v-for="step in preset.key_steps" :key="step">{{ step }}</li>
          </ol>
          <a
            v-if="preset.key_url"
            :href="preset.key_url"
            target="_blank"
            rel="noopener noreferrer"
            class="mt-2 inline-flex items-center gap-1 text-sm text-ink-gray-8 underline"
          >
            {{ __('Open the key page') }}
            <span class="lucide-external-link size-3.5" aria-hidden="true" />
          </a>
        </details>

        <div class="flex flex-col gap-2">
          <FormLabel :label="__('Models')" />
          <label
            v-for="model in preset.models"
            :key="model.model_id"
            class="flex cursor-pointer items-start gap-2.5 rounded-4 border border-outline-gray-2 p-2.5"
          >
            <Checkbox :model-value="form.models.includes(model.model_id)" @update:model-value="(value) => toggle(model.model_id, value)" />
            <span class="min-w-0">
              <span class="flex items-center gap-1.5 text-sm font-medium text-ink-gray-8">
                {{ model.label }}
                <Badge v-if="model.recommended" theme="blue" variant="subtle" size="sm" :label="__('Recommended')" />
              </span>
              <span class="block text-sm text-ink-gray-5">{{ model.note }}</span>
            </span>
          </label>
          <FormControl
            v-model="form.extra"
            type="text"
            :label="preset.models.length ? __('Other model IDs') : __('Model IDs')"
            :placeholder="preset.custom ? 'llama3.1' : ''"
            :description="__('As the provider names them. Separate several with commas.')"
          />
        </div>

        <div v-if="result" class="flex items-start gap-2.5 rounded-4 p-3 text-sm" :class="RESULT_CLASS[result.severity]">
          <span :class="[RESULT_ICON[result.severity], 'mt-0.5 size-4 shrink-0']" aria-hidden="true" />
          <p>{{ result.message }}</p>
        </div>
        <ErrorMessage :message="error" />
      </div>
    </template>

    <template v-if="preset" #actions>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <Button variant="ghost" icon-left="lucide-arrow-left" :label="__('Back')" @click="back" />
        <div class="flex gap-2">
          <Button :label="__('Test key')" :loading="testing" :disabled="!chosen.length" @click="test" />
          <Button variant="solid" :label="__('Add provider')" :loading="saving" :disabled="!chosen.length" @click="add" />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Badge, Button, Checkbox, ErrorMessage, FormControl, FormLabel, Password, call } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ presets: { type: Array, default: () => [] } })
const emit = defineEmits(['added'])
const open = defineModel('open', { type: Boolean, default: false })

const API = 'onechat.assistant.setup'
const RESULT_CLASS = {
  ok: 'bg-surface-green-1 text-ink-green-7',
  warn: 'bg-surface-amber-1 text-ink-amber-8',
  error: 'bg-surface-red-1 text-ink-red-7',
}
const RESULT_ICON = { ok: 'lucide-circle-check', warn: 'lucide-triangle-alert', error: 'lucide-circle-x' }

const preset = ref(null)
const testing = ref(false)
const saving = ref(false)
const error = ref('')
const result = ref(null)
const form = reactive({ name: '', api_base: '', api_key: '', models: [], extra: '' })

const title = computed(() =>
  preset.value ? __('Connect {0}').format(preset.value.name || __('a custom provider')) : __('Add an AI provider'),
)

const keyPlaceholder = computed(() => {
  if (preset.value?.has_key) return __('Saved. Leave blank to keep it.')
  if (preset.value?.custom) return __('Optional')
  return preset.value?.key_prefix ? `${preset.value.key_prefix}…` : ''
})

const chosen = computed(() => [
  ...new Set([
    ...form.models,
    ...form.extra
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean),
  ]),
])

watch(open, (value) => value && back())

function pick(item) {
  preset.value = item
  Object.assign(form, {
    name: item.name,
    api_base: '',
    api_key: '',
    extra: '',
    models: item.models.filter((model) => model.recommended).map((model) => model.model_id),
  })
  result.value = null
  error.value = ''
}

function back() {
  preset.value = null
  result.value = null
  error.value = ''
}

function toggle(modelId, value) {
  form.models = value ? [...form.models, modelId] : form.models.filter((id) => id !== modelId)
}

function payload() {
  return { preset: preset.value.id, api_key: form.api_key, api_base: form.api_base, name: form.name }
}

async function test() {
  testing.value = true
  error.value = ''
  try {
    result.value = await call(`${API}.verify_key`, { ...payload(), model_id: chosen.value[0] })
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    testing.value = false
  }
}

async function add() {
  saving.value = true
  error.value = ''
  try {
    emit('added', await call(`${API}.add_provider`, { ...payload(), models: JSON.stringify(chosen.value) }))
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}
</script>

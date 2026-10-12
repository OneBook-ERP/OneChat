<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="label" :required="required" />
      <Button v-if="!python" size="sm" variant="ghost" :loading="checking" :disabled="!modelValue" :label="__('Check')" @click="check" />
    </div>
    <FormControl type="text" class="font-mono" :model-value="modelValue" :placeholder="placeholder" @update:model-value="update">
      <template #prefix>
        <span class="lucide-braces size-3.5 text-ink-gray-4" aria-hidden="true" />
      </template>
    </FormControl>
    <div class="flex flex-wrap items-center gap-1">
      <button
        v-for="chip in chips"
        :key="chip"
        type="button"
        class="rounded-1 bg-surface-gray-2 px-1.5 py-0.5 font-mono text-xs text-ink-gray-6 hover:bg-surface-gray-3"
        @click="insert(chip)"
      >
        {{ chip }}
      </button>
    </div>
    <p v-if="result" class="text-xs" :class="result.valid ? 'text-ink-green-6' : 'text-ink-red-6'">{{ result.text }}</p>
    <p v-else class="text-xs text-ink-gray-5">{{ hint }}</p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, FormControl, FormLabel, call } from 'frappe-ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  required: { type: Boolean, default: false },
  python: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const checking = ref(false)
const result = ref(null)

const chips = computed(() =>
  props.python
    ? ["context['vars']", "context['erp']['doc']", '==']
    : ['context.erp.doc.', 'context.erp.name', 'context.vars.', 'context.last_output.'],
)

const hint = computed(() =>
  props.python
    ? __('A Python expression evaluated against context, for example {0}').format("context['vars']['total'] > 5000")
    : __('context.path, doc.field, doctype or docname are read from the run; anything else is used as typed.'),
)

const KINDS = {
  doc_field: 'Reads a field of the document.',
  context_path: 'Reads a value from the run context.',
  context_variable: 'Reads a value about the run.',
  literal: 'Used exactly as typed.',
}

watch(
  () => props.modelValue,
  () => (result.value = null),
)

function update(value) {
  emit('update:modelValue', value)
}

function insert(chip) {
  const current = String(props.modelValue || '')
  const joiner = current && !current.endsWith(' ') && props.python ? ' ' : ''

  update(props.python || !current ? `${current}${joiner}${chip}` : chip)
}

async function check() {
  checking.value = true
  try {
    const data = await call('onechat.automation.flow_helpers.validate_expression', { expression: String(props.modelValue || '') })
    result.value = data.valid
      ? { valid: true, text: __(KINDS[data.type] || 'Looks fine.') }
      : { valid: false, text: data.error || __('This expression is not valid.') }
  } catch (err) {
    result.value = { valid: false, text: errorMessage(err) }
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <div v-if="template" class="flex flex-col gap-2">
    <FormLabel :label="label" />
    <div v-if="body" class="whitespace-pre-wrap rounded-4 bg-surface-gray-1 px-2.5 py-2 text-sm text-ink-gray-7">{{ body }}</div>
    <p v-if="loading" class="text-xs text-ink-gray-5">{{ __('Loading template…') }}</p>
    <p v-else-if="!count" class="text-xs text-ink-gray-5">{{ __('This template has no variables.') }}</p>
    <MessageField
      v-for="index in count"
      :key="index"
      compact
      :label="`{{${index}}}`"
      :model-value="values[index - 1] || ''"
      :placeholder="scope === 'record' ? '{{record.customer_name}}' : '{{first_name}}'"
      @update:model-value="(value) => set(index - 1, value)"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { FormLabel } from 'frappe-ui'
import MessageField from './MessageField.vue'
import { placeholderCount, templateDetails } from './api'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  template: { type: String, default: '' },
  label: { type: String, default: '' },
  scope: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const details = ref(null)
const loading = ref(false)

const body = computed(() => details.value?.template || '')
const count = computed(() => placeholderCount(body.value))
const values = computed(() => (props.modelValue || []).map((value) => (typeof value === 'object' ? value?.value || '' : value)))

watch(
  () => props.template,
  async (name) => {
    details.value = null
    if (!name) return
    loading.value = true
    try {
      details.value = await templateDetails(name)
    } catch {
      details.value = null
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

function set(index, value) {
  const list = [...values.value]
  while (list.length < count.value) list.push('')
  list[index] = value
  emit('update:modelValue', list.slice(0, count.value))
}
</script>

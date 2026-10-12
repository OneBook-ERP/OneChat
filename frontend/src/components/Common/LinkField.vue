<template>
  <div class="flex flex-col gap-1.5">
    <FormLabel v-if="label" :label="label" :required="required" />
    <Combobox
      :model-value="modelValue"
      :options="options"
      :filterable="false"
      :loading="results.loading"
      :placeholder="placeholder || __('Search {0}').format(__(doctype))"
      :disabled="disabled"
      @update:query="lookup"
      @update:model-value="(value) => emit('update:modelValue', value)"
    />
    <p v-if="description" class="text-xs text-ink-gray-5">{{ description }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { Combobox, FormLabel, createResource, debounce } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: [String, Number], default: null },
  doctype: { type: String, required: true },
  filters: { type: Object, default: () => ({}) },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  description: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const results = createResource({
  url: 'onechat.integrations.records.search',
  makeParams: (params) => ({
    doctype: props.doctype,
    txt: params?.txt || '',
    filters: props.filters,
    page_length: 20,
  }),
})

const DESCRIPTION_LIMIT = 70

function plain(value) {
  const text = String(value || '')
    .replace(/<br\s*\/?>/gi, ', ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s*,\s*(,\s*)+/g, ', ')
    .replace(/\s+/g, ' ')
    .replace(/^[\s,]+|[\s,]+$/g, '')
  return text.length > DESCRIPTION_LIMIT ? `${text.slice(0, DESCRIPTION_LIMIT - 1).trimEnd()}…` : text
}

const options = computed(() => {
  const rows = (results.data || []).map((row) => {
    const detail = plain(row.description)
    const label = row.label && row.label !== row.value ? row.label : ''
    return {
      label: label || row.value,
      value: row.value,
      description: [label ? row.value : '', detail !== row.value ? detail : ''].filter(Boolean).join(' · ') || undefined,
    }
  })

  if (props.modelValue && !rows.some((row) => row.value === props.modelValue)) {
    rows.unshift({ label: String(props.modelValue), value: props.modelValue })
  }

  return rows
})

const lookup = debounce((txt) => results.submit({ txt }), 250)

onMounted(() => results.submit({ txt: '' }))
</script>

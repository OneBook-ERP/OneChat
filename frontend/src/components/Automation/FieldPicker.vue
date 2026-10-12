<template>
  <Combobox
    :model-value="modelValue"
    :options="options"
    :label="label"
    :description="description"
    :required="required"
    :loading="loading"
    :disabled="disabled"
    :placeholder="placeholder || (doctype ? __('Pick a field') : __('Pick a DocType first'))"
    :empty-text="doctype ? __('No matching fields') : __('Pick a DocType first')"
    @update:model-value="(value) => emit('update:modelValue', value ?? '')"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Combobox } from 'frappe-ui'
import { NO_VALUE_TYPES, doctypeFields } from '@/components/FlowBuilder/api'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: String, default: '' },
  doctype: { type: String, default: '' },
  label: { type: String, default: '' },
  description: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  fieldtypes: { type: Array, default: () => [] },
  extra: { type: Array, default: () => [] },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const fields = ref([])
const loading = ref(false)

watch(
  () => props.doctype,
  async (doctype) => {
    fields.value = []
    if (!doctype) return

    loading.value = true
    try {
      fields.value = await doctypeFields(doctype)
    } catch {
      fields.value = []
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

const options = computed(() => {
  const rows = fields.value
    .filter((field) => !NO_VALUE_TYPES.includes(field.fieldtype))
    .filter((field) => !props.fieldtypes.length || props.fieldtypes.includes(field.fieldtype))
    .map((field) => ({
      label: field.label || field.fieldname,
      value: field.fieldname,
      description: `${field.fieldname} · ${field.fieldtype}`,
    }))
    .concat(props.extra)

  if (props.modelValue && !rows.some((row) => row.value === props.modelValue)) {
    rows.unshift({ label: props.modelValue, value: props.modelValue })
  }

  return [
    ...rows,
    {
      type: 'custom',
      key: 'use-typed',
      label: __('Use typed field name'),
      icon: 'lucide-corner-down-left',
      condition: ({ query }) => !!query && !rows.some((row) => row.value === query),
      onClick: ({ query }) => emit('update:modelValue', query.trim()),
    },
  ]
})
</script>

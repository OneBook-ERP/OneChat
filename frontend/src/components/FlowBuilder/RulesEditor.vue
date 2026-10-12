<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="label" :required="required" />
      <Select
        v-if="rules.length > 1"
        size="sm"
        class="w-28"
        :model-value="match"
        :options="[
          { label: __('All match'), value: 'all' },
          { label: __('Any matches'), value: 'any' },
        ]"
        @update:model-value="(value) => emit('update:modelValue', { ...current, match: value })"
      />
    </div>

    <p v-if="!rules.length" class="rounded-4 border border-dashed border-outline-gray-2 px-3 py-3 text-center text-xs text-ink-gray-5">
      {{ optional ? __('No conditions, so it always runs') : __('Add a condition') }}
    </p>

    <div v-for="(rule, index) in rules" :key="index" class="flex flex-col gap-1.5 rounded-4 bg-surface-gray-1 p-2">
      <div class="flex items-center gap-1.5">
        <Select
          v-if="!SPECIAL.includes(rule.operator)"
          class="min-w-0 flex-1"
          :model-value="rule.field"
          :options="fieldOptions"
          :placeholder="__('Pick a value')"
          @update:model-value="(value) => set(index, { field: value })"
        />
        <TruncatedText v-else class="min-w-0 flex-1 truncate px-1 text-sm text-ink-gray-7" :text="__(operatorLabel(rule.operator))" />
        <Button variant="ghost" icon="lucide-x" :label="__('Remove')" @click="remove(index)" />
      </div>
      <Select :model-value="rule.operator" :options="operators" @update:model-value="(value) => set(index, { operator: value })" />
      <LinkField
        v-if="rule.operator === 'has_label'"
        :model-value="rule.value"
        doctype="OneChat Label"
        @update:model-value="(value) => set(index, { value })"
      />
      <FormControl
        type="text"
        v-else-if="!NO_VALUE.includes(rule.operator)"
        :model-value="rule.value"
        :placeholder="rule.operator === 'is_one_of' ? __('Chennai, Madurai') : __('Value')"
        @update:model-value="(value) => set(index, { value })"
      />
    </div>

    <Button variant="subtle" icon-left="lucide-plus" :label="__('Add condition')" @click="add" />
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, inject, ref } from 'vue'
import { Button, FormControl, FormLabel, Select } from 'frappe-ui'
import LinkField from '@/components/Common/LinkField.vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: [Object, Array], default: () => ({}) },
  label: { type: String, default: '' },
  required: { type: Boolean, default: false },
  optional: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const OPERATORS = [
  { label: 'is', value: 'equals' },
  { label: 'is not', value: 'not_equals' },
  { label: 'contains', value: 'contains' },
  { label: 'does not contain', value: 'not_contains' },
  { label: 'starts with', value: 'starts_with' },
  { label: 'is more than', value: 'greater_than' },
  { label: 'is less than', value: 'less_than' },
  { label: 'is one of', value: 'is_one_of' },
  { label: 'is empty', value: 'is_empty' },
  { label: 'is not empty', value: 'is_not_empty' },
  { label: 'Conversation has label', value: 'has_label' },
  { label: 'It is business hours', value: 'in_business_hours' },
]
const SPECIAL = ['has_label', 'in_business_hours']
const NO_VALUE = ['is_empty', 'is_not_empty', 'in_business_hours']

const variables = inject('flowVariables', ref([]))

const current = computed(() => (Array.isArray(props.modelValue) ? { rules: props.modelValue } : props.modelValue || {}))
const rules = computed(() => current.value.rules || [])
const match = computed(() => current.value.match || 'all')

const operators = computed(() => OPERATORS.map((row) => ({ label: __(row.label), value: row.value })))

const fieldOptions = computed(() => {
  const known = variables.value.map((row) => ({ label: `${__(row.group)} · ${__(row.label)}`, value: row.token }))
  const used = rules.value.map((rule) => rule.field).filter((field) => field && !known.some((row) => row.value === field))
  return [...known, ...used.map((field) => ({ label: field, value: field }))]
})

function operatorLabel(value) {
  return OPERATORS.find((row) => row.value === value)?.label || value
}

function commit(list) {
  emit('update:modelValue', { match: match.value, rules: list })
}

function set(index, patch) {
  commit(rules.value.map((rule, position) => (position === index ? { ...rule, ...patch } : rule)))
}

function add() {
  commit([...rules.value, { field: fieldOptions.value[0]?.value || '', operator: 'equals', value: '' }])
}

function remove(index) {
  commit(rules.value.filter((_, position) => position !== index))
}
</script>

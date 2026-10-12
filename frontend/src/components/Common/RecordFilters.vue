<template>
  <div class="flex flex-col gap-2">
    <p v-if="!rows.length" class="text-sm text-ink-gray-5">{{ emptyText || __('No filters. Every record is included.') }}</p>

    <div v-for="(row, index) in rows" :key="row.id" class="flex flex-wrap items-center gap-2">
      <span class="w-10 shrink-0 text-sm text-ink-gray-5">{{ index ? __('and') : __('Where') }}</span>
      <Select
        class="min-w-0 flex-1 sm:max-w-52"
        :options="fieldOptions"
        :model-value="row.field"
        :placeholder="__('Field')"
        @update:model-value="(value) => setField(row, value)"
      />
      <Select
        class="w-40 shrink-0"
        :options="operatorsFor(row)"
        :model-value="row.op"
        @update:model-value="(value) => update(row, { op: value })"
      />
      <template v-if="needsValue(row)">
        <Select
          v-if="kindOf(row) === 'select'"
          class="min-w-0 flex-1"
          :options="choicesOf(row)"
          :model-value="row.value"
          :placeholder="__('Value')"
          @update:model-value="(value) => update(row, { value })"
        />
        <Select
          v-else-if="kindOf(row) === 'check'"
          class="min-w-0 flex-1"
          :options="[
            { label: __('Yes'), value: '1' },
            { label: __('No'), value: '0' },
          ]"
          :model-value="String(row.value ?? '')"
          @update:model-value="(value) => update(row, { value })"
        />
        <div v-else-if="kindOf(row) === 'link'" class="min-w-0 flex-1">
          <LinkField
            :key="`${row.id}-${row.field}`"
            :doctype="fieldOf(row).options"
            :model-value="row.value"
            @update:model-value="(value) => update(row, { value })"
          />
        </div>
        <FormControl
          v-else
          class="min-w-0 flex-1"
          :type="kindOf(row) === 'date' ? 'date' : kindOf(row) === 'number' ? 'number' : 'text'"
          :model-value="row.value"
          :placeholder="__('Value')"
          @update:model-value="(value) => update(row, { value })"
        />
      </template>
      <div v-else class="min-w-0 flex-1" />
      <Button variant="ghost" icon="lucide-x" :label="__('Remove filter')" @click="remove(row)" />
    </div>

    <div>
      <Button size="sm" variant="subtle" icon-left="lucide-plus" :label="__('Add filter')" :disabled="!fields.length" @click="add" />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, FormControl, Select } from 'frappe-ui'
import LinkField from './LinkField.vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  fields: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
  emptyText: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const NUMBER = ['Int', 'Float', 'Currency', 'Percent', 'Rating', 'Duration']
const DATE = ['Date', 'Datetime']
const OPERATORS = {
  text: ['equals', 'not_equals', 'contains', 'not_contains', 'set', 'not_set'],
  select: ['equals', 'not_equals', 'set', 'not_set'],
  link: ['equals', 'not_equals', 'set', 'not_set'],
  check: ['equals'],
  number: ['equals', 'not_equals', 'greater', 'less', 'at_least', 'at_most'],
  date: ['equals', 'after', 'before', 'on_or_after', 'on_or_before', 'set', 'not_set'],
}
const LABELS = {
  equals: 'is',
  not_equals: 'is not',
  contains: 'contains',
  not_contains: "doesn't contain",
  set: 'is set',
  not_set: 'is empty',
  greater: 'is more than',
  less: 'is less than',
  at_least: 'is at least',
  at_most: 'is at most',
  after: 'is after',
  before: 'is before',
  on_or_after: 'is on or after',
  on_or_before: 'is on or before',
}
const TO_FRAPPE = {
  equals: '=',
  not_equals: '!=',
  greater: '>',
  after: '>',
  less: '<',
  before: '<',
  at_least: '>=',
  on_or_after: '>=',
  at_most: '<=',
  on_or_before: '<=',
}

let counter = 0
const rows = ref([])

const fieldOptions = computed(() => props.fields.map((field) => ({ label: field.label || field.fieldname, value: field.fieldname })))

function fieldOf(row) {
  return props.fields.find((field) => field.fieldname === row.field) || { fieldtype: 'Data' }
}

function kindOf(row) {
  const type = fieldOf(row).fieldtype
  if (type === 'Select') return 'select'
  if (type === 'Check') return 'check'
  if (type === 'Link' && fieldOf(row).options) return 'link'
  if (NUMBER.includes(type)) return 'number'
  if (DATE.includes(type)) return 'date'
  return 'text'
}

function operatorsFor(row) {
  return OPERATORS[kindOf(row)].map((value) => ({ label: __(LABELS[value]), value }))
}

function choicesOf(row) {
  return String(fieldOf(row).options || '')
    .split('\n')
    .filter(Boolean)
    .map((value) => ({ label: __(value), value }))
}

function needsValue(row) {
  return !['set', 'not_set'].includes(row.op)
}

function toRow([field, operator, value]) {
  const text = String(value ?? '')
  let op = 'equals'
  let plain = value
  if (operator === 'is') op = value === 'not set' ? 'not_set' : 'set'
  else if (operator === 'like' || operator === 'not like') {
    op = operator === 'like' ? 'contains' : 'not_contains'
    plain = text.replace(/^%|%$/g, '')
  } else {
    const found = Object.entries(TO_FRAPPE).find(([, symbol]) => symbol === operator)
    op = found ? found[0] : 'equals'
  }
  return { id: ++counter, field, op, value: plain ?? '' }
}

function fromRows(list) {
  return list
    .filter((row) => row.field)
    .map((row) => {
      if (row.op === 'set') return [row.field, 'is', 'set']
      if (row.op === 'not_set') return [row.field, 'is', 'not set']
      if (row.op === 'contains') return [row.field, 'like', `%${row.value ?? ''}%`]
      if (row.op === 'not_contains') return [row.field, 'not like', `%${row.value ?? ''}%`]
      const value = kindOf(row) === 'number' || kindOf(row) === 'check' ? Number(row.value || 0) : row.value
      return [row.field, TO_FRAPPE[row.op] || '=', value]
    })
}

function sync() {
  emit('update:modelValue', fromRows(rows.value))
}

function add() {
  const first = props.fields.find((field) => field.fieldname !== 'name') || props.fields[0]
  rows.value.push({ id: ++counter, field: first?.fieldname || '', op: 'equals', value: '' })
  sync()
}

function remove(row) {
  rows.value = rows.value.filter((item) => item !== row)
  sync()
}

function setField(row, field) {
  Object.assign(row, { field, value: '' })
  if (!operatorsFor(row).some((option) => option.value === row.op)) row.op = operatorsFor(row)[0].value
  sync()
}

function update(row, changes) {
  Object.assign(row, changes)
  sync()
}

watch(
  () => props.modelValue,
  (value) => {
    if (JSON.stringify(value || []) === JSON.stringify(fromRows(rows.value))) return
    rows.value = (value || []).filter((item) => Array.isArray(item) && item.length >= 2).map(toRow)
  },
  { immediate: true, deep: true },
)
</script>

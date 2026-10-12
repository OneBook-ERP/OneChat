<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="label" />
      <Select
        v-if="mode === 'simple' && rules.length > 1"
        size="sm"
        class="w-32"
        :model-value="match"
        :options="[
          { label: __('All must match'), value: 'all' },
          { label: __('Any can match'), value: 'any' },
        ]"
        @update:model-value="(value) => commit(rules, value)"
      />
    </div>

    <template v-if="mode === 'simple'">
      <p v-if="!rules.length" class="rounded-4 border border-dashed border-outline-gray-2 px-3 py-3 text-center text-sm text-ink-gray-5">
        {{ emptyText }}
      </p>

      <div
        v-for="(rule, index) in rules"
        :key="index"
        class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-2 sm:flex-row sm:items-start"
      >
        <span v-if="index" class="shrink-0 px-1 pt-1.5 text-xs font-medium uppercase text-ink-gray-5 sm:w-9">
          {{ match === 'any' ? __('or') : __('and') }}
        </span>
        <span v-else class="hidden shrink-0 px-1 pt-1.5 text-xs font-medium uppercase text-ink-gray-5 sm:block sm:w-9">{{ __('if') }}</span>
        <Combobox
          class="min-w-0 sm:flex-1"
          :model-value="rule.field"
          :options="fieldOptions"
          :loading="loading"
          :placeholder="doctype ? __('Pick a field') : __('Pick a document type first')"
          @update:model-value="(value) => setField(index, value)"
        />
        <Select
          class="min-w-0 sm:w-40"
          :model-value="rule.operator"
          :options="operatorOptions(rule.field)"
          @update:model-value="(value) => set(index, { operator: value })"
        />
        <div v-if="!NO_VALUE.includes(rule.operator)" class="min-w-0 sm:flex-1">
          <Select
            v-if="choicesOf(rule.field) && rule.operator !== 'is_one_of'"
            :model-value="rule.value"
            :options="choicesOf(rule.field)"
            :placeholder="__('Pick a value')"
            @update:model-value="(value) => set(index, { value })"
          />
          <LinkField
            v-else-if="kindOf(typeOf(rule.field)) === 'link' && rule.operator !== 'is_one_of'"
            :model-value="rule.value"
            :doctype="metaOf(rule.field).options"
            @update:model-value="(value) => set(index, { value: value || '' })"
          />
          <FormControl
            v-else
            :type="inputType(rule)"
            :model-value="rule.value"
            :placeholder="rule.operator === 'is_one_of' ? __('Paid, Overdue') : __('Value')"
            @update:model-value="(value) => set(index, { value })"
          />
        </div>
        <Button variant="ghost" icon="lucide-x" :label="__('Remove condition')" class="self-end sm:self-start" @click="remove(index)" />
      </div>

      <div class="flex items-center justify-between gap-2">
        <Button variant="subtle" icon-left="lucide-plus" :label="__('Add condition')" :disabled="!doctype" @click="add" />
        <Button variant="ghost" size="sm" icon-left="lucide-code" :label="__('Write as code')" @click="mode = 'code'" />
      </div>
    </template>

    <template v-else>
      <FormControl
        type="textarea"
        :rows="3"
        class="font-mono"
        :model-value="modelValue"
        placeholder="doc.grand_total > 0"
        @update:model-value="(value) => emit('update:modelValue', value)"
      />
      <div class="flex flex-wrap items-start justify-between gap-2">
        <p class="min-w-0 flex-1 text-xs leading-5 text-ink-gray-5">
          <slot name="code-help" />
        </p>
        <Button
          variant="ghost"
          size="sm"
          icon-left="lucide-list-filter"
          :label="parse(modelValue) ? __('Use simple conditions') : __('Start over with simple conditions')"
          @click="toSimple"
        />
      </div>
      <p v-if="modelValue && !parse(modelValue)" class="text-xs text-ink-amber-7">
        {{ __('This condition is too advanced for simple mode. Starting over clears it.') }}
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Combobox, FormControl, FormLabel, Select } from 'frappe-ui'
import LinkField from '@/components/Common/LinkField.vue'
import { NO_VALUE_TYPES, doctypeFields } from '@/components/FlowBuilder/api'
import { NO_VALUE, OPERATOR_LABELS, compile, kindOf, operatorsFor, parse } from '@/utils/condition'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: String, default: '' },
  doctype: { type: String, default: '' },
  label: { type: String, default: '' },
  emptyText: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const STANDARD = [
  {
    fieldname: 'docstatus',
    label: 'Document status',
    fieldtype: 'Int',
    choices: [
      { label: 'Draft', value: '0' },
      { label: 'Submitted', value: '1' },
      { label: 'Cancelled', value: '2' },
    ],
  },
  { fieldname: 'owner', label: 'Created by', fieldtype: 'Link', options: 'User' },
  { fieldname: 'name', label: 'ID', fieldtype: 'Data' },
]

const fields = ref([])
const loading = ref(false)
const mode = ref('simple')
const rules = ref([])
const match = ref('all')
const emitted = ref(null)

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

const meta = computed(() => {
  const out = {}
  for (const field of [...fields.value.filter((row) => !NO_VALUE_TYPES.includes(row.fieldtype)), ...STANDARD]) {
    out[field.fieldname] ||= field
  }
  return out
})

const types = computed(() => Object.fromEntries(Object.values(meta.value).map((field) => [field.fieldname, field.fieldtype])))

const fieldOptions = computed(() => {
  const rows = Object.values(meta.value).map((field) => ({
    label: __(field.label || field.fieldname),
    value: field.fieldname,
    description: field.fieldname,
  }))
  const used = rules.value.map((rule) => rule.field).filter((field) => field && !meta.value[field])
  return [...rows, ...[...new Set(used)].map((field) => ({ label: field, value: field }))]
})

function metaOf(fieldname) {
  return meta.value[fieldname] || {}
}

function typeOf(fieldname) {
  return metaOf(fieldname).fieldtype || 'Data'
}

function choicesOf(fieldname) {
  const field = metaOf(fieldname)
  if (field.choices) return field.choices.map((row) => ({ label: __(row.label), value: row.value }))
  if (field.fieldtype !== 'Select') return null

  const values = String(field.options || '')
    .split('\n')
    .map((value) => value.trim())
    .filter(Boolean)
  return values.map((value) => ({ label: __(value), value }))
}

function operatorOptions(fieldname) {
  return operatorsFor(typeOf(fieldname)).map((value) => ({ label: __(OPERATOR_LABELS[value]), value }))
}

function inputType(rule) {
  if (rule.operator === 'is_one_of') return 'text'
  const kind = kindOf(typeOf(rule.field))
  if (kind === 'number') return 'number'
  if (kind === 'date') return 'date'
  return 'text'
}

function normalize(rule) {
  const allowed = operatorsFor(typeOf(rule.field))
  if (allowed.includes(rule.operator)) return rule
  if (rule.operator === 'is_checked') return { ...rule, operator: 'equals', value: '1' }
  if (rule.operator === 'is_not_checked') return { ...rule, operator: 'not_equals', value: '1' }
  return rule
}

function load(expression) {
  const parsed = parse(expression)
  if (!parsed) {
    mode.value = 'code'
    return
  }
  mode.value = 'simple'
  match.value = parsed.match
  rules.value = parsed.rules
}

watch(
  () => props.modelValue,
  (value) => {
    if (value === emitted.value) return
    if (mode.value === 'code' && value) return
    load(value)
  },
  { immediate: true },
)

watch(meta, () => {
  rules.value = rules.value.map(normalize)
})

function commit(list, how = match.value) {
  rules.value = list
  match.value = how
  emitted.value = compile({ match: how, rules: list }, types.value)
  emit('update:modelValue', emitted.value)
}

function set(index, patch) {
  commit(rules.value.map((rule, position) => (position === index ? { ...rule, ...patch } : rule)))
}

function setField(index, field) {
  const allowed = operatorsFor(typeOf(field))
  const rule = rules.value[index]
  set(index, { field: field || '', operator: allowed.includes(rule.operator) ? rule.operator : allowed[0], value: '' })
}

function add() {
  const first = fieldOptions.value[0]?.value || ''
  commit([...rules.value, { field: '', operator: operatorsFor(typeOf(first))[0], value: '' }])
}

function remove(index) {
  commit(rules.value.filter((_, position) => position !== index))
}

function toSimple() {
  const parsed = parse(props.modelValue)
  if (parsed) {
    load(props.modelValue)
    emitted.value = props.modelValue
    return
  }
  mode.value = 'simple'
  commit([], 'all')
}
</script>

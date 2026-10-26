<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="label" />
      <Button size="sm" variant="ghost" icon-left="lucide-plus" :label="__('Add')" @click="add()" />
    </div>
    <p v-if="description" class="text-xs text-ink-gray-5">{{ description }}</p>

    <div v-if="missing.length" class="flex flex-wrap items-center gap-1.5 rounded-4 bg-surface-amber-1 px-2.5 py-2">
      <span class="text-xs text-ink-amber-8">{{ __('Required:') }}</span>
      <Button
        v-for="field in missing"
        :key="field.fieldname"
        size="sm"
        variant="subtle"
        icon-left="lucide-plus"
        :label="__(field.label || field.fieldname)"
        @click="add(field.fieldname)"
      />
    </div>

    <p v-if="!rows.length" class="rounded-4 border border-dashed border-outline-gray-2 px-3 py-3 text-center text-xs text-ink-gray-5">
      {{ doctype ? __('Add the fields to fill in.') : __('Nothing added yet') }}
    </p>

    <div v-for="(row, index) in rows" :key="row.id" class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-2">
      <div class="flex items-center gap-1.5">
        <FieldPicker
          v-if="doctype"
          class="min-w-0 flex-1"
          :model-value="row.key"
          :doctype="doctype"
          :placeholder="keyPlaceholder || __(keyLabel)"
          @update:model-value="(value) => setKey(index, value)"
        />
        <FormControl
          v-else
          type="text"
          class="min-w-0 flex-1"
          :model-value="row.key"
          :placeholder="keyPlaceholder || __(keyLabel)"
          @update:model-value="(value) => set(index, 'key', value)"
        />
        <Button variant="ghost" icon="lucide-x" :label="__('Remove')" @click="remove(index)" />
      </div>

      <TabButtons
        v-if="variables.length"
        size="sm"
        class="self-start"
        :model-value="row.mode"
        :options="[
          { label: __('Type a value'), value: 'fixed' },
          { label: __('Use from this flow'), value: 'flow' },
        ]"
        @update:model-value="(value) => setMode(index, value)"
      />

      <Combobox
        v-if="row.mode === 'flow'"
        :model-value="row.value"
        :options="variableOptions(row.value)"
        :placeholder="__('Pick a value')"
        @update:model-value="(value) => set(index, 'value', value || '')"
      />
      <template v-else>
        <Select
          v-if="kindOf(row) === 'select'"
          :model-value="row.value"
          :options="choices(row)"
          :placeholder="__('Pick a value')"
          @update:model-value="(value) => set(index, 'value', value)"
        />
        <LinkField
          v-else-if="kindOf(row) === 'link'"
          :model-value="row.value"
          :doctype="meta(row).options"
          @update:model-value="(value) => set(index, 'value', value || '')"
        />
        <div v-else-if="kindOf(row) === 'check'" class="flex items-center justify-between gap-2 px-1">
          <span class="text-sm text-ink-gray-7">{{ truthy(row.value) ? __('Yes') : __('No') }}</span>
          <Switch :model-value="truthy(row.value)" @update:model-value="(value) => set(index, 'value', value ? 1 : 0)" />
        </div>
        <FormControl
          v-else-if="kindOf(row) === 'date' || kindOf(row) === 'number'"
          :type="kindOf(row)"
          :model-value="row.value"
          @update:model-value="(value) => set(index, 'value', value)"
        />
        <MessageField
          v-else
          compact
          :model-value="String(row.value ?? '')"
          :placeholder="valuePlaceholder || __('Type the value')"
          :limit="0"
          @update:model-value="(value) => set(index, 'value', value)"
        />
      </template>
    </div>

    <p v-if="rows.length && variables.length" class="text-xs text-ink-gray-5">
      {{ __('Use from this flow takes a value the flow already knows, like an answer or a found record.') }}
    </p>
  </div>
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import { Button, Combobox, FormControl, FormLabel, Select, Switch, TabButtons } from 'frappe-ui'
import FieldPicker from '@/components/Automation/FieldPicker.vue'
import LinkField from '@/components/Common/LinkField.vue'
import MessageField from './MessageField.vue'
import { doctypeFields } from './api'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  label: { type: String, default: '' },
  doctype: { type: String, default: '' },
  keyLabel: { type: String, default: 'Field' },
  valueLabel: { type: String, default: 'Value' },
  keyPlaceholder: { type: String, default: '' },
  valuePlaceholder: { type: String, default: '' },
  showRequired: { type: Boolean, default: true },
  description: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const TOKEN = /^\{\{\s*[\w.]+\s*\}\}$/
const NUMBER_TYPES = ['Int', 'Float', 'Currency', 'Percent']
const SKIP_REQUIRED = ['naming_series', 'amended_from']

const variables = inject('flowVariables', ref([]))
const rows = ref([])
const fields = ref([])
let seed = 0
let last = ''

const byName = computed(() => Object.fromEntries(fields.value.map((field) => [field.fieldname, field])))

const missing = computed(() => {
  if (!props.showRequired) return []
  const used = new Set(rows.value.map((row) => row.key))
  return fields.value.filter((field) => field.reqd && !used.has(field.fieldname) && !SKIP_REQUIRED.includes(field.fieldname)).slice(0, 8)
})

watch(
  () => props.doctype,
  async (doctype) => {
    fields.value = []
    if (!doctype) return
    try {
      fields.value = await doctypeFields(doctype)
    } catch {
      fields.value = []
    }
  },
  { immediate: true },
)

function modeOf(value) {
  return typeof value === 'string' && TOKEN.test(value.trim()) ? 'flow' : 'fixed'
}

watch(
  () => props.modelValue,
  (value) => {
    const incoming = JSON.stringify(value || {})
    if (incoming === last) return

    last = incoming
    rows.value = Object.entries(value || {}).map(([key, item]) => ({
      id: seed++,
      key,
      value: item && typeof item === 'object' ? JSON.stringify(item) : item,
      mode: modeOf(item),
    }))
  },
  { immediate: true, deep: true },
)

function meta(row) {
  return byName.value[row.key] || {}
}

function kindOf(row) {
  const type = meta(row).fieldtype
  if (typeof row.value === 'string' && row.value.includes('{{')) return 'text'
  if (type === 'Select') return 'select'
  if (type === 'Link') return 'link'
  if (type === 'Check') return 'check'
  if (type === 'Date') return 'date'
  if (NUMBER_TYPES.includes(type)) return 'number'
  return 'text'
}

function choices(row) {
  return String(meta(row).options || '')
    .split('\n')
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => ({ label: __(value), value }))
}

function truthy(value) {
  return value === true || value === 1 || value === '1'
}

function variableOptions(current) {
  const groups = new Map()
  for (const row of variables.value) {
    if (!groups.has(row.group)) groups.set(row.group, [])
    groups.get(row.group).push({ label: __(row.label), value: row.token })
  }
  const options = [...groups].map(([group, items]) => ({ group: __(group), options: items }))
  if (current && !variables.value.some((row) => row.token === current)) options.unshift({ label: current, value: current })
  return options
}

function commit() {
  const out = {}
  for (const row of rows.value) {
    const key = String(row.key || '').trim()
    if (key) out[key] = row.value ?? ''
  }
  last = JSON.stringify(out)
  emit('update:modelValue', out)
}

function set(index, part, value) {
  rows.value[index][part] = value ?? ''
  commit()
}

function setKey(index, value) {
  const row = rows.value[index]
  const before = meta(row).fieldtype
  row.key = value || ''
  if (row.mode === 'fixed' && before !== meta(row).fieldtype) row.value = ''
  commit()
}

function setMode(index, mode) {
  const row = rows.value[index]
  if (row.mode === mode) return
  row.mode = mode
  row.value = ''
  commit()
}

function add(key = '') {
  rows.value.push({ id: seed++, key, value: '', mode: 'fixed' })
  if (key) commit()
}

function remove(index) {
  rows.value.splice(index, 1)
  commit()
}
</script>

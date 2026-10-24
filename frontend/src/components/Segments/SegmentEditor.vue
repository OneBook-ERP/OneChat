<template>
  <ResponsiveDialog v-model:open="open" :title="name ? __('Edit segment') : __('New segment')" size="5xl">
    <template #default>
      <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div class="flex min-w-0 flex-col gap-4">
          <div class="grid gap-3 sm:grid-cols-2">
            <FormControl v-model="form.segment_name" type="text" :label="__('Name')" :placeholder="__('Loyal furniture buyers')" required />
            <FormControl v-model="form.description" type="text" :label="__('Description')" :placeholder="__('Optional')" />
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm text-ink-gray-6">{{ __('Contacts that match') }}</span>
            <TabButtons v-model="form.match" :options="matchOptions" />
            <span class="text-sm text-ink-gray-6">{{ __('of these rules') }}</span>
          </div>

          <div v-if="!fields.length" class="flex flex-col gap-2">
            <Skeleton v-for="index in 2" :key="index" class="h-9 w-full rounded-3" />
          </div>

          <ol v-else class="flex flex-col gap-2">
            <li
              v-for="(rule, index) in form.rules"
              :key="rule.id"
              class="flex flex-col gap-2 rounded-4 border border-outline-gray-1 p-2.5 sm:flex-row sm:items-center"
            >
              <span v-if="index" class="w-10 shrink-0 text-xs font-medium uppercase text-ink-gray-5 max-sm:hidden">
                {{ form.match === 'any' ? __('or') : __('and') }}
              </span>
              <span v-else class="w-10 shrink-0 text-xs font-medium uppercase text-ink-gray-5 max-sm:hidden">{{ __('where') }}</span>

              <Combobox
                class="sm:w-48"
                :model-value="rule.field"
                :options="optionsFor(rule)"
                :placeholder="__('Field')"
                @update:query="(value) => (rule.query = value)"
                @update:model-value="(value) => value && setField(rule, value)"
              >
                <template #group-label="{ group }">
                  <button
                    v-if="collapsible.has(group.group)"
                    type="button"
                    class="flex w-full items-center justify-between gap-2 text-left"
                    @pointerdown.prevent
                    @click.stop="toggleGroup(group.group)"
                  >
                    <span class="truncate">{{ group.group }}</span>
                    <span
                      :class="expanded.has(group.group) ? 'lucide-chevron-up' : 'lucide-chevron-down'"
                      class="size-3.5 shrink-0"
                      aria-hidden="true"
                    />
                  </button>
                  <template v-else>{{ group.group }}</template>
                </template>
              </Combobox>
              <Select
                v-if="rule.field"
                class="sm:w-40"
                :model-value="rule.op"
                :options="opOptions(rule)"
                @update:model-value="(value) => setOp(rule, value)"
              />

              <div v-if="rule.field && !NO_VALUE.includes(rule.op)" class="flex min-w-0 flex-1 items-center gap-2">
                <MultiSelect
                  v-if="['choice', 'labels'].includes(kind(rule))"
                  v-model="rule.value"
                  class="min-w-0 flex-1"
                  :options="choiceOptions(rule)"
                  :placeholder="__('Pick values')"
                />
                <template v-else-if="kind(rule) === 'number' && rule.op === 'between'">
                  <FormControl v-model="rule.value[0]" type="number" class="min-w-0 flex-1" :placeholder="__('From')" />
                  <span class="text-sm text-ink-gray-5">{{ __('and') }}</span>
                  <FormControl v-model="rule.value[1]" type="number" class="min-w-0 flex-1" :placeholder="__('To')" />
                </template>
                <template v-else-if="kind(rule) === 'date'">
                  <FormControl v-model="rule.value" type="number" min="1" class="w-24" />
                  <span class="text-sm text-ink-gray-6">{{ rule.op === 'over' ? __('days ago') : __('days') }}</span>
                </template>
                <FormControl
                  v-else
                  v-model="rule.value"
                  :type="kind(rule) === 'number' ? 'number' : 'text'"
                  class="min-w-0 flex-1"
                  :placeholder="__('Value')"
                />
              </div>
              <span v-else class="flex-1" />

              <Button
                variant="ghost"
                icon="lucide-x"
                class="self-end sm:self-auto"
                :label="__('Remove rule')"
                :disabled="form.rules.length === 1"
                @click="form.rules.splice(index, 1)"
              />
            </li>
          </ol>

          <div class="flex flex-wrap gap-2">
            <Button variant="subtle" icon-left="lucide-plus" :label="__('Add rule')" @click="addRule()" />
            <Dropdown :options="presetOptions">
              <Button variant="ghost" icon-left="lucide-wand-sparkles" :label="__('Start from an idea')" />
            </Dropdown>
          </div>
        </div>

        <aside class="flex min-w-0 flex-col gap-3 rounded-5 bg-surface-gray-1 p-4">
          <div>
            <p class="text-sm text-ink-gray-5">{{ __('Matching contacts') }}</p>
            <p class="flex items-baseline gap-2 text-3xl font-semibold tabular-nums text-ink-gray-9">
              {{ formatNumber(preview.count) }}
              <Spinner v-if="previewing" class="size-4 text-ink-gray-5" />
            </p>
            <p v-if="preview.reachable !== null && preview.reachable !== preview.count" class="text-sm text-ink-gray-6">
              {{ __('{0} can receive broadcasts; the rest opted out.').format(formatNumber(preview.reachable)) }}
            </p>
          </div>

          <ErrorMessage :message="previewError" />

          <ul v-if="preview.sample.length" class="flex flex-col gap-1">
            <li v-for="row in preview.sample" :key="row.name" class="flex items-center gap-2 rounded-3 bg-surface-base px-2 py-1.5">
              <Avatar :image="row.profile_image" :label="row.contact_name || row.mobile_no" size="sm" />
              <TruncatedText class="min-w-0 flex-1 truncate text-sm text-ink-gray-8" :text="row.contact_name || row.mobile_no" />
              <Badge v-if="row.value_group" size="sm" :theme="groupMeta(row.value_group).theme" :label="__(row.value_group)" />
              <span class="w-6 text-right text-xs tabular-nums text-ink-gray-5">{{ row.engagement_score || 0 }}</span>
            </li>
          </ul>
          <p v-else-if="!previewing" class="text-sm text-ink-gray-5">{{ __('No contacts match yet.') }}</p>
          <p v-if="preview.count > preview.sample.length" class="text-xs text-ink-gray-5">
            {{ __('Showing the {0} most engaged.').format(preview.sample.length) }}
          </p>
        </aside>
      </div>

      <ErrorMessage :message="error" class="mt-4" />
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button variant="solid" :loading="saving" :label="__('Save segment')" @click="save" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, ref, watch } from 'vue'
import {
  Avatar,
  Badge,
  Button,
  Combobox,
  Dropdown,
  ErrorMessage,
  FormControl,
  MultiSelect,
  Select,
  Skeleton,
  Spinner,
  TabButtons,
  debounce,
  toast,
} from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { NO_VALUE, OP_LABELS, groupMeta, previewSegment, saveSegment, segmentFields } from '@/data/segments'
import { errorMessage, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({ segment: { type: Object, default: null } })
const emit = defineEmits(['saved'])

const open = defineModel('open', { type: Boolean, default: false })

const matchOptions = [
  { label: __('All'), value: 'all' },
  { label: __('Any'), value: 'any' },
]

const PRESETS = [
  {
    label: 'Replied this month',
    rules: [{ field: 'last_reply_at', op: 'within', value: 30 }],
  },
  {
    label: 'Highly engaged',
    rules: [{ field: 'engagement_score', op: 'gte', value: 70 }],
  },
  {
    label: 'Silent for 90 days',
    rules: [{ field: 'last_reply_at', op: 'over', value: 90 }],
  },
  {
    label: 'Win back customers at risk',
    purchases: true,
    rules: [{ field: 'value_group', op: 'in', value: ['At risk', 'Needs attention'] }],
  },
  {
    label: 'Top customers who still reply',
    purchases: true,
    rules: [
      { field: 'value_group', op: 'in', value: ['Champion', 'Loyal'] },
      { field: 'engagement_score', op: 'gte', value: 40 },
    ],
  },
  {
    label: 'Chatted but never bought',
    purchases: true,
    rules: [
      { field: 'order_count', op: 'eq', value: 0 },
      { field: 'last_reply_at', op: 'within', value: 60 },
    ],
  },
  {
    label: 'Unpaid invoices',
    purchases: true,
    rules: [{ field: 'outstanding_amount', op: 'gt', value: 0 }],
  },
  {
    label: 'Gone quiet',
    purchases: true,
    rules: [
      { field: 'last_reply_at', op: 'over', value: 90 },
      { field: 'order_count', op: 'gte', value: 1 },
    ],
  },
]

const fields = ref([])
const form = reactive(blank())
const saving = ref(false)
const error = ref('')
const preview = reactive({ count: 0, reachable: null, sample: [] })
const previewing = ref(false)
const previewError = ref('')
let seed = 0
let ticket = 0

const name = computed(() => props.segment?.name || null)
const byKey = computed(() => Object.fromEntries(fields.value.map((row) => [row.key, row])))
const fieldOptions = computed(() => {
  const groups = new Map()
  for (const row of fields.value) {
    const name = row.group || __('Other')
    if (!groups.has(name)) groups.set(name, [])
    groups.get(name).push({ label: row.label, value: row.key })
  }
  return [...groups].map(([group, options]) => ({ group, options }))
})
const collapsible = computed(() => new Set(fields.value.filter((row) => row.document).map((row) => row.group || __('Other'))))
const expanded = reactive(new Set())

function toggleGroup(group) {
  if (expanded.has(group)) expanded.delete(group)
  else expanded.add(group)
}

function searching(rule) {
  const query = (rule.query || '').trim()
  return !!query && query !== (byKey.value[rule.field]?.label || '')
}

function optionsFor(rule) {
  const all = searching(rule)
  return fieldOptions.value.map((group) => {
    const open =
      all || !collapsible.value.has(group.group) || expanded.has(group.group) || group.options.some((option) => option.value === rule.field)
    if (open) return group
    return {
      group: group.group,
      hideLabel: true,
      options: [
        {
          type: 'custom',
          key: `show:${group.group}`,
          label: group.group,
          description: __('{0} fields').format(group.options.length),
          icon: 'lucide-chevron-right',
          keepOpen: true,
          condition: ({ query }) => !query,
          onClick: () => expanded.add(group.group),
        },
      ],
    }
  })
}
const presetOptions = computed(() =>
  PRESETS.filter((preset) => !preset.purchases || byKey.value.value_group).map((preset) => ({
    label: __(preset.label),
    onClick: () => applyPreset(preset),
  })),
)

function blank() {
  return { segment_name: '', description: '', match: 'all', rules: [] }
}

function makeRule(rule = {}) {
  return { id: ++seed, field: rule.field || null, op: rule.op || null, value: rule.value ?? null }
}

function kind(rule) {
  return byKey.value[rule.field]?.type
}

function opOptions(rule) {
  return (byKey.value[rule.field]?.ops || []).map((op) => ({ label: __(OP_LABELS[op] || op), value: op }))
}

function choiceOptions(rule) {
  return (byKey.value[rule.field]?.options || []).map((row) => ({ label: row.label, value: row.value, description: row.hint }))
}

function emptyValue(type, op) {
  if (type === 'choice' || type === 'labels') return []
  if (op === 'between') return ['', '']
  if (type === 'date') return 30
  return ''
}

function setField(rule, field) {
  rule.field = field
  rule.op = byKey.value[field]?.ops?.[0] || null
  rule.value = emptyValue(kind(rule), rule.op)
}

function setOp(rule, op) {
  const reset = (op === 'between') !== (rule.op === 'between')
  rule.op = op
  if (reset) rule.value = emptyValue(kind(rule), op)
}

function addRule(rule) {
  form.rules.push(makeRule(rule))
}

function applyPreset(preset) {
  form.rules = preset.rules.map((rule) => makeRule(rule))
  form.match = 'all'
  if (!form.segment_name) form.segment_name = __(preset.label)
}

function payload() {
  return form.rules.filter((rule) => rule.field && rule.op).map(({ field, op, value }) => ({ field, op, value }))
}

async function loadFields() {
  if (fields.value.length) return
  try {
    fields.value = await segmentFields()
  } catch (err) {
    error.value = errorMessage(err)
  }
}

const runPreview = debounce(async () => {
  const current = ++ticket
  previewing.value = true
  previewError.value = ''
  try {
    const result = await previewSegment(payload(), form.match)
    if (current !== ticket) return
    Object.assign(preview, result)
  } catch (err) {
    if (current === ticket) previewError.value = errorMessage(err)
  } finally {
    if (current === ticket) previewing.value = false
  }
}, 400)

watch(open, async (value) => {
  if (!value) return
  error.value = ''
  Object.assign(preview, { count: 0, reachable: null, sample: [] })
  const source = props.segment
  Object.assign(
    form,
    blank(),
    source ? { segment_name: source.segment_name, description: source.description || '', match: source.match || 'all' } : {},
  )
  await loadFields()
  form.rules = (source?.rules?.length ? source.rules : [{}]).map((rule) => makeRule(rule))
  if (!source) setField(form.rules[0], byKey.value.value_group ? 'value_group' : 'engagement_score')
})

watch(
  () => (open.value ? JSON.stringify([payload(), form.match]) : null),
  (value) => value && runPreview(),
)

async function save() {
  error.value = ''
  if (!form.segment_name.trim()) {
    error.value = __('Give the segment a name')
    return
  }
  if (!payload().length) {
    error.value = __('Add at least one rule')
    return
  }
  saving.value = true
  try {
    const saved = await saveSegment({ name: name.value, ...form, rules: payload() })
    toast.success(__('Segment saved'))
    emit('saved', saved)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}
</script>

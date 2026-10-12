<template>
  <div
    class="rounded-6 border bg-surface-elevation-1 shadow-sm transition-shadow"
    :class="[frame, width, selected ? 'shadow-lg ring-2 ring-outline-gray-3' : 'hover:shadow-md']"
  >
    <Handle v-if="!trigger" type="target" :position="Position.Top" />

    <div class="flex items-center gap-2.5 px-3 py-2.5">
      <span class="flex size-8 shrink-0 items-center justify-center rounded-4" :class="color.chip">
        <span :class="def.icon" class="size-4" aria-hidden="true" />
      </span>
      <div class="min-w-0 flex-1">
        <TruncatedText as="p" class="truncate text-sm font-medium text-ink-gray-8" :text="title" />
        <TruncatedText as="p" class="truncate text-xs text-ink-gray-5" :text="caption" />
      </div>
      <Tooltip v-if="badge" :text="badge.text">
        <span :class="badge.icon" class="size-4 shrink-0" aria-hidden="true" />
      </Tooltip>
    </div>

    <div v-if="def.preview" class="border-t border-outline-gray-1 bg-surface-gray-1 px-2.5 py-2">
      <div class="max-w-full rounded-4 rounded-tl-none bg-surface-base px-2.5 py-1.5 shadow-sm">
        <TruncatedText as="p" v-if="config.header" class="truncate text-xs font-semibold text-ink-gray-8" :text="config.header" />
        <p class="line-clamp-4 whitespace-pre-wrap break-words text-xs leading-relaxed text-ink-gray-8">
          <template v-for="(part, index) in parts" :key="index">
            <span v-if="part.token" class="rounded-1 bg-surface-blue-2 px-0.5 font-mono text-[11px] text-ink-blue-7">{{ part.text }}</span>
            <template v-else>{{ part.text }}</template>
          </template>
          <span v-if="!parts.length" class="text-ink-gray-4">{{ __('Write the message…') }}</span>
        </p>
        <p v-if="config.attach" class="mt-1 flex items-center gap-1 truncate text-xs text-ink-gray-5">
          <span class="lucide-paperclip size-3 shrink-0" aria-hidden="true" />
          {{ fileName(config.attach) }}
        </p>
        <p v-if="chip" class="mt-1 flex items-center gap-1 truncate text-xs text-ink-gray-5">
          <span :class="chip.icon" class="size-3 shrink-0" aria-hidden="true" />
          {{ chip.text }}
        </p>
      </div>
    </div>

    <div v-else-if="lines.length" class="flex flex-col gap-0.5 border-t border-outline-gray-1 px-3 py-2">
      <p v-for="(line, index) in lines" :key="index" class="flex min-w-0 gap-1.5 text-xs">
        <span v-if="line.label" class="shrink-0 text-ink-gray-5">{{ __(line.label) }}</span>
        <TruncatedText class="truncate text-ink-gray-7" :class="{ 'font-mono': line.label }" :text="line.value" />
      </p>
    </div>

    <div v-if="outputs && outputs.length" class="flex flex-col gap-1 border-t border-outline-gray-1 px-2.5 py-2">
      <div v-for="output in outputs" :key="output.id" class="relative">
        <TruncatedText
          as="div"
          class="truncate rounded-4 px-2 py-1 text-xs"
          :class="
            output.muted ? 'text-ink-gray-5' : 'border border-outline-gray-2 bg-surface-base text-center font-medium text-ink-blue-link'
          "
          :text="__(output.label)"
        />
        <Handle :id="output.id" type="source" :position="Position.Right" class="!-right-[15px]" />
      </div>
    </div>
    <Handle v-else-if="!outputs" type="source" :position="Position.Bottom" />

    <div
      v-if="stats"
      class="flex flex-wrap items-center gap-1.5 rounded-b-6 border-t border-outline-gray-1 bg-surface-gray-1 px-3 py-1.5 text-xs"
    >
      <Tooltip :text="__('Runs that reached this step')">
        <span class="inline-flex items-center gap-1 font-medium tabular-nums text-ink-gray-8">
          <span class="lucide-users size-3 text-ink-gray-5" aria-hidden="true" />
          {{ stats.reached }}
          <span v-if="stats.share !== null" class="font-normal text-ink-gray-5">· {{ stats.share }}%</span>
        </span>
      </Tooltip>
      <span class="flex-1" />
      <Tooltip v-if="stats.waiting" :text="__('Waiting at this step right now')">
        <span class="rounded bg-surface-amber-2 px-1.5 tabular-nums text-ink-amber-7">{{ __('{0} waiting').format(stats.waiting) }}</span>
      </Tooltip>
      <Tooltip v-if="stats.left" :text="__('Stopped or timed out at this step')">
        <span class="rounded bg-surface-red-2 px-1.5 tabular-nums text-ink-red-7">{{ __('{0} left').format(stats.left) }}</span>
      </Tooltip>
      <Tooltip v-if="stats.failed" :text="__('Runs where this step failed')">
        <span class="rounded bg-surface-red-2 px-1.5 tabular-nums text-ink-red-7">{{ __('{0} failed').format(stats.failed) }}</span>
      </Tooltip>
    </div>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { Tooltip } from 'frappe-ui'
import { colorOf, isTrigger, missingFields, nodeDef, outputsOf, summarize } from './nodeTypes'
import { fileName } from '@/data/inbox'
import { translate as __ } from '@/translation'

const props = defineProps({
  id: { type: String, required: true },
  data: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  status: { type: String, default: '' },
  stats: { type: Object, default: null },
})

const TYPES = { text: 'Any text', number: 'A number', email: 'An email', phone: 'A phone number', date: 'A date', yes_no: 'Yes or no' }

const def = computed(() => nodeDef(props.data.nodeType))
const config = computed(() => props.data.config || {})
const color = computed(() => colorOf(props.data.nodeType))
const trigger = computed(() => isTrigger(props.data.nodeType))
const custom = computed(() => !!props.data.label && props.data.label !== def.value.label)
const title = computed(() => (custom.value ? props.data.label : __(def.value.label)))
const caption = computed(() => (custom.value ? __(def.value.label) : __(def.value.description)))
const lines = computed(() => summarize(props.data.nodeType, config.value))
const missing = computed(() => missingFields(props.data.nodeType, config.value))
const outputs = computed(() => outputsOf(props.data.nodeType, config.value))
const width = computed(() => (outputs.value?.length ? 'w-64' : 'w-60'))

const parts = computed(() => {
  const text = String(config.value.text || '')
  if (!text) return []
  return text
    .split(/({{\s*[\w.]+\s*}})/g)
    .filter(Boolean)
    .map((piece) => ({ text: piece, token: /^{{.*}}$/.test(piece) }))
})

const chip = computed(() => {
  const type = props.data.nodeType
  if (type === 'ask_question') {
    const target = config.value.save_as ? ` → ${config.value.save_as}` : ''
    return { icon: 'lucide-corner-down-right', text: `${__(TYPES[config.value.answer_type] || TYPES.text)}${target}` }
  }
  if (type === 'send_form' && config.value.form) return { icon: 'lucide-clipboard-list', text: config.value.form }
  if (type === 'send_list') return { icon: 'lucide-list', text: config.value.button_label || __('Choose') }

  return null
})

const frame = computed(() => {
  if (props.status === 'Success') return 'border-outline-green-4'
  if (props.status === 'Failed') return 'border-outline-red-4'
  if (props.status === 'Started' || props.status === 'Waiting') return 'border-outline-blue-4'

  return 'border-outline-gray-2'
})

const badge = computed(() => {
  if (props.status === 'Waiting') return { icon: 'lucide-hourglass text-ink-blue-6', text: __('Waiting here in the test chat') }
  if (props.status === 'Success') return { icon: 'lucide-circle-check text-ink-green-6', text: __('Ran in the last test') }
  if (props.status === 'Failed') return { icon: 'lucide-circle-x text-ink-red-6', text: __('Failed in the last test') }
  if (props.status === 'Started') return { icon: 'lucide-loader text-ink-blue-6', text: __('Did not finish in the last test') }
  if (missing.value.length) {
    return {
      icon: 'lucide-circle-alert text-ink-amber-6',
      text: __('Needs: {0}').format(missing.value.map((field) => __(field.label)).join(', ')),
    }
  }
  if (def.value.runnable === false) return { icon: 'lucide-info text-ink-gray-5', text: __('The server skips this step') }

  return null
})
</script>

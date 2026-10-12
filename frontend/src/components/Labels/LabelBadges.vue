<template>
  <span v-if="names.length && dots" class="flex shrink-0 items-center gap-1" :title="summary">
    <span
      v-for="row in shown"
      :key="row.name"
      class="size-2 rounded-full"
      :class="LABEL_DOTS[row.color] || LABEL_DOTS.gray"
      aria-hidden="true"
    />
    <span v-if="rest.length" class="text-xs tabular-nums text-ink-gray-5" aria-hidden="true">+{{ countLabel(rest.length) }}</span>
    <span class="sr-only">{{ summary }}</span>
  </span>
  <span v-else-if="names.length" class="flex min-w-0 items-center gap-1">
    <Badge
      v-for="row in shown"
      :key="row.name"
      :theme="row.color || 'gray'"
      variant="subtle"
      :size="size"
      class="min-w-0 shrink truncate"
      :label="row.label_name || row.name"
    />
    <Tooltip v-if="rest.length" :text="rest.map((row) => row.label_name || row.name).join(', ')">
      <Badge theme="gray" variant="subtle" :size="size" class="shrink-0 tabular-nums" :label="`+${countLabel(rest.length)}`" />
    </Tooltip>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, Tooltip } from 'frappe-ui'
import { LABEL_DOTS, labelMeta } from '@/data/inbox'
import { countLabel } from '@/utils/format'

const props = defineProps({
  names: { type: Array, default: () => [] },
  max: { type: Number, default: 0 },
  size: { type: String, default: 'sm' },
  dots: { type: Boolean, default: false },
})

const rows = computed(() => props.names.map(labelMeta))
const shown = computed(() => (props.max ? rows.value.slice(0, props.max) : rows.value))
const rest = computed(() => (props.max ? rows.value.slice(props.max) : []))
const summary = computed(() => rows.value.map((row) => row.label_name || row.name).join(', '))
</script>

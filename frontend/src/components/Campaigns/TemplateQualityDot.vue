<template>
  <Tooltip :text="__('Quality: {0}').format(__(qualityLabel(score)))">
    <span class="inline-flex items-center gap-1.5">
      <span class="size-2 shrink-0 rounded-full" :class="DOTS[key] || DOTS.UNKNOWN" aria-hidden="true" />
      <span v-if="showLabel" class="text-base text-ink-gray-7">{{ __(qualityLabel(score)) }}</span>
      <span v-else class="sr-only">{{ __(qualityLabel(score)) }}</span>
    </span>
  </Tooltip>
</template>

<script>
const LABELS = { GREEN: 'High', YELLOW: 'Medium', RED: 'Low', UNKNOWN: 'Unknown' }

export function qualityLabel(score) {
  return LABELS[String(score || 'UNKNOWN').toUpperCase()] || LABELS.UNKNOWN
}
</script>

<script setup>
import { computed } from 'vue'
import { Tooltip } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  score: { type: String, default: '' },
  showLabel: { type: Boolean, default: false },
})

const DOTS = {
  GREEN: 'bg-surface-green-6',
  YELLOW: 'bg-surface-amber-6',
  RED: 'bg-surface-red-6',
  UNKNOWN: 'bg-surface-gray-4',
}

const key = computed(() => String(props.score || 'UNKNOWN').toUpperCase())
</script>

<template>
  <div class="grid gap-2" :class="columns">
    <template v-if="loading">
      <Skeleton v-for="index in 3" :key="index" class="h-16 w-full rounded-4" />
    </template>
    <Tooltip v-for="stat in shown" v-else :key="stat.key" :text="stat.hint || ''" :disabled="!stat.hint">
      <div class="min-w-0 rounded-4 border border-outline-gray-1 px-3 py-2.5">
        <TruncatedText as="p" class="truncate text-xs text-ink-gray-5" :text="stat.label" />
        <TruncatedText
          as="p"
          class="mt-0.5 truncate text-base font-semibold tabular-nums"
          :class="stat.theme === 'red' ? 'text-ink-red-6' : 'text-ink-gray-9'"
          :text="display(stat)"
        />
      </div>
    </Tooltip>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { Skeleton, Tooltip } from 'frappe-ui'
import { formatDate, timeAgo } from '@/utils/format'

const props = defineProps({
  stats: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  columns: { type: String, default: 'grid-cols-2 sm:grid-cols-3' },
})

const shown = computed(() => props.stats.filter((stat) => stat.value !== null && stat.value !== undefined && stat.value !== ''))

function display(stat) {
  if (stat.type === 'date') return formatDate(stat.value)
  if (stat.type === 'ago') return timeAgo(stat.value)
  return stat.value
}
</script>

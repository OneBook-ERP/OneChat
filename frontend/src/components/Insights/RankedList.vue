<template>
  <ChartCard>
    <ChartContainer :title="title" :subtitle="subtitle" :loading="loading" :empty="!rows.length">
      <template #empty>
        <p class="text-sm text-ink-gray-5">{{ emptyText || __('Nothing in this period') }}</p>
      </template>
      <ul class="flex flex-col gap-1 py-1" :class="{ 'min-h-32': loading || !rows.length }">
        <ErrorHint v-for="row in rows" :key="row.name" :title="row.label || row.name" :info="tip ? tip(row) || {} : null">
          <li
            class="-mx-1.5 flex flex-col gap-1 rounded-4 px-1.5 py-1 outline-none"
            :class="{ 'cursor-default transition-colors hover:bg-surface-gray-2 focus-visible:bg-surface-gray-2': tip }"
            :tabindex="tip ? 0 : undefined"
          >
            <div class="flex items-baseline justify-between gap-3 text-sm">
              <span v-if="tip" class="min-w-0 truncate text-ink-gray-8">{{ row.label || row.name }}</span>
              <TruncatedText v-else class="min-w-0 truncate text-ink-gray-8" :text="row.label || row.name" />
              <span class="shrink-0 tabular-nums text-ink-gray-6">{{ format ? format(row.value) : formatNumber(row.value) }}</span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-surface-gray-2">
              <div class="h-full rounded-full bg-surface-gray-7" :style="{ width: `${width(row.value)}%` }" />
            </div>
          </li>

          <template #stats>
            <div class="flex items-center gap-3">
              <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-gray-2">
                <div class="h-full rounded-full bg-surface-gray-7" :style="{ width: `${share(row.value)}%` }" />
              </div>
              <span class="shrink-0 text-xs tabular-nums text-ink-gray-6">
                {{ format ? format(row.value) : formatNumber(row.value) }} · {{ share(row.value) }}%
              </span>
            </div>
          </template>
        </ErrorHint>
      </ul>
    </ChartContainer>
  </ChartCard>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import ErrorHint from './ErrorHint.vue'
import { ChartCard, ChartContainer } from 'frappe-ui/charts'
import { formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  emptyText: { type: String, default: '' },
  format: { type: Function, default: null },
  tip: { type: Function, default: null },
})

const largest = computed(() => Math.max(1, ...props.rows.map((row) => Number(row.value) || 0)))
const total = computed(() => props.rows.reduce((sum, row) => sum + (Number(row.value) || 0), 0))

function width(value) {
  return Math.max(2, Math.round(((Number(value) || 0) * 100) / largest.value))
}

function share(value) {
  if (!total.value) return 0
  const percent = ((Number(value) || 0) * 100) / total.value
  return percent < 1 && percent > 0 ? '<1' : Math.round(percent)
}
</script>

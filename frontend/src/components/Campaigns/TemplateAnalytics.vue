<template>
  <div class="flex flex-col gap-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-sm text-ink-gray-5">{{ caption }}</p>
      <TabButtons v-model="days" :options="ranges" />
    </div>

    <ErrorMessage v-if="stats.error" :message="errorMessage(stats.error)" />

    <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <NumberCard
        :title="__('Sent')"
        :value="data ? data.sent : null"
        :loading="stats.loading && !data"
        :sparkline="data?.series?.some(Boolean) ? { data: data.series, type: 'bar' } : undefined"
      />
      <NumberCard :title="__('Delivered')" :value="percent('delivered_rate')" :loading="stats.loading && !data" />
      <NumberCard :title="__('Read')" :value="percent('read_rate')" :loading="stats.loading && !data" />
      <NumberCard :title="__('Replied')" :value="percent('replied_rate')" :loading="stats.loading && !data" />
      <NumberCard :title="__('Failed')" :value="data ? data.failed : null" :loading="stats.loading && !data" />
    </div>

    <div v-if="data && !data.sent && days" class="flex flex-wrap items-center justify-between gap-3 rounded-5 bg-surface-gray-1 px-4 py-3">
      <div class="flex min-w-0 items-center gap-2.5">
        <span class="lucide-calendar-search size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
        <p class="text-base text-ink-gray-7">
          {{
            data.last_sent
              ? __('Not sent in this period. Last sent {0}.').format(timeAgo(data.last_sent))
              : __('This template has not been sent yet.')
          }}
        </p>
      </div>
      <Button v-if="data.last_sent" variant="subtle" :label="__('Show all time')" @click="days = 0" />
    </div>

    <p v-else-if="data" class="text-sm text-ink-gray-5">
      {{ __('Replied counts a message from the same contact within 24 hours of the template.') }}
      <template v-if="data.truncated">{{
        __('Replies are estimated from the latest {0} sends.').format(formatNumber(data.sampled))
      }}</template>
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, ErrorMessage, TabButtons, createResource } from 'frappe-ui'
import { NumberCard } from 'frappe-ui/charts'
import { errorMessage, formatNumber, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  template: { type: String, required: true },
})

const days = ref(30)

const ranges = [
  { label: __('7 days'), value: 7 },
  { label: __('30 days'), value: 30 },
  { label: __('90 days'), value: 90 },
  { label: __('1 year'), value: 365 },
  { label: __('All time'), value: 0 },
]

const caption = computed(() => {
  if (!days.value) return __('All template messages sent, by month')
  if (days.value === 365) return __('Template messages sent in the last 12 months, by month')

  return __('Template messages sent in the last {0} days').format(days.value)
})

const stats = createResource({
  url: 'onechat.campaigns.template_stats.stats',
  makeParams: () => ({ template: props.template, days: days.value }),
})

const data = computed(() => stats.data)

function percent(field) {
  if (!data.value) return null
  const value = data.value[field]

  return value === null || value === undefined ? '—' : `${value}%`
}

watch(
  () => [props.template, days.value],
  () => stats.reload(),
  { immediate: true },
)
</script>

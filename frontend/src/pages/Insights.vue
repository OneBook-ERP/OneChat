<template>
  <AppHeader>
    <template #actions>
      <Button
        variant="ghost"
        icon-left="lucide-refresh-cw"
        :label="__('Refresh')"
        :loading="loading"
        :disabled="!params"
        @click="refresh({ fresh: true })"
      />
    </template>
  </AppHeader>

  <div class="mx-auto w-full max-w-[1100px] px-3 pb-10 pt-5 sm:px-5">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <InsightsRange v-model:period="period" v-model:dates="dates" />
      <p v-if="data?.generated_at" class="text-xs text-ink-gray-5">{{ __('Updated {0}').format(timeAgo(data.generated_at)) }}</p>
    </div>

    <ErrorMessage v-if="error && data" :message="errorMessage(error)" class="mb-4" />

    <EmptyState v-if="error && !data" icon="lucide-circle-alert" :title="__('Could not load insights')" :description="errorMessage(error)">
      <Button icon-left="lucide-refresh-cw" :label="__('Try again')" @click="refresh({ fresh: true })" />
    </EmptyState>

    <EmptyState
      v-else-if="!params"
      icon="lucide-calendar-range"
      :title="__('Pick a date range')"
      :description="__('Choose a start and end date to see how messaging went in that window.')"
    />

    <component
      :is="TABS[tab]"
      v-else
      class="transition-opacity"
      :class="{ 'opacity-60': refreshing }"
      :data="data"
      :loading="!data"
      :range-label="rangeLabel"
      @refresh="refresh({ quiet: true, fresh: true })"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button, ErrorMessage, call } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import AutomationTab from '@/components/Insights/AutomationTab.vue'
import CampaignsTab from '@/components/Insights/CampaignsTab.vue'
import ConversationsTab from '@/components/Insights/ConversationsTab.vue'
import CostsTab from '@/components/Insights/CostsTab.vue'
import OrdersTab from '@/components/Insights/OrdersTab.vue'
import InsightsRange from '@/components/Insights/InsightsRange.vue'
import OverviewTab from '@/components/Insights/OverviewTab.vue'
import TeamTab from '@/components/Insights/TeamTab.vue'
import { refField, useQueryState } from '@/composables/useQueryState'
import { errorMessage, formatDate, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({
  compact: { type: Boolean, default: false },
})

const TABS = {
  overview: OverviewTab,
  conversations: ConversationsTab,
  team: TeamTab,
  automation: AutomationTab,
  campaigns: CampaignsTab,
  orders: OrdersTab,
  costs: CostsTab,
}

const LABELS = {
  24: 'Last 24 hours',
  168: 'Last 7 days',
  720: 'Last 30 days',
  2160: 'Last 90 days',
}

const route = useRoute()

const period = ref('168')
const dates = ref([])

useQueryState([
  refField('range', period, '168'),
  {
    key: 'dates',
    fallback: '',
    get: () => (dates.value?.length === 2 ? dates.value.join(',') : ''),
    set: (value) => (dates.value = value ? String(value).split(',').slice(0, 2) : []),
  },
])

const tab = computed(() => (TABS[route.query.tab] ? route.query.tab : 'overview'))

const params = computed(() => {
  if (period.value !== 'custom') return { tab: tab.value, period: period.value }
  if (dates.value?.length !== 2) return null

  return { tab: tab.value, period: 'custom', start: `${dates.value[0]} 00:00:00`, end: `${dates.value[1]} 23:59:59` }
})

const payload = ref(null)
const loading = ref(false)
const error = ref(null)
let latest = 0

const data = computed(() => (payload.value?.tab === tab.value ? payload.value : null))
const refreshing = computed(() => loading.value && !!data.value)

const rangeLabel = computed(() => {
  if (period.value !== 'custom') return __(LABELS[period.value])
  if (dates.value?.length !== 2) return ''

  return `${formatDate(dates.value[0])} – ${formatDate(dates.value[1])}`
})

const seen = new Map()

async function refresh({ quiet = false, fresh = false } = {}) {
  if (!params.value) return

  const ticket = ++latest
  const requested = params.value
  const key = JSON.stringify(requested)
  const known = seen.get(key)
  if (known && !fresh) payload.value = known
  loading.value = !quiet && !(known && !fresh)
  error.value = null
  try {
    const result = await call('onechat.insights.metrics.report', { ...requested, fresh: fresh ? 1 : 0 })
    const value = { ...result, tab: requested.tab }
    seen.set(key, value)
    if (ticket === latest) payload.value = value
  } catch (err) {
    if (ticket === latest && !known) error.value = err
  } finally {
    if (ticket === latest) loading.value = false
  }
}

watch(params, () => refresh(), { immediate: true, deep: true })
</script>

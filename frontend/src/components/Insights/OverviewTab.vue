<template>
  <div class="flex flex-col gap-10">
    <InsightsSection
      id="insights-overview"
      :title="__('At a glance')"
      :description="__('{0}, compared with the period before').format(rangeLabel)"
    >
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <NumberCard v-for="card in cards" :key="card.title" v-bind="card" :loading="loading" />
      </div>
    </InsightsSection>

    <InsightsSection id="insights-messages" :title="__('Messages')" :description="__('Traffic, who is sending and how it lands')">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard class="h-80 lg:col-span-2">
          <AreaChart
            :data="traffic"
            x="label"
            :y="['received', 'sent']"
            :series-config="{ received: { label: __('Received') }, sent: { label: __('Sent') } }"
            :x-axis="{ type: 'category' }"
            :loading="loading"
            :title="__('Messages over time')"
            :subtitle="rangeLabel"
          />
        </ChartCard>

        <ChartCard class="h-80">
          <DonutChart
            :data="sources"
            category="name"
            value="value"
            :center-label="__('sent')"
            :loading="loading"
            :title="__('Who sent messages')"
            :subtitle="__('Agents, chatbots and automations')"
          />
        </ChartCard>

        <ChartCard class="h-80 lg:col-span-3">
          <FunnelChart
            :data="funnel"
            category="stage"
            value="count"
            show-percentages
            :loading="loading"
            :title="__('Delivery')"
            :subtitle="deliveryCaption"
          />
        </ChartCard>
      </div>
    </InsightsSection>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { AreaChart, ChartCard, DonutChart, FunnelChart, NumberCard } from 'frappe-ui/charts'
import InsightsSection from '@/components/Insights/InsightsSection.vue'
import { SOURCES, change, kpi, trend, waitTime, withLabels } from '@/components/Insights/insights'
import { formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  rangeLabel: { type: String, default: '' },
})

const traffic = computed(() => withLabels(props.data?.traffic, props.data?.range?.hourly))

const cards = computed(() => {
  const now = props.data?.now || {}
  const before = props.data?.before || {}
  const caption = __('vs previous period')
  const compared = (key, extra = {}) => ({ delta: change(now[key], before[key]), deltaSuffix: '%', deltaCaption: caption, ...extra })

  return [
    kpi(__('Conversations'), now.conversations, compared('conversations', { sparkline: trend(props.data?.traffic, 'received') })),
    kpi(__('Avg first response'), waitTime(now.response) ?? '—', compared('response', { negativeIsBetter: true, compact: false })),
    kpi(__('Resolved'), now.resolved, compared('resolved')),
    kpi(__('Read rate'), now.read_rate, compared('read_rate', { suffix: '%', precision: 0, compact: false })),
    kpi(__('Messages received'), now.received, compared('received')),
    kpi(__('Messages sent'), now.sent, compared('sent', { sparkline: trend(props.data?.traffic, 'sent') })),
    kpi(__('New contacts'), now.contacts, compared('contacts')),
    kpi(__('Opt-outs'), now.opt_outs, compared('opt_outs', { negativeIsBetter: true })),
    kpi(
      __('Satisfaction'),
      now.satisfaction === null || now.satisfaction === undefined ? '—' : now.satisfaction,
      compared('satisfaction', { suffix: '%', precision: 0, compact: false }),
    ),
  ]
})

const sources = computed(() => (props.data?.sources || []).map((row) => ({ name: __(SOURCES[row.name] || row.name), value: row.value })))

const funnel = computed(() => {
  const delivery = props.data?.delivery
  if (!delivery?.sent) return []

  return [
    { stage: __('Sent'), count: delivery.sent },
    { stage: __('Delivered'), count: delivery.delivered },
    { stage: __('Read'), count: delivery.read },
  ]
})

const deliveryCaption = computed(() => {
  const failed = props.data?.delivery?.failed || 0
  return failed ? __('{0} failed to send').format(formatNumber(failed)) : __('Every outgoing message in this period')
})
</script>

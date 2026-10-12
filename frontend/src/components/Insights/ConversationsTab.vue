<template>
  <div class="flex flex-col gap-10">
    <InsightsSection id="insights-backlog" :title="__('Right now')" :description="__('Conversations waiting on your team at this moment')">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <NumberCard v-for="card in backlog" :key="card.title" v-bind="card" :loading="loading" />
      </div>
    </InsightsSection>

    <InsightsSection id="insights-speed" :title="__('Speed')" :description="rangeLabel">
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <NumberCard v-for="card in speed" :key="card.title" v-bind="card" :loading="loading" />
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ChartCard class="h-80 lg:col-span-2">
            <BarChart
              :data="flow"
              x="label"
              :y="['opened', 'resolved']"
              :series-config="{ opened: { label: __('Opened') }, resolved: { label: __('Resolved') } }"
              :x-axis="{ type: 'category' }"
              :loading="loading"
              :title="__('Opened vs resolved')"
              :subtitle="__('Is the team keeping up?')"
            />
          </ChartCard>

          <ChartCard class="h-80">
            <BarChart
              :data="bands"
              x="band"
              y="count"
              :series-config="{ count: { label: __('Conversations') } }"
              :x-axis="{ type: 'category' }"
              :loading="loading"
              :title="__('Time to first reply')"
              :subtitle="__('How long customers waited')"
            />
          </ChartCard>
        </div>
      </div>
    </InsightsSection>

    <InsightsSection
      v-if="channelRows.length"
      id="insights-channels"
      :title="__('By channel')"
      :description="__('How quickly and how fully each channel gets handled')"
    >
      <div class="flex flex-col gap-3 sm:hidden">
        <div v-for="row in channelRows" :key="row.channel" class="rounded-5 border border-outline-gray-1 p-3">
          <p class="mb-2 inline-flex items-center gap-2 text-base font-medium text-ink-gray-8">
            <ChannelIcon :channel="row.channel" show-whatsapp class="size-4 shrink-0" />
            {{ __(row.channel) }}
          </p>
          <dl class="grid grid-cols-2 gap-x-4 gap-y-2">
            <div v-for="column in CHANNEL_COLUMNS" :key="column.key">
              <dt class="text-xs text-ink-gray-5">{{ __(column.label) }}</dt>
              <dd
                class="text-base tabular-nums text-ink-gray-8"
                :class="row.best.includes(column.key) ? 'font-semibold text-ink-green-4' : ''"
              >
                {{ row.text[column.key] }}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div class="hidden overflow-x-auto rounded-5 border border-outline-gray-1 sm:block">
        <table class="w-full min-w-[720px] text-base">
          <thead>
            <tr class="border-b border-outline-gray-1 text-left text-sm text-ink-gray-5">
              <th class="px-4 py-2.5 font-normal">{{ __('Channel') }}</th>
              <th v-for="column in CHANNEL_COLUMNS" :key="column.key" class="px-4 py-2.5 text-right font-normal">
                {{ __(column.label) }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-gray-1">
            <tr v-for="row in channelRows" :key="row.channel" class="text-ink-gray-8">
              <td class="px-4 py-3">
                <span class="inline-flex items-center gap-2 font-medium">
                  <ChannelIcon :channel="row.channel" show-whatsapp class="size-4 shrink-0" />
                  {{ __(row.channel) }}
                </span>
              </td>
              <td
                v-for="column in CHANNEL_COLUMNS"
                :key="column.key"
                class="px-4 py-3 text-right tabular-nums"
                :class="row.best.includes(column.key) ? 'font-semibold text-ink-green-4' : ''"
              >
                {{ row.text[column.key] }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </InsightsSection>

    <InsightsSection
      id="insights-hours"
      :title="__('Busiest hours')"
      :description="__('Incoming messages by weekday and hour. Use it to plan shifts and business hours.')"
    >
      <ChartCard class="h-96">
        <HeatmapChart
          :data="heatmap"
          x="hour"
          y="day"
          value="count"
          :loading="loading"
          :title="__('When customers write in')"
          :subtitle="peak"
        />
      </ChartCard>
    </InsightsSection>

    <InsightsSection id="insights-topics" :title="__('What comes in')" :description="rangeLabel">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard class="h-80">
          <DonutChart
            :data="contentTypes"
            category="name"
            value="value"
            :center-label="__('received')"
            :loading="loading"
            :title="__('Message types')"
            :subtitle="__('What customers send')"
          />
        </ChartCard>
        <RankedList
          :title="__('Conversations by label')"
          :subtitle="__('Labels on contacts who wrote in')"
          :rows="data?.labels || []"
          :loading="loading"
          :empty-text="__('No labelled conversations in this period')"
        />
        <RankedList
          v-if="data?.channels?.length"
          :title="__('Conversations by channel')"
          :subtitle="__('WhatsApp or Instagram')"
          :rows="data.channels"
          :loading="loading"
        />
        <RankedList
          v-if="commentRows.length"
          :title="__('Instagram comments')"
          :subtitle="__('Comments on your posts and how they were handled')"
          :rows="commentRows"
          :loading="loading"
        />
        <RankedList
          v-if="data?.accounts?.length"
          :title="__('Conversations by account')"
          :subtitle="__('Which WhatsApp number or Instagram account they reached')"
          :rows="data.accounts"
          :loading="loading"
        />
      </div>
    </InsightsSection>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { BarChart, ChartCard, DonutChart, HeatmapChart, NumberCard } from 'frappe-ui/charts'
import InsightsSection from '@/components/Insights/InsightsSection.vue'
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import RankedList from '@/components/Insights/RankedList.vue'
import { BANDS, CONTENT_TYPES, DAYS, kpi, percentText, share, waitTime, withLabels } from '@/components/Insights/insights'
import { translate as __ } from '@/translation'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  rangeLabel: { type: String, default: '' },
})

const commentRows = computed(() => {
  const counts = props.data?.comments
  if (!counts) return []
  return [
    { name: __('Received'), value: counts.received },
    { name: __('Replied privately'), value: counts.replied },
    { name: __('Replied publicly'), value: counts.public },
    { name: __('Hidden'), value: counts.hidden },
  ]
})

const CHANNEL_COLUMNS = [
  { key: 'opened', label: 'Opened' },
  { key: 'resolved', label: 'Resolved' },
  { key: 'resolution_rate', label: 'Resolution rate', better: 'high' },
  { key: 'response', label: 'Avg first response', better: 'low', time: true },
  { key: 'median_response', label: 'Median first response', better: 'low', time: true },
  { key: 'resolution', label: 'Avg time to resolve', better: 'low', time: true },
  { key: 'unanswered', label: 'Not replied yet' },
]

const channelRows = computed(() => {
  const rows = props.data?.by_channel || []
  const winners = {}
  for (const column of CHANNEL_COLUMNS.filter((item) => item.better)) {
    const values = rows.map((row) => row[column.key]).filter((value) => value !== null && value !== undefined)
    if (values.length < 2 || new Set(values).size < 2) continue
    winners[column.key] = column.better === 'high' ? Math.max(...values) : Math.min(...values)
  }
  return rows.map((row) => ({
    ...row,
    best: Object.keys(winners).filter((key) => row[key] === winners[key]),
    text: Object.fromEntries(
      CHANNEL_COLUMNS.map((column) => [
        column.key,
        column.time
          ? (waitTime(row[column.key]) ?? '—')
          : column.key === 'resolution_rate'
            ? percentText(row[column.key])
            : (row[column.key] ?? 0),
      ]),
    ),
  }))
})

const backlog = computed(() => {
  const now = props.data?.backlog || {}
  return [
    kpi(__('Open'), now.open),
    kpi(__('Waiting for a reply'), now.waiting, { negativeIsBetter: true }),
    kpi(__('Open and unassigned'), now.unassigned),
    kpi(__('Pending'), now.pending),
  ]
})

const speed = computed(() => {
  const summary = props.data?.summary || {}
  return [
    kpi(__('Conversations opened'), summary.opened),
    kpi(__('Resolved'), summary.resolved),
    kpi(__('Avg first response'), waitTime(summary.response) ?? '—', { compact: false }),
    kpi(__('Median first response'), waitTime(summary.median_response) ?? '—', { compact: false }),
    kpi(__('Avg time to resolve'), waitTime(summary.resolution) ?? '—', { compact: false }),
    kpi(__('Not replied yet'), summary.unanswered),
    kpi(__('Handled by a bot only'), summary.bot_only),
    kpi(__('Resolution rate'), share(summary.resolved || 0, summary.opened || 0), { suffix: '%', compact: false }),
  ]
})

const flow = computed(() => withLabels(props.data?.flow, props.data?.range?.hourly))

const bands = computed(() =>
  (props.data?.response_bands || []).map((row, index) => ({ band: __(BANDS[index] || row.name), count: row.value })),
)

const heatmap = computed(() => (props.data?.heatmap || []).map((cell) => ({ ...cell, day: __(DAYS[cell.day] || cell.day) })))

const peak = computed(() => {
  const busiest = (props.data?.heatmap || []).reduce((top, cell) => (cell.count > (top?.count || 0) ? cell : top), null)
  if (!busiest) return __('No incoming messages in this period')

  return __('Busiest: {0} around {1}:00').format(__(DAYS[busiest.day] || busiest.day), busiest.hour)
})

const contentTypes = computed(() =>
  (props.data?.content_types || []).map((row) => ({ name: __(CONTENT_TYPES[row.name] || row.name), value: row.value })),
)
</script>

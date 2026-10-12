<template>
  <div class="flex flex-col gap-10">
    <InsightsSection id="insights-agents" :title="__('Agents')" :description="rangeLabel">
      <div class="flex flex-col gap-4">
        <div class="flex flex-wrap items-center gap-2 text-sm text-ink-gray-6">
          <span class="inline-flex items-center gap-1.5 rounded-full bg-surface-gray-2 px-2.5 py-1">
            <span class="size-2 rounded-full bg-surface-green-6" aria-hidden="true" />{{
              __('{0} available').format(availability.Available || 0)
            }}
          </span>
          <span class="inline-flex items-center gap-1.5 rounded-full bg-surface-gray-2 px-2.5 py-1">
            <span class="size-2 rounded-full bg-surface-gray-5" aria-hidden="true" />{{ __('{0} away').format(availability.Away || 0) }}
          </span>
        </div>

        <InsightsTable
          :title="__('Agent performance')"
          :subtitle="__('Replies and response times per agent')"
          :columns="columns"
          :rows="agents"
          row-key="user"
          :loading="loading"
          :empty-text="__('No agent activity in this period')"
        >
          <template #name="{ row }">
            <div class="flex items-center gap-2">
              <Avatar size="sm" :image="row.image" :label="row.name" />
              <TruncatedText class="truncate" :text="row.name" />
              <span
                v-if="row.availability"
                class="size-1.5 shrink-0 rounded-full"
                :class="row.availability === 'Away' ? 'bg-surface-gray-5' : 'bg-surface-green-6'"
                :title="__(row.availability)"
              />
            </div>
          </template>
        </InsightsTable>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ChartCard class="h-80">
            <BarChart
              :data="workload"
              x="name"
              :y="['replies', 'resolved']"
              :series-config="{ replies: { label: __('Replies') }, resolved: { label: __('Resolved') } }"
              horizontal
              :loading="loading"
              :title="__('Workload')"
              :subtitle="__('Top agents by replies')"
            />
          </ChartCard>
          <ChartCard class="h-80">
            <AreaChart
              :data="replies"
              x="label"
              y="replies"
              :series-config="{ replies: { label: __('Agent replies') } }"
              :x-axis="{ type: 'category' }"
              :loading="loading"
              :title="__('Agent replies over time')"
              :subtitle="rangeLabel"
            />
          </ChartCard>
        </div>
      </div>
    </InsightsSection>

    <InsightsSection v-if="loading || data?.teams?.length" id="insights-teams" :title="__('Teams')" :description="rangeLabel">
      <InsightsTable
        :title="__('Team performance')"
        :subtitle="__('Conversations routed to each team')"
        :columns="teamColumns"
        :rows="data?.teams || []"
        row-key="team"
        :loading="loading"
      />
    </InsightsSection>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { Avatar } from 'frappe-ui'
import { AreaChart, BarChart, ChartCard } from 'frappe-ui/charts'
import InsightsSection from '@/components/Insights/InsightsSection.vue'
import InsightsTable from '@/components/Insights/InsightsTable.vue'
import { waitTime, withLabels } from '@/components/Insights/insights'
import { translate as __ } from '@/translation'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  rangeLabel: { type: String, default: '' },
})

const duration = (value) => waitTime(value) ?? '—'

const columns = [
  { key: 'name', label: __('Agent') },
  { key: 'open', label: __('Open now'), numeric: true },
  { key: 'assigned', label: __('Assigned'), numeric: true },
  { key: 'replies', label: __('Replies'), numeric: true },
  { key: 'first_responses', label: __('First replies'), numeric: true },
  { key: 'response', label: __('Avg first response'), numeric: true, format: duration },
  { key: 'resolved', label: __('Resolved'), numeric: true },
  { key: 'resolution', label: __('Avg time to resolve'), numeric: true, format: duration },
  { key: 'rating', label: __('Rating (of 3)'), numeric: true, format: (value) => (value === null || value === undefined ? '—' : value) },
]

const teamColumns = [
  { key: 'team', label: __('Team') },
  { key: 'opened', label: __('Conversations'), numeric: true },
  { key: 'resolved', label: __('Resolved'), numeric: true },
  { key: 'response', label: __('Avg first response'), numeric: true, format: duration },
]

const agents = computed(() => props.data?.agents || [])
const availability = computed(() => props.data?.availability || {})

const workload = computed(() =>
  agents.value
    .filter((row) => row.replies || row.resolved)
    .slice(0, 10)
    .map((row) => ({ name: row.name, replies: row.replies, resolved: row.resolved })),
)

const replies = computed(() => withLabels(props.data?.replies, props.data?.range?.hourly))
</script>

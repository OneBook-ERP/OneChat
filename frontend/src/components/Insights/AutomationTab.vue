<template>
  <div class="flex flex-col gap-10">
    <InsightsSection id="insights-bots" :title="__('Chatbots')" :description="rangeLabel">
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <NumberCard v-for="card in cards" :key="card.title" v-bind="card" :loading="loading" />
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ChartCard class="h-80 lg:col-span-2">
            <AreaChart
              :data="activity"
              x="label"
              :y="['automated', 'agent']"
              :series-config="{ automated: { label: __('Automated replies') }, agent: { label: __('Agent replies') } }"
              :x-axis="{ type: 'category' }"
              stacked
              :loading="loading"
              :title="__('Automated vs agent replies')"
              :subtitle="__('How much of the talking bots do')"
            />
          </ChartCard>
          <ChartCard class="h-80">
            <DonutChart
              :data="outcomes"
              category="name"
              value="value"
              :center-label="__('runs')"
              :loading="loading"
              :title="__('How flow runs ended')"
              :subtitle="rangeLabel"
            />
          </ChartCard>
        </div>

        <InsightsTable
          :title="__('Flows')"
          :subtitle="__('Runs started in this period')"
          :columns="flowColumns"
          :rows="data?.flows || []"
          row-key="flow"
          :loading="loading"
          :empty-text="__('No flow runs in this period')"
        >
          <template #name="{ row }">
            <router-link :to="{ name: 'FlowBuilder', params: { name: row.flow } }" class="text-ink-gray-8 hover:underline">
              {{ row.name }}
            </router-link>
          </template>
        </InsightsTable>

        <InsightsTable
          :title="__('Where customers drop off')"
          :subtitle="__('The step a run was on when it stopped, timed out or failed')"
          :columns="dropColumns"
          :rows="drops"
          row-key="key"
          :loading="loading"
          :empty-text="__('No drop-offs in this period')"
        >
          <template #reason="{ row }">
            <ErrorHint :title="row.reason" :info="OUTCOME_HINTS[row.status] || null" side="top">
              <span
                class="cursor-default"
                :class="{ 'underline decoration-outline-gray-3 decoration-dotted underline-offset-4': OUTCOME_HINTS[row.status] }"
                :tabindex="OUTCOME_HINTS[row.status] ? 0 : undefined"
              >
                {{ row.reason }}
              </span>
            </ErrorHint>
          </template>
        </InsightsTable>
      </div>
    </InsightsSection>

    <InsightsSection id="insights-rules" :title="__('Auto replies and errors')" :description="rangeLabel">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InsightsTable
          :title="__('Auto reply rules')"
          :subtitle="__('Replies sent since each rule was created')"
          :columns="ruleColumns"
          :rows="data?.auto_reply_rules || []"
          :loading="loading"
          :empty-text="__('No auto reply rules yet')"
        />
        <RankedList
          :title="__('Failed runs')"
          :subtitle="__('Most common errors')"
          :rows="data?.failures || []"
          :tip="(row) => explainAutomation(row.name)"
          :loading="loading"
          :empty-text="__('No failed runs in this period')"
        />
      </div>
    </InsightsSection>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { AreaChart, ChartCard, DonutChart, NumberCard } from 'frappe-ui/charts'
import InsightsSection from '@/components/Insights/InsightsSection.vue'
import InsightsTable from '@/components/Insights/InsightsTable.vue'
import RankedList from '@/components/Insights/RankedList.vue'
import ErrorHint from '@/components/Insights/ErrorHint.vue'
import { OUTCOME_HINTS, explainAutomation } from '@/data/whatsappErrors'
import { OUTCOMES, kpi, percentText, share, withLabels } from '@/components/Insights/insights'
import { timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  rangeLabel: { type: String, default: '' },
})

const cards = computed(() => {
  const summary = props.data?.summary || {}
  return [
    kpi(__('Flow runs'), summary.started),
    kpi(__('Finished'), summary.completed),
    kpi(__('Stopped for no reply'), summary.expired, { negativeIsBetter: true }),
    kpi(__('Failed runs'), summary.failed, { negativeIsBetter: true }),
    kpi(__('Conversations with a bot'), share(summary.with_bot || 0, summary.conversations || 0), { suffix: '%', compact: false }),
    kpi(__('Solved without an agent'), summary.bot_only),
    kpi(__('Automated replies'), summary.automated),
    kpi(__('Notifications sent'), summary.notifications),
  ]
})

const activity = computed(() => withLabels(props.data?.activity, props.data?.range?.hourly))

const outcomes = computed(() => (props.data?.outcomes || []).map((row) => ({ name: __(OUTCOMES[row.name] || row.name), value: row.value })))

const flowColumns = [
  { key: 'name', label: __('Flow') },
  { key: 'started', label: __('Runs'), numeric: true },
  { key: 'completed', label: __('Finished'), numeric: true },
  { key: 'active', label: __('In progress'), numeric: true },
  { key: 'stopped', label: __('Stopped'), numeric: true },
  { key: 'expired', label: __('No reply'), numeric: true },
  { key: 'failed', label: __('Failed'), numeric: true },
  { key: 'completion_rate', label: __('Finish rate'), numeric: true, format: percentText },
]

const dropColumns = [
  { key: 'flow', label: __('Flow') },
  { key: 'step', label: __('Step') },
  { key: 'reason', label: __('Why') },
  { key: 'count', label: __('Runs'), numeric: true },
]

const drops = computed(() =>
  (props.data?.drop_offs || []).map((row) => ({
    ...row,
    key: `${row.flow}-${row.step}-${row.status}`,
    reason: __(OUTCOMES[row.status] || row.status),
  })),
)

const ruleColumns = [
  { key: 'rule_name', label: __('Rule') },
  { key: 'enabled', label: __('Status'), format: (value) => (value ? __('On') : __('Off')) },
  { key: 'reply_count', label: __('Replies'), numeric: true },
  { key: 'last_replied_at', label: __('Last used'), numeric: true, format: (value) => (value ? timeAgo(value) : '—') },
]
</script>

<template>
  <div class="flex flex-col gap-10">
    <InsightsSection id="insights-templates" :title="__('Template messages')" :description="rangeLabel">
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <NumberCard v-for="card in cards" :key="card.title" v-bind="card" :loading="loading" />
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ChartCard class="h-80 lg:col-span-2">
            <FunnelChart
              :data="funnel"
              category="stage"
              value="count"
              show-percentages
              :loading="loading"
              :title="__('From sent to read')"
              :subtitle="__('Every template message sent in this period')"
            />
          </ChartCard>
          <RankedList
            :title="__('Why messages failed')"
            :subtitle="__('Reasons WhatsApp gave')"
            :rows="failures"
            :tip="failureTip"
            :loading="loading"
            :empty-text="__('No failed messages in this period')"
          />
        </div>

        <InsightsTable
          :title="__('Top templates')"
          :subtitle="__('By messages sent')"
          :columns="templateColumns"
          :rows="data?.templates || []"
          row-key="template"
          :loading="loading"
          :empty-text="__('No templates sent in this period')"
        />
      </div>
    </InsightsSection>

    <InsightsSection id="insights-broadcasts" :title="__('Broadcasts')" :description="__('Broadcasts created in this period')">
      <InsightsTable
        :title="__('Broadcast results')"
        :subtitle="__('Delivery and reads for each broadcast')"
        :columns="broadcastColumns"
        :rows="data?.broadcasts || []"
        :loading="loading"
        :empty-text="__('No broadcasts in this period')"
      >
        <template #title="{ row }">
          <div class="flex min-w-0 flex-col">
            <TruncatedText class="truncate" :text="row.title || row.name" />
            <span class="text-xs text-ink-gray-5">{{ formatDate(row.creation) }}</span>
          </div>
        </template>
        <template #status="{ row }">
          <CampaignStatusBadge :status="row.status" />
        </template>
      </InsightsTable>
    </InsightsSection>

    <InsightsSection id="insights-audience" :title="__('Audience')" :description="rangeLabel">
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <NumberCard v-for="card in audienceCards" :key="card.title" v-bind="card" :loading="loading" />
        </div>
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ChartCard class="h-80 lg:col-span-2">
            <BarChart
              :data="audience"
              x="label"
              :y="['joined', 'opted_out']"
              :series-config="{ joined: { label: __('New contacts') }, opted_out: { label: __('Opted out') } }"
              :x-axis="{ type: 'category' }"
              :loading="loading"
              :title="__('Growth')"
              :subtitle="__('New contacts against opt-outs')"
            />
          </ChartCard>
          <ChartCard class="h-80">
            <DonutChart
              :data="templateStatus"
              category="name"
              value="value"
              :center-label="__('templates')"
              :loading="loading"
              :title="__('Template approval')"
              :subtitle="__('All templates, as of now')"
            />
          </ChartCard>
          <RankedList
            :title="__('Chat links')"
            :subtitle="__('Conversations started from each link')"
            :rows="data?.chat_links || []"
            :loading="loading"
            :empty-text="__('No chat link conversations in this period')"
          />
          <RankedList
            :title="__('Form responses')"
            :subtitle="__('Submissions per form')"
            :rows="data?.forms || []"
            :loading="loading"
            :empty-text="__('No form responses in this period')"
          />
        </div>
      </div>
    </InsightsSection>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { BarChart, ChartCard, DonutChart, FunnelChart, NumberCard } from 'frappe-ui/charts'
import CampaignStatusBadge from '@/components/Campaigns/CampaignStatusBadge.vue'
import InsightsSection from '@/components/Insights/InsightsSection.vue'
import InsightsTable from '@/components/Insights/InsightsTable.vue'
import RankedList from '@/components/Insights/RankedList.vue'
import { errorCode, explainError } from '@/data/whatsappErrors'
import { kpi, percentText, withLabels } from '@/components/Insights/insights'
import { formatDate } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  rangeLabel: { type: String, default: '' },
})

const cards = computed(() => {
  const funnel = props.data?.funnel || {}
  return [
    kpi(__('Templates sent'), funnel.sent),
    kpi(__('Delivered'), funnel.delivery_rate, { suffix: '%', precision: 0, compact: false }),
    kpi(__('Read'), funnel.read_rate, { suffix: '%', precision: 0, compact: false }),
    kpi(__('Failed'), funnel.failed, { negativeIsBetter: true }),
  ]
})

const funnel = computed(() => {
  const counts = props.data?.funnel
  if (!counts?.sent) return []

  return [
    { stage: __('Sent'), count: counts.sent },
    { stage: __('Delivered'), count: counts.delivered },
    { stage: __('Read'), count: counts.read },
  ]
})

const failures = computed(() => (props.data?.failures || []).map((row) => ({ ...row, label: row.name || __('No reason given') })))

function failureTip(row) {
  const known = explainError(row.name)
  return { code: errorCode(row.name), meaning: known?.meaning, action: known?.action }
}

const templateColumns = [
  { key: 'name', label: __('Template') },
  { key: 'sent', label: __('Sent'), numeric: true },
  { key: 'delivery_rate', label: __('Delivered'), numeric: true, format: percentText },
  { key: 'read_rate', label: __('Read'), numeric: true, format: percentText },
  { key: 'failed', label: __('Failed'), numeric: true },
]

const broadcastColumns = [
  { key: 'title', label: __('Broadcast') },
  { key: 'status', label: __('Status') },
  { key: 'recipient_count', label: __('Recipients'), numeric: true },
  { key: 'sent', label: __('Sent'), numeric: true },
  { key: 'skipped_count', label: __('Skipped'), numeric: true },
  { key: 'delivery_rate', label: __('Delivered'), numeric: true, format: percentText },
  { key: 'read_rate', label: __('Read'), numeric: true, format: percentText },
  { key: 'failed', label: __('Failed'), numeric: true },
]

const audienceCards = computed(() => {
  const summary = props.data?.audience_summary || {}
  return [
    kpi(__('New contacts'), summary.joined),
    kpi(__('Opted out'), summary.opted_out, { negativeIsBetter: true }),
    kpi(__('Opted out, all time'), summary.opted_out_total),
    kpi(__('All contacts'), summary.contacts),
  ]
})

const audience = computed(() => withLabels(props.data?.audience, props.data?.range?.hourly))

const templateStatus = computed(() =>
  (props.data?.template_status || []).map((row) => ({ name: __(titleCase(row.name)), value: row.value })),
)

function titleCase(value) {
  const text = String(value || '').toLowerCase()
  return text.charAt(0).toUpperCase() + text.slice(1)
}
</script>

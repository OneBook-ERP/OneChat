<template>
  <div class="flex flex-col gap-10">
    <div class="flex flex-wrap items-center justify-between gap-3 rounded-5 border border-outline-gray-2 px-4 py-3">
      <div class="flex min-w-0 items-center gap-3">
        <span class="relative flex size-2.5 shrink-0">
          <span v-if="realtime.connected" class="absolute inline-flex size-full animate-ping rounded-full bg-surface-green-6 opacity-60" />
          <span
            class="relative inline-flex size-2.5 rounded-full"
            :class="realtime.connected ? 'bg-surface-green-6' : 'bg-surface-gray-4'"
          />
        </span>
        <div class="min-w-0">
          <p class="text-base font-medium text-ink-gray-8">
            {{ realtime.connected ? __('Live') : __('Reconnecting…') }}
            <span v-if="today !== null" class="font-normal text-ink-gray-6"> · {{ __('Today so far: {0}').format(money(today)) }}</span>
          </p>
          <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="syncText" />
        </div>
      </div>
      <Button variant="subtle" icon-left="lucide-refresh-cw" :loading="syncing" :label="__('Fetch from Meta')" @click="syncNow" />
    </div>

    <div v-if="data?.tiers?.length" class="flex flex-wrap items-center gap-2 text-sm text-ink-gray-6">
      <span class="font-medium text-ink-gray-7">{{ __('Volume tier this month') }}</span>
      <Badge
        v-for="row in data.tiers"
        :key="`${row.account}-${row.category}`"
        variant="subtle"
        theme="blue"
        :label="`${row.account} · ${__(row.category)}: ${tierLabel(row.tier)}`"
      />
    </div>

    <div v-if="problems.length" class="flex items-start gap-2 rounded-4 bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-7">
      <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <ul class="min-w-0 flex-1 space-y-0.5">
        <li v-for="problem in problems" :key="problem.text">
          <ErrorHint :title="problem.title" :info="problem.info" side="bottom">
            <span
              class="cursor-default"
              :class="{ 'underline decoration-dotted underline-offset-4': problem.info }"
              :tabindex="problem.info ? 0 : undefined"
            >
              {{ problem.text }}
            </span>
          </ErrorHint>
        </li>
      </ul>
    </div>

    <InsightsSection
      id="insights-spend"
      :title="__('Spend')"
      :description="__('{0}. Days Meta has not reported yet are estimated.').format(rangeLabel)"
    >
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <NumberCard v-for="card in cards" :key="card.title" v-bind="card" :loading="loading" />
        </div>

        <div class="rounded-5 border border-outline-gray-2 p-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p class="text-base font-medium text-ink-gray-8">{{ __('This month') }}</p>
              <p class="text-sm text-ink-gray-5">
                <template v-if="month.budget">
                  {{ __('{0} of {1} budget').format(money(month.spend), money(month.budget)) }}
                </template>
                <template v-else>{{ __('{0} so far. Set a budget to get alerts.').format(money(month.spend)) }}</template>
              </p>
            </div>
            <Button size="sm" variant="subtle" :label="month.budget ? __('Change budget') : __('Set budget')" @click="openBudget" />
          </div>
          <div v-if="month.budget" class="mt-3 h-2 overflow-hidden rounded-full bg-surface-gray-2">
            <div
              class="h-full rounded-full transition-all"
              :class="budgetColor"
              :style="{ width: `${Math.min(month.percent || 0, 100)}%` }"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ChartCard class="h-80 lg:col-span-2">
            <BarChart
              :data="days"
              x="label"
              :y="CATEGORY_KEYS"
              :series-config="seriesConfig"
              :x-axis="{ type: 'category' }"
              :y-axis="{ format: (value) => money(value) }"
              stacked
              :loading="loading"
              :title="__('Spend per day')"
              :subtitle="__('* estimated from your rates')"
            />
          </ChartCard>
          <ChartCard class="h-80">
            <DonutChart
              :data="categories"
              category="name"
              value="value"
              :format="(value) => money(value)"
              :loading="loading"
              :title="__('By category')"
              :subtitle="rangeLabel"
            />
          </ChartCard>
        </div>
      </div>
    </InsightsSection>

    <InsightsSection
      id="insights-where"
      :title="__('Where the money goes')"
      :description="__('Per template, broadcast and sender, estimated from each message\'s rate')"
    >
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InsightsTable
          v-if="data?.meta_templates?.length"
          class="lg:col-span-2"
          :title="__('Templates')"
          :subtitle="__('Reported by Meta for the last 90 days at most. Reads and clicks cover the last 7 days.')"
          :columns="metaTemplateColumns"
          :rows="data.meta_templates"
          row-key="key"
          :loading="loading"
        />
        <InsightsTable
          v-else
          :title="__('Templates')"
          :columns="spendColumns(__('Template'))"
          :rows="data?.templates || []"
          row-key="key"
          :loading="loading"
        />
        <InsightsTable
          v-if="(data?.numbers || []).length > 1"
          :title="__('By WhatsApp number')"
          :subtitle="__('Cost reported by Meta for each number')"
          :columns="numberColumns"
          :rows="data.numbers"
          row-key="key"
          :loading="loading"
        />
        <InsightsTable
          :title="__('Broadcasts')"
          :columns="spendColumns(__('Broadcast'))"
          :rows="data?.broadcasts || []"
          row-key="key"
          :loading="loading"
          :empty-text="__('No paid broadcast messages in this period')"
        />
        <InsightsTable :title="__('Sent by')" :columns="spendColumns(__('Sender'))" :rows="senders" row-key="key" :loading="loading" />
        <RankedList
          :title="__('By country')"
          :subtitle="__('Rates differ by the customer\'s country')"
          :rows="countries"
          :format="(value) => money(value)"
          :loading="loading"
        />
      </div>
    </InsightsSection>

    <InsightsSection id="insights-free" :title="__('Free messages')" :description="__('Messages WhatsApp did not charge for')">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <NumberCard v-for="card in freeCards" :key="card.title" v-bind="card" :loading="loading" />
      </div>
    </InsightsSection>

    <InsightsSection
      id="insights-rates"
      :title="__('Rates')"
      :description="
        __(
          'Used for live estimates. Rates from Meta are worked out from your actual spend each hour; your own rates are never overwritten.',
        )
      "
    >
      <InsightsTable
        :title="__('Price per paid message')"
        :columns="rateColumns"
        :rows="rates"
        :loading="loading"
        :empty-text="__('No rates yet. They appear after the first fetch from Meta, or add your own.')"
      >
        <template #source="{ row }">
          <Badge
            :theme="row.source === 'Meta' ? 'blue' : 'gray'"
            size="sm"
            :label="row.source === 'Meta' ? __('From Meta') : __('Yours')"
          />
        </template>
        <template #actions="{ row }">
          <div class="flex justify-end gap-1">
            <Button size="sm" variant="ghost" icon="lucide-pencil" :label="__('Edit')" @click="editRate(row)" />
            <Button size="sm" variant="ghost" icon="lucide-trash-2" :label="__('Delete')" @click="removeRate(row)" />
          </div>
        </template>
      </InsightsTable>
      <Button class="mt-3" variant="subtle" icon-left="lucide-plus" :label="__('Add rate')" @click="editRate(null)" />
    </InsightsSection>

    <ResponsiveDialog v-model:open="budgetOpen" :title="__('Monthly budget')" size="sm">
      <template #default>
        <FormControl
          v-model="budgetValue"
          type="number"
          :label="__('Budget ({0})').format(currency)"
          :description="__('You get a notification at 80% and 100%. Set 0 to turn alerts off.')"
        />
      </template>
      <template #actions>
        <Button class="w-full" variant="solid" :loading="saving" :label="__('Save')" @click="saveBudget" />
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog v-model:open="rateOpen" :title="rateForm.name ? __('Edit rate') : __('Add rate')" size="sm">
      <template #default>
        <div class="flex flex-col gap-3">
          <FormControl
            v-model="rateForm.country"
            :label="__('Country')"
            placeholder="IN"
            :description="__('Two-letter code, or * for every other country')"
          />
          <FormControl v-model="rateForm.category" type="select" :label="__('Category')" :options="categoryOptions" />
          <FormControl v-model="rateForm.rate" type="number" :label="__('Price per message ({0})').format(currency)" />
        </div>
      </template>
      <template #actions>
        <Button class="w-full" variant="solid" :loading="saving" :label="__('Save')" @click="saveRate" />
      </template>
    </ResponsiveDialog>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Badge, Button, FormControl, call, toast } from 'frappe-ui'
import { BarChart, ChartCard, DonutChart, NumberCard } from 'frappe-ui/charts'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import InsightsSection from '@/components/Insights/InsightsSection.vue'
import InsightsTable from '@/components/Insights/InsightsTable.vue'
import RankedList from '@/components/Insights/RankedList.vue'
import ErrorHint from '@/components/Insights/ErrorHint.vue'
import { explainMeta } from '@/data/whatsappErrors'
import { SOURCES, change, kpi, money as formatMoney } from '@/components/Insights/insights'
import { realtime, useSocket } from '@/data/socket'
import { useUI } from '@/stores/ui'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  rangeLabel: { type: String, default: '' },
})

const emit = defineEmits(['refresh'])

const ui = useUI()

const CATEGORY_KEYS = ['marketing', 'utility', 'authentication', 'service']
const CATEGORY_LABELS = { marketing: 'Marketing', utility: 'Utility', authentication: 'Authentication', service: 'Service', other: 'Other' }

const currency = computed(() => props.data?.currency || 'USD')
const month = computed(() => props.data?.month || {})
const summary = computed(() => props.data?.summary || {})

function money(value) {
  return formatMoney(value, currency.value)
}

const seriesConfig = Object.fromEntries(CATEGORY_KEYS.map((key) => [key, { label: __(CATEGORY_LABELS[key]) }]))
const categoryOptions = CATEGORY_KEYS.map((key) => ({ label: __(CATEGORY_LABELS[key]), value: key }))

const days = computed(() =>
  (props.data?.days || []).map((row) => {
    const date = new Date(`${row.at}T00:00:00`)
    const label = date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
    return { ...row, label: row.estimated || row.mixed ? `${label} *` : label }
  }),
)

const today = computed(() => {
  const now = new Date()
  const key = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const row = (props.data?.days || []).find((day) => day.at === key)
  return row ? CATEGORY_KEYS.reduce((sum, category) => sum + (row[category] || 0), 0) : null
})

const cards = computed(() => [
  kpi(__('Spend'), money(summary.value.spend), {
    compact: false,
    delta: change(summary.value.spend, summary.value.previous),
    deltaSuffix: '%',
    deltaCaption: __('vs previous period'),
    negativeIsBetter: true,
  }),
  kpi(__('Estimated part'), money(summary.value.estimated), { compact: false }),
  kpi(__('Paid messages'), summary.value.paid),
  kpi(
    __('Avg per paid message'),
    summary.value.per_message === null || summary.value.per_message === undefined ? '—' : money(summary.value.per_message),
    { compact: false },
  ),
])

const freeCards = computed(() => {
  const counts = props.data?.free || {}
  return [
    kpi(__('Replies within 24 hours'), counts.free_customer_service || 0),
    kpi(__('From ads and entry points'), counts.free_entry_point || 0),
    kpi(__('Paid'), summary.value.paid || 0),
  ]
})

const categories = computed(() =>
  (props.data?.categories || []).map((row) => ({ name: __(CATEGORY_LABELS[row.name] || row.name), value: row.value })),
)
const countries = computed(() => props.data?.countries || [])
const senders = computed(() => (props.data?.senders || []).map((row) => ({ ...row, name: __(SOURCES[row.key] || SOURCES.Other) })))
const rates = computed(() =>
  (props.data?.rates || []).map((row) => ({ ...row, category: __(CATEGORY_LABELS[row.category] || row.category), key: row.category })),
)

function spendColumns(label) {
  return [
    { key: 'name', label },
    { key: 'messages', label: __('Paid messages'), numeric: true },
    { key: 'cost', label: __('Est. cost'), numeric: true, format: (value) => money(value) },
  ]
}

const metaTemplateColumns = [
  { key: 'name', label: __('Template') },
  { key: 'sent', label: __('Sent'), numeric: true },
  { key: 'delivered', label: __('Delivered'), numeric: true },
  { key: 'read_rate', label: __('Read'), numeric: true, format: (value) => (value === null || value === undefined ? '—' : `${value}%`) },
  { key: 'clicked', label: __('Clicks'), numeric: true },
  { key: 'cost', label: __('Cost'), numeric: true, format: (value) => money(value) },
]

const numberColumns = [
  { key: 'name', label: __('Number') },
  { key: 'messages', label: __('Paid messages'), numeric: true },
  { key: 'cost', label: __('Cost'), numeric: true, format: (value) => money(value) },
]

function tierLabel(value) {
  const [lower, upper] = String(value || '').split(':')
  const short = (number) => (Number(number) >= 1000 ? `${Math.round(Number(number) / 1000)}K` : number)
  if (!upper || upper === '-1' || upper === 'inf') return __('{0}+ messages').format(short(lower))
  return __('{0}–{1} messages').format(short(lower), short(upper))
}

const rateColumns = [
  { key: 'country', label: __('Country'), format: (value) => (value === '*' ? __('All others') : value) },
  { key: 'category', label: __('Category') },
  { key: 'rate', label: __('Rate'), numeric: true, format: (value, row) => formatMoney(value, row.currency || currency.value) },
  { key: 'source', label: __('Source') },
  { key: 'actions', label: '' },
]

const syncText = computed(() => {
  const rows = props.data?.sync || []
  if (!rows.length) return __('Add the WhatsApp Business Account ID to your accounts to fetch spend from Meta.')
  const synced = rows
    .map((row) => row.synced_at)
    .filter(Boolean)
    .sort()
    .at(-1)
  if (allLive.value) {
    return synced ? __('Live from Meta, fetched {0}. Nothing is stored.').format(timeAgo(synced)) : __('Live from Meta. Nothing is stored.')
  }
  return synced ? __('Actual spend fetched from Meta {0}').format(timeAgo(synced)) : __('Not fetched from Meta yet')
})

const problems = computed(() => {
  const out = (props.data?.sync || [])
    .filter((row) => row.error)
    .map((row) => ({ text: __('{0}: {1}').format(row.account, row.error), title: row.error, info: explainMeta(row.error) }))
  if (props.data?.template_problem) {
    const text = props.data.template_problem
    out.push({ text, title: text, info: /\(#\d+\)/.test(text) ? explainMeta(text) : null })
  }
  if (props.data?.meta_limited)
    out.push({ text: __('Meta keeps one year of cost data. Older days in this range show only estimates from your rates.'), info: null })
  if (summary.value.unpriced) {
    out.push(
      __('{0} paid messages have no rate yet, so they are not in the estimate. Add a rate or wait for Meta.').format(
        summary.value.unpriced,
      ),
    )
  }
  return out
})

const budgetColor = computed(() => {
  const percent = month.value.percent || 0
  if (percent >= 100) return 'bg-surface-red-5'
  if (percent >= 80) return 'bg-surface-amber-5'
  return 'bg-surface-green-6'
})

const allLive = computed(() => {
  const live = props.data?.live || []
  return live.length > 0 && live.length >= (props.data?.sync || []).length
})

const syncing = ref(false)
const saving = ref(false)
const budgetOpen = ref(false)
const budgetValue = ref(0)
const rateOpen = ref(false)
const rateForm = reactive({ name: null, country: '', category: 'marketing', rate: 0 })

async function syncNow() {
  syncing.value = true
  try {
    toast.success(await call('onechat.insights.costs.sync_now'))
    if (props.data?.live?.length) emit('refresh')
    else setTimeout(() => emit('refresh'), 15000)
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    syncing.value = false
  }
}

function openBudget() {
  budgetValue.value = month.value.budget || 0
  budgetOpen.value = true
}

async function saveBudget() {
  saving.value = true
  try {
    await call('onechat.insights.costs.set_budget', { amount: budgetValue.value })
    budgetOpen.value = false
    emit('refresh')
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    saving.value = false
  }
}

function editRate(row) {
  Object.assign(
    rateForm,
    row
      ? { name: row.name, country: row.country, category: row.key, rate: row.rate }
      : { name: null, country: '', category: 'marketing', rate: 0 },
  )
  rateOpen.value = true
}

async function saveRate() {
  saving.value = true
  try {
    await call('onechat.insights.costs.save_rate', { ...rateForm })
    rateOpen.value = false
    emit('refresh')
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    saving.value = false
  }
}

function removeRate(row) {
  ui.confirm({
    title: __('Delete this rate?'),
    message: __('Estimates for {0} {1} messages will use the rate for all other countries, if there is one.').format(
      row.country,
      row.category,
    ),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      try {
        await call('onechat.insights.costs.delete_rate', { name: row.name })
        emit('refresh')
      } catch (err) {
        toast.error(errorMessage(err))
      }
    },
  })
}

let timer = null

function onCost() {
  clearTimeout(timer)
  timer = setTimeout(() => emit('refresh'), 3000)
}

onMounted(() => useSocket().on('onechat_cost', onCost))
onBeforeUnmount(() => {
  clearTimeout(timer)
  useSocket().off('onechat_cost', onCost)
})
</script>

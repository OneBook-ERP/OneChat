<template>
  <div class="flex flex-col gap-10">
    <InsightsSection id="insights-orders" :title="__('Catalog orders')" :description="rangeLabel">
      <div class="flex flex-col gap-4">
        <p v-if="data && !data.ready" class="flex items-center gap-1.5 text-sm text-ink-gray-5">
          <span class="lucide-info size-4 shrink-0" aria-hidden="true" />
          {{ __('Connect ERPNext to see which orders became Sales Orders and were paid.') }}
        </p>
        <ErrorMessage v-if="data?.warning" :message="data.warning" />

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <NumberCard v-for="card in cards" :key="card.title" v-bind="card" :loading="loading" />
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ChartCard class="h-80 lg:col-span-2">
            <BarChart
              :data="timeline"
              x="label"
              :y="['orders', 'sales_orders']"
              :series-config="{ orders: { label: __('WhatsApp orders') }, sales_orders: { label: __('Became Sales Orders') } }"
              :x-axis="{ type: 'category' }"
              :loading="loading"
              :title="__('Orders over time')"
              :subtitle="__('Orders placed from the WhatsApp catalog')"
            />
          </ChartCard>
          <ChartCard class="h-80">
            <FunnelChart
              :data="funnel"
              category="stage"
              value="count"
              show-percentages
              :loading="loading"
              :title="__('From order to payment')"
              :subtitle="__('Each WhatsApp order in this period')"
            />
          </ChartCard>
        </div>
      </div>
    </InsightsSection>

    <InsightsSection
      id="insights-products"
      :title="__('Products')"
      :description="__('Revenue by product, at the prices customers saw on WhatsApp')"
    >
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <RankedList
          :title="__('Top products')"
          :subtitle="__('By order value')"
          :rows="data?.top_products || []"
          :format="(value) => money(value, data?.currency || 'INR')"
          :loading="loading"
          :empty-text="__('No catalog orders in this period')"
        />
        <InsightsTable
          class="lg:col-span-2"
          :title="__('All products')"
          :subtitle="__('Paid value counts orders that are fully paid')"
          :columns="productColumns"
          :rows="data?.products || []"
          row-key="code"
          :loading="loading"
          :empty-text="__('No catalog orders in this period')"
        />
      </div>
    </InsightsSection>

    <InsightsSection id="insights-order-list" :title="__('Orders')" :description="__('Latest 100 orders and where each one stands')">
      <InsightsTable
        :title="__('Order list')"
        :subtitle="__('Open the chat or the Sales Order from here')"
        :columns="orderColumns"
        :rows="data?.recent || []"
        :loading="loading"
        :empty-text="__('No catalog orders in this period')"
      >
        <template #customer="{ row }">
          <div class="flex min-w-0 flex-col">
            <router-link
              v-if="row.contact"
              :to="{ name: 'Inbox', params: { contact: row.contact } }"
              class="truncate text-ink-gray-8 hover:underline"
            >
              {{ row.customer }}
            </router-link>
            <span v-else class="truncate">{{ row.customer || '—' }}</span>
            <span class="text-xs text-ink-gray-5">{{ formatDate(row.creation) }}</span>
          </div>
        </template>
        <template #sales_order="{ row }">
          <a
            v-if="row.sales_order"
            :href="row.sales_order_url"
            target="_blank"
            rel="noopener"
            class="truncate text-ink-gray-8 hover:underline"
          >
            {{ row.sales_order }}
          </a>
          <span v-else class="text-ink-gray-5">—</span>
        </template>
        <template #state="{ row }">
          <Badge size="sm" variant="subtle" :theme="STATE_THEME[row.state] || 'gray'" :label="__(row.state)" />
        </template>
      </InsightsTable>
    </InsightsSection>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, ErrorMessage } from 'frappe-ui'
import { BarChart, ChartCard, FunnelChart, NumberCard } from 'frappe-ui/charts'
import InsightsSection from '@/components/Insights/InsightsSection.vue'
import InsightsTable from '@/components/Insights/InsightsTable.vue'
import RankedList from '@/components/Insights/RankedList.vue'
import { kpi, money, withLabels } from '@/components/Insights/insights'
import { formatDate, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  rangeLabel: { type: String, default: '' },
})

const STATE_THEME = {
  Paid: 'green',
  'Part paid': 'blue',
  Unpaid: 'amber',
  Draft: 'gray',
  Cancelled: 'red',
  'No order': 'gray',
}

const cards = computed(() => {
  const summary = props.data?.summary || {}
  return [
    kpi(__('WhatsApp orders'), summary.orders),
    kpi(__('Became Sales Orders'), summary.sales_orders, { target: summary.orders || undefined }),
    kpi(__('Paid'), summary.paid, { target: summary.sales_orders || undefined }),
    kpi(__('Collected'), summary.paid_label || '—', { compact: false, target: summary.revenue_label || undefined }),
  ]
})

const timeline = computed(() => withLabels(props.data?.timeline, props.data?.range?.hourly))

const funnel = computed(() => {
  const rows = props.data?.funnel || []
  if (!rows[0]?.count) return []
  return rows.map((row) => ({ ...row, stage: __(row.stage) }))
})

const productColumns = [
  { key: 'name', label: __('Product') },
  { key: 'orders', label: __('Orders'), numeric: true },
  { key: 'qty', label: __('Qty'), numeric: true, format: (value) => formatNumber(value) },
  { key: 'value_label', label: __('Order value'), numeric: true },
  { key: 'paid_label', label: __('Paid value'), numeric: true },
]

const orderColumns = [
  { key: 'customer', label: __('Customer') },
  { key: 'items', label: __('Items'), numeric: true },
  { key: 'value_label', label: __('Value'), numeric: true },
  { key: 'sales_order', label: __('Sales Order') },
  { key: 'state', label: __('Payment') },
  { key: 'paid_label', label: __('Paid'), numeric: true },
]
</script>

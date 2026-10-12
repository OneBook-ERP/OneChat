<template>
  <AppHeader>
    <template #actions>
      <Button variant="subtle" icon-left="lucide-refresh-cw" :label="__('Refresh')" :loading="report.loading" @click="report.reload()" />
      <Button variant="solid" icon-left="lucide-download" :label="__('Export CSV')" :disabled="!rows.length" @click="exportOpen = true" />
    </template>
  </AppHeader>

  <div class="mx-auto w-full max-w-[1100px] px-3 pb-24 pt-5 sm:px-5 sm:pb-10">
    <div class="flex flex-col gap-5">
      <div class="flex flex-wrap items-end gap-2">
        <FormControl v-model="filters.from_date" class="w-[calc(50%-0.25rem)] sm:w-40" type="date" :label="__('From')" />
        <FormControl v-model="filters.to_date" class="w-[calc(50%-0.25rem)] sm:w-40" type="date" :label="__('To')" />
        <FormControl v-model="filters.status" class="w-full sm:w-44" type="select" :label="__('Status')" :options="statusOptions" />
        <Button v-if="changed" variant="ghost" icon-left="lucide-x" :label="__('Clear')" @click="reset" />
      </div>

      <div class="grid grid-cols-2 gap-3 md:grid-cols-5 max-sm:[&>*:last-child]:col-span-2">
        <NumberCard :title="__('Recipients')" :value="totals.recipients" :loading="report.loading && !report.data" />
        <NumberCard :title="__('Sent')" :value="totals.sent" :loading="report.loading && !report.data" />
        <NumberCard :title="__('Delivered')" :value="totals.delivered" :loading="report.loading && !report.data" />
        <NumberCard :title="__('Read')" :value="totals.read" :loading="report.loading && !report.data" />
        <NumberCard :title="__('Failed')" :value="totals.failed" :loading="report.loading && !report.data" />
      </div>

      <ErrorMessage v-if="report.error" :message="errorMessage(report.error)" />

      <ListSkeleton v-if="report.loading && !report.data" :avatar="false" />

      <EmptyState
        v-else-if="!rows.length"
        icon="lucide-chart-no-axes-column"
        :title="__('No broadcasts in this period')"
        :description="__('Only sent broadcasts are counted. Widen the dates or clear the status filter.')"
      />

      <div v-else-if="!isDesktop" class="flex flex-col divide-y divide-outline-gray-1 rounded-5 border border-outline-gray-1">
        <div
          v-for="row in pageRows"
          :key="row.name"
          role="button"
          tabindex="0"
          class="flex min-h-14 cursor-pointer items-center gap-3 px-3 py-2 transition-colors first:rounded-t-5 last:rounded-b-5 active:bg-surface-gray-2"
          @click="openDetail(row.name)"
          @keydown.enter.self="openDetail(row.name)"
        >
          <div class="flex min-w-0 flex-1 flex-col gap-1">
            <TruncatedText as="p" class="truncate text-base text-ink-gray-9" :text="row.title" />
            <div class="flex min-w-0 items-center gap-1.5">
              <CampaignStatusBadge :status="row.status" size="sm" />
              <TruncatedText class="truncate text-sm text-ink-gray-5" :text="formatDateTime(row.creation)" />
            </div>
          </div>
          <div class="flex shrink-0 flex-col items-end gap-1 text-sm tabular-nums">
            <span class="text-ink-gray-7">{{ __('{0} sent').format(formatNumber(row.sent)) }}</span>
            <span v-if="row.failed" class="text-ink-red-3">{{ __('{0} failed').format(formatNumber(row.failed)) }}</span>
          </div>
          <span class="lucide-chevron-right size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
        </div>
      </div>

      <ListScroll v-else>
        <ListView
          :columns="viewColumns"
          :rows="pageRows"
          row-key="name"
          :options="{ selectable: false, showTooltip: false, rowHeight: 52, onRowClick: (row) => openDetail(row.name) }"
        >
          <template #cell="{ column, row, item }">
            <div v-if="column.key === 'title'" class="min-w-0">
              <TruncatedText as="p" class="truncate text-base text-ink-gray-9" :text="row.title" />
              <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="formatDateTime(row.creation)" />
            </div>
            <CampaignStatusBadge v-else-if="column.key === 'status'" :status="row.status" size="sm" />
            <TruncatedText v-else class="truncate text-base tabular-nums text-ink-gray-7" :text="formatNumber(item)" />
          </template>
        </ListView>
      </ListScroll>

      <Pagination v-if="rows.length > PAGE_SIZES[0]" v-model:page="page" :total="rows.length" />

      <p v-if="rows.length" class="px-1 text-sm text-ink-gray-5">
        {{ __('{0} broadcasts. Delivered includes read; sent includes delivered and read.').format(rows.length) }}
      </p>
    </div>
  </div>

  <BroadcastDetail v-model:open="detailOpen" :name="active" @changed="report.reload()" />

  <ExportDialog
    v-model:open="exportOpen"
    :default-name="`delivery-report-${filters.from_date || 'all'}-${filters.to_date || dayjs().format('YYYY-MM-DD')}`"
    :filtered="narrowed"
    :filtered-count="rows.length"
    :build="buildExport"
  />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, call, createResource, dayjs } from 'frappe-ui'
import { NumberCard } from 'frappe-ui/charts'
import { ListView } from 'frappe-ui/experimental'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import ExportDialog from '@/components/Common/ExportDialog.vue'
import ListScroll from '@/components/Common/ListScroll.vue'
import ListSkeleton from '@/components/Common/ListSkeleton.vue'
import Pagination from '@/components/Common/Pagination.vue'
import BroadcastDetail from '@/components/Campaigns/BroadcastDetail.vue'
import CampaignStatusBadge from '@/components/Campaigns/CampaignStatusBadge.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { field, refField, useQueryState } from '@/composables/useQueryState'
import { PAGE_SIZES, pageLength, pageOf } from '@/utils/paging'
import { errorMessage, formatDateTime, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const defaults = () => ({
  from_date: dayjs().subtract(1, 'month').format('YYYY-MM-DD'),
  to_date: dayjs().format('YYYY-MM-DD'),
  status: '',
})

const filters = reactive(defaults())
const page = ref(1)

const state = useQueryState(
  [
    field('from', filters, 'from_date', defaults().from_date),
    field('to', filters, 'to_date', defaults().to_date),
    field('status', filters, 'status', ''),
    refField('page', page, 1),
  ],
  { size: true },
)
const detailOpen = ref(false)
const active = ref(null)

const statusOptions = [
  { label: __('Any status'), value: '' },
  ...['Queued', 'In Progress', 'Completed', 'Partially Failed'].map((value) => ({ label: __(value), value })),
]

const columns = [
  { key: 'title', label: __('Broadcast'), width: 'minmax(0,2fr)' },
  { key: 'recipient_count', label: __('Recipients'), align: 'right', hideOnMobile: true },
  { key: 'sent', label: __('Sent'), align: 'right' },
  { key: 'delivered', label: __('Delivered'), align: 'right', hideOnMobile: true },
  { key: 'read', label: __('Read'), align: 'right', hideOnMobile: true },
  { key: 'failed', label: __('Failed'), align: 'right' },
  { key: 'status', label: __('Status'), width: '130px', hideOnMobile: true },
]

const { isDesktop } = useBreakpoint()

const viewColumns = computed(() =>
  columns
    .filter((column) => isDesktop.value || !column.hideOnMobile)
    .map((column) => ({ ...column, width: column.width === 'minmax(0,2fr)' ? 2 : column.width || 0.8 })),
)

const report = createResource({
  url: 'onechat.campaigns.broadcasts.delivery_report',
  makeParams: () => ({
    filters: Object.fromEntries(Object.entries(filters).filter(([, value]) => value)),
  }),
  auto: true,
})

function shape(row) {
  const read = Number(row.read_count) || 0
  const delivered = (Number(row.delivered_count) || 0) + read

  return {
    ...row,
    read,
    delivered,
    sent: (Number(row.sent_count) || 0) + delivered,
    failed: Number(row.failed_count) || 0,
  }
}

const rows = computed(() => (report.data?.rows || []).map(shape))
const exportOpen = ref(false)
const narrowed = computed(() => Object.values(filters).some(Boolean))

const totals = computed(() =>
  rows.value.reduce(
    (sum, row) => ({
      recipients: sum.recipients + (Number(row.recipient_count) || 0),
      sent: sum.sent + row.sent,
      delivered: sum.delivered + row.delivered,
      read: sum.read + row.read,
      failed: sum.failed + row.failed,
    }),
    { recipients: 0, sent: 0, delivered: 0, read: 0, failed: 0 },
  ),
)

const changed = computed(() => JSON.stringify(filters) !== JSON.stringify(defaults()))

const pageRows = computed(() => pageOf(rows.value, page.value))

watch(pageLength, () => !state.restoring() && (page.value = 1))

watch(
  filters,
  () => {
    if (!state.restoring()) page.value = 1
    report.reload()
  },
  { deep: true },
)

function reset() {
  Object.assign(filters, defaults())
}

function openDetail(name) {
  active.value = name
  detailOpen.value = true
}

async function buildExport(scope) {
  const source =
    scope === 'filtered' ? rows.value : ((await call('onechat.campaigns.broadcasts.delivery_report', {}))?.rows || []).map(shape)
  const fields = [
    { key: 'name', label: __('ID') },
    { key: 'title', label: __('Broadcast') },
    { key: 'created', label: __('Created on') },
    ...columns.filter((column) => column.key !== 'title'),
  ]

  return { columns: fields, rows: source.map((row) => ({ ...row, created: formatDateTime(row.creation) })) }
}
</script>

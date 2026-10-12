<template>
  <AppHeader>
    <template #actions>
      <Button variant="solid" icon-left="lucide-send" :label="__('New broadcast')" data-tour="new-broadcast" @click="wizard = true" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <template v-if="view === 'calendar'">
      <div class="mb-3 flex items-center justify-between gap-2">
        <TabButtons v-model="view" :options="views" />
      </div>
      <BroadcastCalendar ref="calendar" :status-of="statusOf" @open="openDetail" />
    </template>

    <DocListView
      v-else
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search broadcasts')"
      empty-icon="lucide-send"
      :empty-title="__('No broadcasts yet')"
      :empty-description="__('Send an approved template to a recipient list or a batch of numbers.')"
      export-name="broadcasts"
      :deletable="false"
      @open="openDetail"
    >
      <template #toolbar>
        <TabButtons v-model="view" :options="views" />
      </template>

      <template #cell-title="{ row }">
        <div class="min-w-0">
          <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.title" />
          <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="row.template || row.name" />
        </div>
      </template>

      <template #cell-status="{ row }">
        <CampaignStatusBadge :status="statusOf(row)" />
      </template>

      <template #cell-sent_count="{ row }">
        <div v-if="row.docstatus === 1" class="flex w-full min-w-0 flex-col gap-1">
          <span class="text-sm text-ink-gray-6"> {{ formatNumber(row.sent_count) }} / {{ formatNumber(row.recipient_count) }} </span>
          <div class="h-1.5 w-full overflow-hidden rounded-full bg-surface-gray-2">
            <div class="h-full rounded-full bg-surface-gray-7 transition-all" :style="{ width: `${percent(row)}%` }" />
          </div>
        </div>
        <span v-else class="text-base text-ink-gray-5">{{ __('{0} recipients').format(formatNumber(row.recipient_count)) }}</span>
      </template>
    </DocListView>
  </div>

  <BroadcastWizard v-model:open="wizard" :segment="segment" @created="created" />
  <BroadcastDetail v-model:open="detailOpen" :name="active" @changed="refresh" @open="openFollowUp" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, TabButtons } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import BroadcastCalendar from '@/components/Campaigns/BroadcastCalendar.vue'
import BroadcastDetail from '@/components/Campaigns/BroadcastDetail.vue'
import BroadcastWizard from '@/components/Campaigns/BroadcastWizard.vue'
import CampaignStatusBadge from '@/components/Campaigns/CampaignStatusBadge.vue'
import { useDocList } from '@/composables/useDocList'
import { formatDateTime, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const REFRESH = 10000
const VIEW_KEY = 'onechat.broadcasts.view'

const route = useRoute()
const router = useRouter()
const wizard = ref(false)
const segment = ref(null)
const detailOpen = ref(false)
const active = ref(null)
const calendar = ref(null)
const view = ref(savedView())
const views = [
  { label: __('List'), value: 'list', iconLeft: 'lucide-list' },
  { label: __('Calendar'), value: 'calendar', iconLeft: 'lucide-calendar-days' },
]
let timer = null

function savedView() {
  try {
    return localStorage.getItem(VIEW_KEY) === 'calendar' ? 'calendar' : 'list'
  } catch {
    return 'list'
  }
}

watch(view, (value) => {
  try {
    localStorage.setItem(VIEW_KEY, value)
  } catch {
    return
  }
})

function refresh() {
  list.refresh()
  calendar.value?.refresh()
}

const list = useDocList({
  doctype: 'Bulk WhatsApp Message',
  fields: [
    'name',
    'title',
    'template',
    'recipient_type',
    'recipient_list',
    'segment',
    'recipient_count',
    'sent_count',
    'status',
    'scheduled_time',
    'docstatus',
    'creation',
  ],
  searchFields: ['title', 'template', 'recipient_list', 'name'],
  quickFilters: [
    {
      key: 'status',
      label: 'Status',
      options: ['Draft', 'Queued', 'In Progress', 'Completed', 'Partially Failed'].map((value) => ({ label: __(value), value })),
    },
  ],
  sortOptions: [
    { label: 'Newest first', value: 'creation desc' },
    { label: 'Recently updated', value: 'modified desc' },
    { label: 'Scheduled time', value: 'scheduled_time desc' },
  ],
  orderBy: 'creation desc',
})

const columns = [
  { key: 'title', label: 'Broadcast', width: 'minmax(0,2fr)' },
  { key: 'status', label: 'Status', width: '130px', format: (value, row) => statusOf(row) },
  {
    key: 'sent_count',
    label: 'Progress',
    width: 'minmax(0,1.2fr)',
    hideOnMobile: true,
    format: (value, row) => `${value}/${row.recipient_count}`,
  },
  {
    key: 'scheduled_time',
    label: 'When',
    width: '170px',
    hideOnMobile: true,
    format: (value, row) => formatDateTime(value || row.creation),
  },
]

function statusOf(row) {
  if (row.docstatus === 0 && row.scheduled_time) return 'Scheduled'
  if (row.docstatus === 2) return 'Cancelled'

  return row.status || 'Draft'
}

function percent(row) {
  return row.recipient_count ? Math.min(100, Math.round((row.sent_count / row.recipient_count) * 100)) : 0
}

function openDetail(row) {
  active.value = row.name
  detailOpen.value = true
}

function openFollowUp(name) {
  refresh()
  openDetail({ name })
}

watch(
  () => route.query.segment,
  (value) => {
    if (!value) return
    segment.value = value
    wizard.value = true
    router.replace({ query: { ...route.query, segment: undefined } })
  },
  { immediate: true },
)

watch(wizard, (value) => {
  if (!value) segment.value = null
})

function created(name) {
  refresh()
  openDetail({ name })
}

function tick() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    if (!document.hidden && list.rows.value.some((row) => ['Queued', 'In Progress'].includes(row.status))) list.refresh()
    tick()
  }, REFRESH)
}

tick()
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <AppHeader />

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search by flow or run id')"
      empty-icon="lucide-scroll-text"
      :empty-title="__('No runs yet')"
      :empty-description="__('Every time a flow runs, a log of its steps shows up here.')"
      export-name="flow-runs"
      @open="(row) => openLog(row.name)"
    >
      <template #cell-flow="{ row }">
        <div class="min-w-0">
          <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.flow" />
          <TruncatedText as="p" class="truncate text-sm text-ink-gray-5 md:hidden" :text="formatDateTime(row.start_time)" />
        </div>
      </template>

      <template #cell-run_id="{ row }">
        <TruncatedText class="truncate font-mono text-sm text-ink-gray-6" :text="row.run_id" />
      </template>

      <template #cell-status="{ row }">
        <RunStatusBadge :status="row.status" />
      </template>
    </DocListView>
  </div>

  <ExecutionLogDetail v-model:open="detail" :name="selected" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { call } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import ExecutionLogDetail from '@/components/Automation/ExecutionLogDetail.vue'
import RunStatusBadge from '@/components/Automation/RunStatusBadge.vue'
import { formatDuration } from '@/components/FlowBuilder/api'
import { useDocList } from '@/composables/useDocList'
import { formatDateTime, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({
  compact: { type: Boolean, default: false },
})

const STATUSES = ['Running', 'Waiting', 'Success', 'Failed', 'Partially Failed', 'Cancelled']

const route = useRoute()
const detail = ref(false)
const selected = ref(null)
const flowOptions = reactive([])

const list = useDocList({
  doctype: 'Automation Execution Log',
  fields: ['name', 'flow', 'run_id', 'status', 'start_time', 'end_time', 'duration'],
  searchFields: ['flow', 'run_id'],
  orderBy: 'start_time desc',
  initialFilters: { flow: route.query.flow || '', status: route.query.status || '' },
  quickFilters: [
    { key: 'flow', label: 'Flow', options: flowOptions },
    { key: 'status', label: 'Status', options: STATUSES.map((value) => ({ label: __(value), value })) },
  ],
  sortOptions: [
    { label: 'Newest first', value: 'start_time desc' },
    { label: 'Oldest first', value: 'start_time asc' },
    { label: 'Longest first', value: 'duration desc' },
  ],
})

const columns = [
  { key: 'flow', label: 'Flow' },
  { key: 'run_id', label: 'Run', width: '110px', hideOnMobile: true },
  { key: 'status', label: 'Status', width: '150px' },
  {
    key: 'start_time',
    label: 'Started',
    width: '170px',
    hideOnMobile: true,
    format: (value) => timeAgo(value),
  },
  {
    key: 'duration',
    label: 'Duration',
    width: '110px',
    align: 'right',
    hideOnMobile: true,
    format: (value) => formatDuration(value) || '—',
  },
]

watch(
  () => route.query.flow,
  (flow) => {
    if (flow) list.values.flow = flow
  },
)

function openLog(name) {
  selected.value = name
  detail.value = true
}

call('frappe.client.get_list', {
  doctype: 'OneChat Flow',
  fields: ['name', 'flow_name'],
  order_by: 'flow_name asc',
  limit_page_length: 500,
})
  .then((flows) => {
    flowOptions.splice(0, flowOptions.length, ...flows.map((flow) => ({ label: flow.flow_name || flow.name, value: flow.name })))
    if (route.query.flow && !flows.some((flow) => flow.name === route.query.flow)) {
      flowOptions.unshift({ label: route.query.flow, value: route.query.flow })
    }
  })
  .catch(() => {})
</script>

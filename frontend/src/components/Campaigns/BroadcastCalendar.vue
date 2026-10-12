<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <ErrorMessage :message="error" />
    <div class="relative min-h-[32rem] flex-1">
      <Calendar :events="events" :config="config" :on-click="pick" :on-cell-click="noop" @range-change="loadRange" />
      <div v-if="loading && !rows.length" class="absolute inset-0 grid place-content-center bg-surface-base/60">
        <Spinner class="size-5" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ErrorMessage, Spinner, call, dayjs } from 'frappe-ui'
import { Calendar } from 'frappe-ui/experimental'
import { errorMessage } from '@/utils/format'

const props = defineProps({
  statusOf: { type: Function, required: true },
})

const emit = defineEmits(['open'])

const LENGTH_MINUTES = 30
const COLORS = {
  Scheduled: 'blue',
  Queued: 'cyan',
  'In Progress': 'cyan',
  Completed: 'green',
  'Partially Failed': 'orange',
  Failed: 'pink',
}

const config = {
  defaultMode: 'Month',
  isEditMode: false,
  enableShortcuts: false,
  scrollToHour: 9,
}

const rows = ref([])
const loading = ref(false)
const error = ref('')
let range = null

const events = computed(() =>
  rows.value.map((row) => {
    const status = props.statusOf(row)
    const at = dayjs(row.scheduled_time || row.creation)
    const end = at.add(LENGTH_MINUTES, 'minute')
    return {
      id: row.name,
      name: row.name,
      title: row.title || row.name,
      fromDate: at.format('YYYY-MM-DD'),
      toDate: at.format('YYYY-MM-DD'),
      fromTime: at.format('HH:mm'),
      toTime: end.isSame(at, 'day') ? end.format('HH:mm') : '23:59',
      color: COLORS[status] || 'violet',
      isDraft: status === 'Draft',
      isDeclined: status === 'Cancelled',
    }
  }),
)

function noop() {}

function pick({ calendarEvent }) {
  emit('open', { name: calendarEvent.name })
}

function bounds(payload) {
  return {
    from: dayjs(payload?.startDate || dayjs().startOf('month').subtract(7, 'day')).format('YYYY-MM-DD 00:00:00'),
    to: dayjs(payload?.endDate || dayjs().endOf('month').add(7, 'day')).format('YYYY-MM-DD 23:59:59'),
  }
}

async function loadRange(payload) {
  range = bounds(payload)
  await refresh()
}

async function refresh() {
  if (!range) range = bounds()
  loading.value = true
  error.value = ''
  try {
    rows.value = await call('frappe.client.get_list', {
      doctype: 'Bulk WhatsApp Message',
      fields: ['name', 'title', 'template', 'status', 'scheduled_time', 'docstatus', 'creation'],
      or_filters: [
        ['scheduled_time', 'between', [range.from, range.to]],
        ['creation', 'between', [range.from, range.to]],
      ],
      order_by: 'creation asc',
      limit_page_length: 500,
    })
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

defineExpose({ refresh })
</script>

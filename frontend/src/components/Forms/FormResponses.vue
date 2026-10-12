<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-outline-gray-1 px-5 py-3">
      <div class="shrink-0">
        <p class="text-base font-medium text-ink-gray-8">{{ __('Responses') }}</p>
        <p class="text-sm text-ink-gray-5">
          {{ subtitle }}
        </p>
      </div>
      <div class="flex flex-wrap items-center justify-end gap-2">
        <template v-if="name && overall">
          <FormControl v-model="filters.search" class="w-full sm:w-56" type="text" :placeholder="__('Search name, number or answer')">
            <template #prefix>
              <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
            </template>
          </FormControl>
          <FormControl v-model="filters.from_date" class="w-[calc(50%-0.25rem)] sm:w-36" type="date" :placeholder="__('From date')" />
          <FormControl v-model="filters.to_date" class="w-[calc(50%-0.25rem)] sm:w-36" type="date" :placeholder="__('To date')" />
          <Button v-if="narrowed" variant="ghost" icon="lucide-x" :label="__('Clear filters')" @click="clearFilters" />
        </template>
        <Button variant="ghost" icon-left="lucide-download" :disabled="!overall" :label="__('Export')" @click="exportOpen = true" />
        <Button variant="subtle" icon-left="lucide-refresh-cw" :loading="loading" :label="__('Refresh')" @click="load" />
      </div>
    </div>

    <ExportDialog
      v-model:open="exportOpen"
      :default-name="`${name}-responses-${today}`"
      :filtered="narrowed"
      :filtered-count="total"
      :total-count="overall"
      :limit="EXPORT_LIMIT"
      :build="buildExport"
    />

    <div v-if="!name" class="p-5">
      <EmptyState
        icon="lucide-inbox"
        :title="__('Save the form first')"
        :description="__('Responses show up here once the form is live.')"
      />
    </div>

    <div v-else-if="loading && !rows.length" class="p-5">
      <ListSkeleton :avatar="false" />
    </div>

    <div v-else-if="error" class="p-5">
      <ErrorMessage :message="error" />
    </div>

    <div v-else-if="!rows.length && narrowed" class="p-5">
      <EmptyState
        icon="lucide-search-x"
        :title="__('No responses match these filters')"
        :description="__('Widen the dates or clear the search.')"
      />
    </div>

    <div v-else-if="!rows.length" class="p-5">
      <EmptyState
        icon="lucide-inbox"
        :title="__('No responses yet')"
        :description="__('When someone completes this form in WhatsApp, their answers appear here.')"
      />
    </div>

    <template v-else>
      <ScrollArea orientation="both" class="min-h-0 flex-1" viewport-class="px-5 pb-5" :class="{ 'opacity-60': loading }">
        <List :columns="columns" :style="{ minWidth: `${minWidth}px` }">
          <ListHeader class="sticky top-0 z-[1] bg-surface-base">
            <ListHeaderCell>{{ __('Contact') }}</ListHeaderCell>
            <ListHeaderCell>{{ __('Received') }}</ListHeaderCell>
            <ListHeaderCell v-for="key in keys" :key="key">
              <TruncatedText class="truncate" :text="labels[key] || key" :tip="labels[key] || key" />
            </ListHeaderCell>
          </ListHeader>
          <ListRows :items="rows" row-key="name" v-slot="{ item }">
            <ListRow class="items-start border-b border-outline-gray-1 py-2.5 last:border-b-0">
              <ListCell class="flex-col !items-start">
                <TruncatedText class="truncate text-base text-ink-gray-8" :text="item.contact_name || item.phone" />
                <TruncatedText v-if="item.contact_name" class="truncate text-sm tabular-nums text-ink-gray-5" :text="item.phone" />
              </ListCell>
              <ListCell>
                <span class="whitespace-nowrap text-base text-ink-gray-6" :title="formatDateTime(item.creation)">{{
                  timeAgo(item.creation)
                }}</span>
              </ListCell>
              <ListCell v-for="key in keys" :key="key">
                <TruncatedText
                  class="line-clamp-3 break-words text-base text-ink-gray-8"
                  :text="display(item.response[key])"
                  :tip="display(item.response[key])"
                />
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
      </ScrollArea>

      <div v-if="total > PAGE_SIZES[0]" class="px-5">
        <Pagination v-model:page="page" :total="total" inline class="pb-3" />
      </div>
    </template>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, ScrollArea, call, dayjs, debounce } from 'frappe-ui'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from 'frappe-ui/list'
import EmptyState from '@/components/Common/EmptyState.vue'
import ExportDialog from '@/components/Common/ExportDialog.vue'
import ListSkeleton from '@/components/Common/ListSkeleton.vue'
import Pagination from '@/components/Common/Pagination.vue'
import { useSocket } from '@/data/socket'
import { errorMessage, formatDateTime, formatNumber, timeAgo } from '@/utils/format'
import { PAGE_SIZES, pageLength } from '@/utils/paging'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
  screens: { type: Array, default: () => [] },
})

const rows = ref([])
const total = ref(0)
const overall = ref(0)
const page = ref(1)
const exportOpen = ref(false)
const filters = reactive({ search: '', from_date: '', to_date: '' })
const EXPORT_LIMIT = 10000
const today = dayjs().format('YYYY-MM-DD')

const narrowed = computed(() => Boolean(filters.search.trim() || filters.from_date || filters.to_date))

const subtitle = computed(() => {
  if (!overall.value) return __('Submissions from WhatsApp')
  if (narrowed.value) return __('{0} of {1} submissions match').format(formatNumber(total.value), formatNumber(overall.value))
  return __('{0} submissions from WhatsApp').format(formatNumber(overall.value))
})

function params() {
  return {
    from_date: filters.from_date || undefined,
    to_date: filters.to_date || undefined,
    search: filters.search.trim() || undefined,
  }
}

function clearFilters() {
  Object.assign(filters, { search: '', from_date: '', to_date: '' })
}
const loading = ref(false)
const error = ref('')

const labels = computed(() => {
  const out = {}
  for (const screen of props.screens) {
    for (const field of screen.fields) if (field.field_name) out[field.field_name] = field.label || field.field_name
  }

  return out
})

function keysOf(list) {
  const ordered = Object.keys(labels.value)
  const seen = new Set()
  for (const row of list) Object.keys(row.response || {}).forEach((key) => seen.add(key))

  return [...ordered.filter((key) => seen.has(key)), ...[...seen].filter((key) => !ordered.includes(key))]
}

const keys = computed(() => keysOf(rows.value))

const CONTACT_WIDTH = 190
const RECEIVED_WIDTH = 130
const FIELD_WIDTH = 220

const columns = computed(() => [`${CONTACT_WIDTH}px`, `${RECEIVED_WIDTH}px`, ...keys.value.map(() => `minmax(${FIELD_WIDTH}px,1fr)`)])
const minWidth = computed(() => CONTACT_WIDTH + RECEIVED_WIDTH + keys.value.length * FIELD_WIDTH)

function display(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'boolean') return value ? __('Yes') : __('No')
  if (typeof value === 'object') return JSON.stringify(value)

  return String(value)
}

async function load() {
  if (!props.name) return

  loading.value = true
  error.value = ''
  try {
    const data = await call('onechat.campaigns.forms.responses', {
      name: props.name,
      start: (page.value - 1) * pageLength.value,
      limit: pageLength.value,
      ...params(),
    })
    rows.value = data?.rows || []
    total.value = data?.total || 0
    overall.value = data?.overall ?? total.value
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function buildExport(scope) {
  const all =
    (await call('onechat.campaigns.forms.export_responses', { name: props.name, ...(scope === 'filtered' ? params() : {}) })) || []
  const fields = keysOf(all)
  const columns = [
    { key: '__contact', label: __('Contact') },
    { key: '__phone', label: __('Phone') },
    { key: '__received', label: __('Received') },
    ...fields.map((key) => ({ key: `r:${key}`, label: labels.value[key] || key })),
  ]
  const body = all.map((row) => ({
    __contact: row.contact_name || '',
    __phone: row.phone || '',
    __received: formatDateTime(row.creation),
    ...Object.fromEntries(fields.map((key) => [`r:${key}`, display(row.response[key])])),
  }))
  return { columns, rows: body }
}

function reload() {
  page.value === 1 ? load() : (page.value = 1)
}

const reloadSoon = debounce(reload, 300)

let socket = null

function onResponse() {
  load()
}

watch(page, load)
watch(() => [props.name, pageLength.value, filters.from_date, filters.to_date], reload)
watch(() => filters.search, reloadSoon)

onMounted(() => {
  load()
  socket = useSocket()
  socket.on('whatsapp_flow_response', onResponse)
})

onBeforeUnmount(() => {
  socket?.off('whatsapp_flow_response', onResponse)
})
</script>

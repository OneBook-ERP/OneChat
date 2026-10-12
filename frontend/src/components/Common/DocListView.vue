<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <MobileListToolbar v-if="!isDesktop" :list="list" :placeholder="searchPlaceholder" :menu="moreMenu">
      <slot name="toolbar" />
    </MobileListToolbar>

    <ScrollArea v-else orientation="horizontal" class="shrink-0" viewport-class="pb-1">
      <div class="flex w-max min-w-full items-center gap-2">
        <FormControl v-model="list.search.value" class="w-60 shrink-0" type="search" :placeholder="searchPlaceholder || __('Search')">
          <template #prefix>
            <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
          </template>
        </FormControl>

        <Select
          v-for="filter in list.quickFilters"
          :key="filter.key"
          v-model="list.values[filter.key]"
          class="w-40 shrink-0"
          :placeholder="__(filter.label)"
          :options="[{ label: __('All {0}').format(__(filter.label).toLowerCase()), value: '' }, ...filter.options]"
        />

        <Button v-if="filtered" class="shrink-0" variant="ghost" icon-left="lucide-x" :label="__('Clear')" @click="clearFilters" />

        <div class="flex flex-1 items-center justify-end gap-2 pl-2">
          <slot name="toolbar" />

          <Dropdown v-if="list.sortOptions.length" :options="sortMenu" align="end">
            <Button variant="ghost" icon="lucide-arrow-up-down" :label="__('Sort')" />
          </Dropdown>

          <Dropdown :options="moreMenu" align="end">
            <Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" />
          </Dropdown>
        </div>
      </div>
    </ScrollArea>

    <ListSkeleton v-if="list.loading.value && !list.rows.value.length" :avatar="false" />

    <EmptyState
      v-else-if="!list.rows.value.length"
      :icon="emptyIcon"
      :title="filtered ? __('Nothing matches') : emptyTitle"
      :description="filtered ? __('Try a different search or clear the filters.') : emptyDescription"
    >
      <Button v-if="filtered" variant="subtle" :label="__('Clear filters')" @click="clearFilters" />
    </EmptyState>

    <div
      v-else-if="!isDesktop"
      class="flex flex-col divide-y divide-outline-gray-1 rounded-5 border border-outline-gray-1"
      :class="{ 'mb-16': list.total.value <= PAGE_SIZES[0] }"
    >
      <div
        v-for="row in list.rows.value"
        :key="row.name"
        role="button"
        tabindex="0"
        class="flex min-h-14 cursor-pointer items-center gap-3 px-3 py-2 transition-colors first:rounded-t-5 last:rounded-b-5 active:bg-surface-gray-2"
        @click="emit('open', row)"
        @keydown.enter.self="emit('open', row)"
      >
        <div class="flex min-w-0 flex-1 flex-col gap-1">
          <div class="flex min-w-0 items-center">
            <slot :name="`cell-${titleColumn.key}`" :row="row" :value="row[titleColumn.key]">
              <TruncatedText class="truncate text-base text-ink-gray-9" :text="display(titleColumn, row)" />
            </slot>
          </div>
          <div v-if="subtitleColumns.length" class="flex min-w-0 items-center gap-1.5 overflow-hidden">
            <template v-for="(column, index) in subtitleColumns" :key="column.key">
              <span v-if="index" class="text-sm text-ink-gray-4" aria-hidden="true">·</span>
              <div class="flex min-w-0 items-center">
                <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                  <TruncatedText class="truncate text-sm text-ink-gray-5" :text="display(column, row)" />
                </slot>
              </div>
            </template>
          </div>
        </div>
        <div v-for="column in trailingColumns" :key="column.key" class="flex shrink-0 items-center">
          <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
            <span class="text-sm tabular-nums text-ink-gray-7">{{ display(column, row) }}</span>
          </slot>
        </div>
        <span class="lucide-chevron-right size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
      </div>
    </div>

    <ListScroll v-else class="min-h-0 flex-1">
      <ListView
        ref="view"
        class="!w-full"
        :columns="viewColumns"
        :rows="viewRows"
        row-key="name"
        :options="options"
        @update:selections="(selections) => (list.selection.value = [...selections])"
      >
        <ListHeader class="sticky top-0 z-10 shadow-[0_8px_0_0_var(--surface-base)]" @column-width-updated="resize" />
        <ListRows />
        <ListSelectBanner v-if="selectable">
          <template #actions="{ selections }">
            <div class="flex items-center gap-1">
              <Button
                v-for="action in bulkActions"
                :key="action.label"
                variant="ghost"
                :theme="action.theme || 'gray'"
                :icon-left="action.icon"
                :label="__(action.label)"
                @click="action.onClick([...selections])"
              />
              <Button
                v-if="deletable"
                variant="ghost"
                theme="red"
                icon-left="lucide-trash-2"
                :label="__('Delete')"
                @click="removeSelected([...selections])"
              />
            </div>
          </template>
        </ListSelectBanner>

        <template #cell="{ column, row, item }">
          <div class="flex w-full min-w-0 items-center [&>*]:min-w-0" :class="ALIGN[column.align] || 'justify-start'">
            <slot :name="`cell-${column.key}`" :row="source(row)" :value="source(row)[column.key]">
              <TruncatedText
                class="truncate text-base"
                :class="[
                  column.key === columns[0].key ? 'text-ink-gray-9' : 'text-ink-gray-7',
                  { 'tabular-nums': column.align === 'right' },
                ]"
                :text="column.format ? column.format(source(row)[column.key], source(row)) : source(row)[column.key]"
              />
            </slot>
          </div>
        </template>
      </ListView>
    </ListScroll>

    <Pagination v-if="list.total.value > PAGE_SIZES[0]" class="shrink-0" v-model:page="list.page.value" :total="list.total.value" />

    <ExportDialog
      v-model:open="exportOpen"
      :default-name="exportFileName"
      :filtered="list.filtered.value"
      :filtered-count="list.total.value"
      :total-count="allCount"
      :limit="EXPORT_LIMIT"
      :build="buildExport"
    />
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, ref, watch } from 'vue'
import { Button, Dropdown, FormControl, ScrollArea, Select, dayjs } from 'frappe-ui'
import { ListHeader, ListRows, ListSelectBanner, ListView } from 'frappe-ui/experimental'
import EmptyState from './EmptyState.vue'
import ExportDialog from './ExportDialog.vue'
import ListScroll from './ListScroll.vue'
import ListSkeleton from './ListSkeleton.vue'
import MobileListToolbar from './MobileListToolbar.vue'
import Pagination from './Pagination.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useUI } from '@/stores/ui'
import { EXPORT_LIMIT } from '@/composables/useDocList'
import { PAGE_SIZES } from '@/utils/paging'
import { translate as __ } from '@/translation'

const props = defineProps({
  list: { type: Object, required: true },
  columns: { type: Array, required: true },
  searchPlaceholder: { type: String, default: '' },
  emptyIcon: { type: String, default: 'lucide-inbox' },
  emptyTitle: { type: String, default: 'Nothing here yet' },
  emptyDescription: { type: String, default: '' },
  bulkActions: { type: Array, default: () => [] },
  deletable: { type: Boolean, default: true },
  exportName: { type: String, default: '' },
  importable: { type: Boolean, default: false },
})

const emit = defineEmits(['open'])

const ui = useUI()
const view = ref(null)
const { isDesktop } = useBreakpoint()

const ALIGN = { left: 'justify-start', center: 'justify-center', right: 'justify-end' }

const storageKey = `onechat:columns:${props.list.doctype}`
const widths = reactive(readWidths())

const selectable = computed(() => props.deletable || props.bulkActions.length > 0)

const options = computed(() => ({
  selectable: selectable.value,
  resizeColumn: isDesktop.value,
  showTooltip: false,
  rowHeight: 52,
  onRowClick: (row) => emit('open', source(row)),
}))

const viewRows = computed(() => props.list.rows.value.map((row) => (row.disabled ? { ...row, disabled: false, __source: row } : row)))

function source(row) {
  return row.__source || row
}

const viewColumns = computed(() =>
  props.columns
    .filter((column) => !column.exportOnly)
    .filter((column) => isDesktop.value || !column.hideOnMobile)
    .map((column) => ({
      ...column,
      label: __(column.label),
      width: widths[column.key] || trackWidth(column.width),
    })),
)

const titleColumn = computed(() => props.columns[0])

const mobileColumns = computed(() =>
  props.columns
    .slice(1)
    .filter((column) => !column.hideOnMobile && !column.exportOnly)
    .slice(0, 2),
)

const subtitleColumns = computed(() => mobileColumns.value.filter((column) => column.align !== 'right'))

const trailingColumns = computed(() => mobileColumns.value.filter((column) => column.align === 'right'))

const filtered = computed(
  () =>
    !!props.list.search.value || props.list.quickFilters.some((filter) => ![undefined, null, ''].includes(props.list.values[filter.key])),
)

const sortMenu = computed(() =>
  props.list.sortOptions.map((option) => ({
    label: __(option.label),
    icon: props.list.orderBy.value === option.value ? 'lucide-check' : 'lucide-dot',
    onClick: () => (props.list.orderBy.value = option.value),
  })),
)

const moreMenu = computed(() => [
  {
    label: __('Export'),
    icon: 'lucide-download',
    onClick: openExport,
  },
  {
    label: __('Import from a file'),
    icon: 'lucide-upload',
    condition: () => props.importable,
    onClick: () => window.open(`/app/data-import/new?reference_doctype=${encodeURIComponent(props.list.doctype)}`, '_blank'),
  },
  {
    label: __('Reset column widths'),
    icon: 'lucide-columns-3',
    condition: () => isDesktop.value && Object.keys(widths).length > 0,
    onClick: resetWidths,
  },
  {
    label: __('Refresh'),
    icon: 'lucide-refresh-cw',
    onClick: props.list.refresh,
  },
])

function display(column, row) {
  const value = row[column.key]
  const shown = column.format ? column.format(value, row) : value

  return [undefined, null, ''].includes(shown) ? '—' : shown
}

function trackWidth(width) {
  if (!width) return 1

  const fraction = String(width).match(/^minmax\(0,\s*([\d.]+)fr\)$/)
  return fraction ? Number(fraction[1]) : width
}

function readWidths() {
  try {
    return JSON.parse(localStorage.getItem(storageKey) || '{}')
  } catch {
    return {}
  }
}

function saveWidths() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(widths))
  } catch {
    return
  }
}

function resize({ key, width, save }) {
  widths[key] = width
  if (save) saveWidths()
}

function resetWidths() {
  for (const key of Object.keys(widths)) delete widths[key]
  saveWidths()
}

function clearFilters() {
  props.list.search.value = ''
  for (const filter of props.list.quickFilters) props.list.values[filter.key] = ''
}

const exportOpen = ref(false)
const allCount = ref(null)

const exportFileName = computed(() => {
  const base = (props.exportName || props.list.doctype)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  return `${base}-${dayjs().format('YYYY-MM-DD')}`
})

async function openExport() {
  allCount.value = props.list.filtered.value ? null : props.list.total.value
  exportOpen.value = true
  if (props.list.filtered.value) {
    try {
      allCount.value = await props.list.countAll()
    } catch {
      allCount.value = null
    }
  }
}

async function buildExport(scope) {
  const data = await props.list.exportRows(scope)
  const shown = props.columns.filter((column) => column.label)
  const columns = shown.map((column) => ({ key: column.key, label: __(column.label) }))
  const rows = (data || []).map((row) =>
    Object.fromEntries(shown.map((column) => [column.key, column.format ? column.format(row[column.key], row) : row[column.key]])),
  )
  return { columns, rows }
}

function removeSelected(names) {
  ui.confirm({
    title: __('Delete {0} records?').format(names.length),
    message: __('This cannot be undone.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await props.list.remove(names)
      view.value?.toggleAllRows(false)
    },
  })
}

watch(
  () => props.list.page.value,
  () => view.value?.toggleAllRows(false),
)
</script>

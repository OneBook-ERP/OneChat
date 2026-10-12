<template>
  <ChartCard>
    <ChartContainer :title="title" :subtitle="subtitle" :loading="loading" :empty="!rows.length">
      <template #empty>
        <p class="text-sm text-ink-gray-5">{{ emptyText || __('Nothing in this period') }}</p>
      </template>
      <ScrollArea orientation="horizontal" class="-mx-4" :class="{ 'min-h-32': loading || !rows.length }" viewport-class="px-4 pb-1">
        <List :columns="tracks" :row-height="40" :style="{ minWidth: `${minWidth}px` }">
          <ListHeader>
            <ListHeaderCell v-for="column in columns" :key="column.key" :class="column.numeric ? 'justify-end text-right' : ''">
              <span class="whitespace-nowrap">{{ column.label }}</span>
            </ListHeaderCell>
          </ListHeader>
          <ListRows :items="shown" :row-key="(row, index) => row[rowKey] ?? index" v-slot="{ item }">
            <ListRow>
              <ListCell
                v-for="column in columns"
                :key="column.key"
                :class="
                  column.numeric ? 'justify-end whitespace-nowrap text-right tabular-nums text-ink-gray-7' : 'min-w-0 text-ink-gray-8'
                "
              >
                <slot :name="column.key" :row="item" :value="item[column.key]">
                  <TruncatedText
                    class="truncate text-base"
                    :text="column.format ? column.format(item[column.key], item) : display(item[column.key])"
                  />
                </slot>
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
      </ScrollArea>
      <Pagination v-if="rows.length > PAGE_SIZES[0]" v-model:page="page" :total="rows.length" inline class="mt-2" />
    </ChartContainer>
  </ChartCard>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import { ScrollArea } from 'frappe-ui'
import { ChartCard, ChartContainer } from 'frappe-ui/charts'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from 'frappe-ui/list'
import Pagination from '@/components/Common/Pagination.vue'
import { formatNumber } from '@/utils/format'
import { PAGE_SIZES, pageLength, pageOf } from '@/utils/paging'
import { translate as __ } from '@/translation'

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  rowKey: { type: String, default: 'name' },
  loading: { type: Boolean, default: false },
  emptyText: { type: String, default: '' },
})

const page = ref(1)
const shown = computed(() => pageOf(props.rows, page.value))

watch(pageLength, () => (page.value = 1))

watch(
  () => props.rows,
  (rows) => {
    if ((page.value - 1) * pageLength.value >= rows.length) page.value = 1
  },
)

const FIRST_WIDTH = 180
const NUMBER_WIDTH = 110
const TEXT_WIDTH = 150

function widthOf(column, index) {
  if (index === 0) return FIRST_WIDTH
  return column.numeric ? NUMBER_WIDTH : TEXT_WIDTH
}

const tracks = computed(() => props.columns.map((column, index) => `minmax(${widthOf(column, index)}px,${index === 0 ? 2 : 1}fr)`))
const minWidth = computed(() => props.columns.reduce((sum, column, index) => sum + widthOf(column, index), 0))

function display(value) {
  if (value === null || value === undefined || value === '') return '—'
  return typeof value === 'number' ? formatNumber(value) : value
}
</script>

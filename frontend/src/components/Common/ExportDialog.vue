<template>
  <ResponsiveDialog v-model:open="open" :title="title || __('Export')" size="md">
    <template #default>
      <div class="flex flex-col gap-4">
        <div v-if="filtered" class="flex flex-col gap-2">
          <FormLabel :label="__('Records')" />
          <TabButtons
            v-model="scope"
            class="self-start"
            :options="[
              { label: __('Filtered'), value: 'filtered' },
              { label: __('All'), value: 'all' },
            ]"
          />
          <p class="text-sm text-ink-gray-5">{{ scopeHint }}</p>
        </div>
        <p v-else class="text-sm text-ink-gray-6">
          {{
            totalCount === null
              ? __('No filters are applied, so every record is exported.')
              : __('No filters are applied, so all {0} records are exported.').format(formatNumber(totalCount))
          }}
        </p>

        <FormControl v-model="fileName" :label="__('File name')" :placeholder="defaultName">
          <template #suffix>
            <span class="text-sm text-ink-gray-5">.csv</span>
          </template>
        </FormControl>

        <p v-if="limit && exportCount > limit" class="text-sm text-ink-amber-3">
          {{ __('Only the first {0} records are exported. Narrow the filters to export the rest.').format(formatNumber(limit)) }}
        </p>

        <ErrorMessage :message="error" />
      </div>
    </template>

    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="close" />
        <Button
          variant="solid"
          icon-left="lucide-download"
          :label="__('Export')"
          :loading="busy"
          :disabled="!fileName.trim()"
          @click="run(close)"
        />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, FormLabel, TabButtons } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { downloadCsv } from '@/utils/csv'
import { errorMessage, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  title: { type: String, default: '' },
  defaultName: { type: String, required: true },
  filtered: { type: Boolean, default: false },
  filteredCount: { type: Number, default: null },
  totalCount: { type: Number, default: null },
  limit: { type: Number, default: null },
  build: { type: Function, required: true },
})

const open = defineModel('open', { type: Boolean, default: false })

const scope = ref('filtered')
const fileName = ref('')
const busy = ref(false)
const error = ref('')

const exportCount = computed(() => (props.filtered && scope.value === 'filtered' ? props.filteredCount : props.totalCount) ?? 0)

const scopeHint = computed(() => {
  if (scope.value === 'filtered') {
    return props.filteredCount === null
      ? __('Only the records that match the current filters.')
      : __('Only the {0} records that match the current filters.').format(formatNumber(props.filteredCount))
  }
  return props.totalCount === null
    ? __('Every record, ignoring the current filters.')
    : __('All {0} records, ignoring the current filters.').format(formatNumber(props.totalCount))
})

watch(open, (value) => {
  if (!value) return
  scope.value = props.filtered ? 'filtered' : 'all'
  fileName.value = props.defaultName
  error.value = ''
})

async function run(close) {
  busy.value = true
  error.value = ''
  try {
    const { columns, rows } = await props.build(props.filtered ? scope.value : 'all')
    downloadCsv(fileName.value.trim().replace(/\.csv$/i, ''), columns, rows)
    close()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}
</script>

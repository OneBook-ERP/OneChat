<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <MobileListToolbar v-if="!isDesktop" :list="list" :placeholder="__('Search templates')">
      <slot name="toolbar" />
    </MobileListToolbar>

    <ScrollArea v-else orientation="horizontal" class="shrink-0" viewport-class="pb-1">
      <div class="flex w-max min-w-full items-center gap-2">
        <FormControl v-model="list.search.value" class="w-60 shrink-0" type="search" :placeholder="__('Search templates')">
          <template #prefix>
            <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
          </template>
        </FormControl>
        <Select
          v-for="filter in list.quickFilters"
          :key="filter.key"
          v-model="list.values[filter.key]"
          class="w-40 shrink-0"
          :options="[{ label: __('All {0}').format(__(filter.label).toLowerCase()), value: '' }, ...filter.options]"
        />
        <div class="flex flex-1 items-center justify-end gap-2 pl-2">
          <slot name="toolbar" />
        </div>
      </div>
    </ScrollArea>

    <div v-if="list.loading.value && !list.rows.value.length" class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Skeleton v-for="card in 6" :key="card" class="h-44 w-full rounded-5" />
    </div>

    <EmptyState
      v-else-if="!list.rows.value.length"
      icon="lucide-layout-template"
      :title="__('No templates found')"
      :description="__('Create a template or sync the ones already approved on Meta.')"
    />

    <component :is="isDesktop ? ScrollArea : 'div'" v-else class="min-h-0 flex-1">
      <div
        class="grid grid-cols-1 gap-3 pb-2 sm:grid-cols-2 lg:grid-cols-3"
        :class="{ 'mb-16': !isDesktop && list.total.value <= PAGE_SIZES[0] }"
      >
        <button
          v-for="row in list.rows.value"
          :key="row.name"
          type="button"
          class="flex min-w-0 flex-col gap-2 rounded-5 border border-outline-gray-1 bg-surface-base p-4 text-left transition-colors hover:border-outline-gray-3 hover:bg-surface-gray-1 active:bg-surface-gray-1 sm:p-3"
          @click="emit('open', row)"
        >
          <div class="flex w-full items-start justify-between gap-2">
            <div class="min-w-0">
              <TruncatedText as="p" class="truncate text-base font-medium text-ink-gray-9" :text="row.template_name" />
              <TruncatedText
                as="p"
                class="truncate text-sm text-ink-gray-5"
                :text="[categoryLabel(row.category), row.language_code].filter(Boolean).join(' · ')"
              />
            </div>
            <CampaignStatusBadge :status="row.status" size="sm" />
          </div>
          <p class="line-clamp-4 whitespace-pre-line text-sm text-ink-gray-7">
            <span v-if="row.header_type === 'TEXT' && row.header" class="font-semibold">{{ row.header }}<br /></span>
            <span v-else-if="row.header_type" class="text-ink-gray-5">[{{ __(row.header_type.toLowerCase()) }}]<br /></span>
            {{ fill(row.template, splitList(row.sample_values)) }}
          </p>
          <p class="mt-auto text-xs text-ink-gray-5">{{ __('Updated {0}').format(timeAgo(row.modified)) }}</p>
        </button>
      </div>
    </component>

    <Pagination v-if="list.total.value > PAGE_SIZES[0]" class="shrink-0" v-model:page="list.page.value" :total="list.total.value" />
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { FormControl, ScrollArea, Select, Skeleton } from 'frappe-ui'
import EmptyState from '@/components/Common/EmptyState.vue'
import MobileListToolbar from '@/components/Common/MobileListToolbar.vue'
import Pagination from '@/components/Common/Pagination.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { PAGE_SIZES } from '@/utils/paging'
import CampaignStatusBadge from './CampaignStatusBadge.vue'
import { fill, splitList } from './TemplatePreview.vue'
import { timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({
  list: { type: Object, required: true },
})

const emit = defineEmits(['open'])

const { isDesktop } = useBreakpoint()

function categoryLabel(value) {
  return value ? __(value.charAt(0) + value.slice(1).toLowerCase()) : ''
}
</script>

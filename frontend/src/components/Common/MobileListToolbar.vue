<template>
  <div class="flex items-center gap-2">
    <FormControl v-model="list.search.value" class="min-w-0 flex-1" size="lg" type="search" :placeholder="placeholder || __('Search')">
      <template #prefix>
        <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
      </template>
    </FormControl>

    <div class="relative shrink-0">
      <Button size="lg" variant="subtle" icon="lucide-sliders-horizontal" :label="__('Filters')" @click="open = true" />
      <Badge
        v-if="count"
        class="pointer-events-none absolute -right-1.5 -top-1.5 tabular-nums"
        variant="solid"
        theme="blue"
        size="sm"
        :label="String(count)"
      />
    </div>

    <Button v-if="count" class="shrink-0" size="lg" variant="ghost" icon="lucide-x" :label="__('Clear filters')" @click="clear" />

    <ResponsiveDialog v-model:open="open" :title="__('Filters')" size="sm">
      <template #default="{ close }">
        <FilterChips
          v-for="filter in list.quickFilters"
          :key="filter.key"
          :label="__(filter.label)"
          :options="[{ label: __('All'), value: '' }, ...filter.options]"
          :model-value="list.values[filter.key] ?? ''"
          @update:model-value="(value) => (list.values[filter.key] = value)"
        />

        <slot />

        <FilterChips
          v-if="list.sortOptions.length"
          v-model="list.orderBy.value"
          :label="__('Sort by')"
          :options="list.sortOptions.map((option) => ({ label: __(option.label), value: option.value }))"
        />

        <div v-if="items.length" class="-mx-4 flex flex-col border-t border-outline-gray-1 pt-2">
          <button
            v-for="item in items"
            :key="item.label"
            type="button"
            class="flex h-11 items-center gap-3 px-4 text-left text-base text-ink-gray-8 transition-colors active:bg-surface-gray-2"
            @click="run(item, close)"
          >
            <span :class="item.icon" class="size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
            <TruncatedText class="truncate" :text="item.label" />
          </button>
        </div>
      </template>

      <template #actions="{ close }">
        <div class="flex gap-2">
          <Button v-if="count" class="flex-1" size="lg" variant="subtle" :label="__('Clear filters')" @click="clear" />
          <Button class="flex-1" size="lg" variant="solid" :label="__('Done')" @click="close" />
        </div>
      </template>
    </ResponsiveDialog>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref } from 'vue'
import { Badge, Button, FormControl } from 'frappe-ui'
import FilterChips from './FilterChips.vue'
import ResponsiveDialog from './ResponsiveDialog.vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  list: { type: Object, required: true },
  placeholder: { type: String, default: '' },
  menu: { type: Array, default: () => [] },
  activeCount: { type: Number, default: 0 },
})

const emit = defineEmits(['clear'])

const open = ref(false)

const count = computed(
  () =>
    props.activeCount + props.list.quickFilters.filter((filter) => ![undefined, null, ''].includes(props.list.values[filter.key])).length,
)

const items = computed(() => props.menu.filter((item) => !item.condition || item.condition()))

function run(item, close) {
  close()
  item.onClick()
}

function clear() {
  for (const filter of props.list.quickFilters) props.list.values[filter.key] = ''
  emit('clear')
}
</script>

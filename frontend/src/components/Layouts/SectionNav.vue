<template>
  <template v-for="(group, index) in section.groups" :key="group.label || index">
    <div v-if="group.label" class="mt-4 flex h-7 items-center">
      <SidebarLabel>{{ __(group.label) }}</SidebarLabel>
    </div>

    <nav v-if="touch" class="flex flex-col gap-0.5" :class="{ 'mt-0.5': group.label }">
      <RouterLink
        v-for="item in group.items"
        :key="item.label"
        :to="item.to"
        class="flex h-11 items-center gap-3 rounded-5 px-3 transition-colors"
        :class="isActive(item.to) ? 'bg-surface-gray-2 text-ink-gray-9' : 'text-ink-gray-7 active:bg-surface-gray-2'"
        :aria-current="isActive(item.to) ? 'page' : undefined"
        @click="emit('navigate')"
      >
        <span v-if="item.dot" class="grid size-5 shrink-0 place-content-center" aria-hidden="true">
          <span class="size-2.5 rounded-full" :class="item.dot" />
        </span>
        <span v-else :class="item.icon" class="size-5 shrink-0" aria-hidden="true" />
        <TruncatedText class="min-w-0 flex-1 truncate text-base" :text="item.raw ? item.label : __(item.label)" />
        <span v-if="counts[item.label]" class="shrink-0 text-sm tabular-nums text-ink-gray-5">
          {{ countLabel(counts[item.label]) }}
        </span>
      </RouterLink>
    </nav>

    <nav v-else class="space-y-0.5" :class="{ 'mt-0.5': group.label }">
      <SidebarItem
        v-for="item in group.items"
        :key="item.label"
        :to="item.to"
        :active="isActive(item.to)"
        :icon="item.icon"
        :label="item.raw ? item.label : __(item.label)"
        @click="emit('navigate')"
      >
        <template v-if="item.dot" #prefix>
          <span class="grid size-4 place-content-center" aria-hidden="true">
            <span class="size-2 rounded-full" :class="item.dot" />
          </span>
        </template>
        <template v-if="counts[item.label]" #suffix>
          <span class="mr-1 min-w-4 text-right text-xs tabular-nums text-ink-gray-5">
            {{ countLabel(counts[item.label]) }}
          </span>
        </template>
      </SidebarItem>
    </nav>
  </template>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { SidebarItem, SidebarLabel } from 'frappe-ui'
import { useSection } from '@/composables/useSection'
import { countLabel } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({
  section: { type: Object, required: true },
  counts: { type: Object, default: () => ({}) },
  touch: { type: Boolean, default: false },
})

const emit = defineEmits(['navigate'])

const { isActive } = useSection()
</script>

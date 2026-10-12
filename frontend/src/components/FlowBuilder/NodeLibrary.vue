<template>
  <aside class="flex w-64 shrink-0 flex-col border-r border-outline-gray-2 bg-surface-base">
    <div class="border-b border-outline-gray-1 p-3">
      <FormControl v-model="search" type="search" :placeholder="__('Search steps')">
        <template #prefix>
          <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
        </template>
      </FormControl>
      <p class="mt-2 text-xs text-ink-gray-5">{{ __('Drag onto the canvas, or click to add after the selected step.') }}</p>
    </div>

    <ScrollArea class="min-h-0 flex-1" viewport-class="p-2">
      <p v-if="!groups.length" class="px-2 py-6 text-center text-sm text-ink-gray-5">{{ __('No steps match') }}</p>

      <section v-for="group in groups" :key="group.key" class="mb-1">
        <button
          type="button"
          class="flex w-full items-center gap-1.5 rounded-4 px-2 py-1.5 text-left text-sm font-medium text-ink-gray-6 hover:bg-surface-gray-2"
          @click="toggle(group.key)"
        >
          <span
            :class="closed.includes(group.key) && !search ? 'lucide-chevron-right' : 'lucide-chevron-down'"
            class="size-3.5"
            aria-hidden="true"
          />
          <span class="flex-1">{{ __(group.label) }}</span>
          <span class="text-xs text-ink-gray-4">{{ group.items.length }}</span>
        </button>

        <div v-show="!closed.includes(group.key) || search" class="mt-0.5 flex flex-col gap-0.5">
          <button
            v-for="item in group.items"
            :key="item.type"
            type="button"
            draggable="true"
            class="flex w-full cursor-grab items-center gap-2.5 rounded-4 px-2 py-1.5 text-left hover:bg-surface-gray-2 active:cursor-grabbing"
            @dragstart="(event) => onDragStart(event, item.type)"
            @click="emit('add', item.type)"
          >
            <span class="flex size-7 shrink-0 items-center justify-center rounded-4" :class="COLORS[item.color].chip">
              <span :class="item.icon" class="size-3.5" aria-hidden="true" />
            </span>
            <span class="min-w-0 flex-1">
              <TruncatedText class="block truncate text-sm text-ink-gray-8" :text="__(item.label)" />
              <TruncatedText class="block truncate text-xs text-ink-gray-5" :text="__(item.description)" />
            </span>
          </button>
        </div>
      </section>
    </ScrollArea>
  </aside>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref } from 'vue'
import { FormControl, ScrollArea } from 'frappe-ui'
import { CATEGORIES, COLORS, NODE_TYPES } from './nodeTypes'
import { translate as __ } from '@/translation'

const props = defineProps({ channel: { type: String, default: 'WhatsApp' } })

const emit = defineEmits(['add'])

const search = ref('')
const closed = ref(CATEGORIES.filter((category) => category.collapsed).map((category) => category.key))

const groups = computed(() => {
  const text = search.value.trim().toLowerCase()

  return CATEGORIES.map((category) => ({
    ...category,
    items: NODE_TYPES.filter(
      (item) => item.category === category.key && !item.hidden && !(props.channel === 'Instagram' && item.whatsappOnly),
    ).filter(
      (item) =>
        !text ||
        [item.label, item.description, item.type, __(item.label), __(item.description)].some((value) =>
          String(value).toLowerCase().includes(text),
        ),
    ),
  })).filter((group) => group.items.length)
})

function toggle(key) {
  closed.value = closed.value.includes(key) ? closed.value.filter((item) => item !== key) : [...closed.value, key]
}

function onDragStart(event, type) {
  event.dataTransfer.setData('application/onechat-node', type)
  event.dataTransfer.effectAllowed = 'move'
}
</script>

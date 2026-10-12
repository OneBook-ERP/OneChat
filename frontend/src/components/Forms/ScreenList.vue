<template>
  <aside class="flex w-64 shrink-0 flex-col border-r border-outline-gray-2 bg-surface-base">
    <div class="flex items-center justify-between border-b border-outline-gray-1 py-2 pl-3 pr-2">
      <p class="text-base font-medium text-ink-gray-8">{{ __('Screens') }}</p>
      <Button size="sm" variant="ghost" icon="lucide-plus" :label="__('Add screen')" @click="emit('add')" />
    </div>

    <ScrollArea class="min-h-0 flex-1" viewport-class="p-2">
      <ol class="flex flex-col gap-1">
        <li
          v-for="(screen, index) in screens"
          :key="screen.key"
          draggable="true"
          class="group flex cursor-pointer items-center gap-2 rounded-4 px-2 py-1.5"
          :class="[
            screen.key === selected ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2',
            overIndex === index && dragIndex !== index ? 'ring-1 ring-outline-gray-4' : '',
          ]"
          @click="emit('select', screen.key)"
          @dragstart="onDragStart($event, index)"
          @dragover.prevent="overIndex = index"
          @dragleave="overIndex = overIndex === index ? null : overIndex"
          @drop.prevent="onDrop(index)"
          @dragend="reset"
        >
          <span
            class="flex size-5 shrink-0 items-center justify-center rounded-full bg-surface-gray-2 text-xs tabular-nums text-ink-gray-6"
          >
            {{ index + 1 }}
          </span>
          <div class="min-w-0 flex-1">
            <TruncatedText as="p" class="truncate text-sm text-ink-gray-8" :text="screen.screen_title || __('Untitled screen')" />
            <TruncatedText
              as="p"
              class="truncate text-xs text-ink-gray-5"
              :text="__('{0} fields').format(screen.fields.filter((field) => field.enabled).length)"
            />
          </div>
          <Tooltip v-if="screen.terminal" :text="__('Final screen')">
            <span class="lucide-flag size-3.5 shrink-0 text-ink-green-6" aria-hidden="true" />
          </Tooltip>
          <span
            v-if="errorScreens.has(screen.key)"
            class="lucide-circle-alert size-3.5 shrink-0 text-ink-red-3"
            :aria-label="__('Has problems')"
          />
          <Dropdown :options="menu(screen, index)" align="end">
            <Button
              size="sm"
              variant="ghost"
              icon="lucide-ellipsis"
              class="opacity-0 group-hover:opacity-100"
              :label="__('Screen actions')"
              @click.stop
            />
          </Dropdown>
        </li>
      </ol>
    </ScrollArea>

    <p class="border-t border-outline-gray-1 px-3 py-2 text-xs text-ink-gray-5">
      {{ __('Screens show in this order. Drag to reorder.') }}
    </p>
  </aside>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref } from 'vue'
import { Button, Dropdown, ScrollArea, Tooltip } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  screens: { type: Array, required: true },
  selected: { type: String, default: null },
  issues: { type: Array, default: () => [] },
})

const emit = defineEmits(['select', 'add', 'move', 'terminal', 'duplicate', 'remove'])

const dragIndex = ref(null)
const overIndex = ref(null)

const errorScreens = computed(
  () => new Set(props.issues.filter((issue) => issue.level === 'error' && issue.screenKey).map((issue) => issue.screenKey)),
)

function menu(screen, index) {
  return [
    {
      label: __('Make final screen'),
      icon: 'lucide-flag',
      condition: () => !screen.terminal,
      onClick: () => emit('terminal', screen.key),
    },
    { label: __('Move up'), icon: 'lucide-arrow-up', condition: () => index > 0, onClick: () => emit('move', index, index - 1) },
    {
      label: __('Move down'),
      icon: 'lucide-arrow-down',
      condition: () => index < props.screens.length - 1,
      onClick: () => emit('move', index, index + 1),
    },
    { label: __('Duplicate'), icon: 'lucide-copy', onClick: () => emit('duplicate', screen.key) },
    {
      label: __('Delete'),
      icon: 'lucide-trash-2',
      condition: () => props.screens.length > 1,
      onClick: () => emit('remove', screen.key),
    },
  ]
}

function onDragStart(event, index) {
  dragIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(index))
}

function onDrop(index) {
  if (dragIndex.value !== null && dragIndex.value !== index) emit('move', dragIndex.value, index)
  reset()
}

function reset() {
  dragIndex.value = null
  overIndex.value = null
}
</script>

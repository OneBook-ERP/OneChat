<template>
  <Popover v-if="error" side="top" align="end">
    <template #trigger>
      <button
        type="button"
        class="-m-0.5 grid place-content-center rounded-full p-0.5 hover:bg-surface-red-2 focus-visible:ring-2 focus-visible:ring-outline-red-2"
        :aria-label="__('Why was this not delivered?')"
      >
        <span :class="[tick.icon, tick.class]" class="size-3.5" aria-hidden="true" />
      </button>
    </template>
    <template #default>
      <div class="flex w-72 max-w-[80vw] flex-col gap-1 p-3 text-left">
        <p class="flex items-center gap-1.5 text-sm font-medium text-ink-red-7">
          <span class="lucide-circle-alert size-4 shrink-0" aria-hidden="true" />
          {{ tick.label }}
        </p>
        <p class="whitespace-normal break-words text-sm leading-5 text-ink-gray-7">{{ error }}</p>
      </div>
    </template>
  </Popover>
  <Tooltip v-else :text="tick.label">
    <span :class="[tick.icon, tick.class]" class="size-3.5" :aria-label="tick.label" />
  </Tooltip>
</template>

<script setup>
import { Popover, Tooltip } from 'frappe-ui'
import { translate as __ } from '@/translation'

defineProps({
  tick: { type: Object, required: true },
  error: { type: String, default: '' },
})
</script>

<template>
  <HoverCard side="top" align="start" :offset="6" :hover-delay="0.1" :leave-delay="0.1">
    <template #trigger>
      <button
        type="button"
        class="inline-flex size-4 shrink-0 items-center justify-center rounded-full text-ink-gray-4 outline-none hover:text-ink-gray-7 focus-visible:text-ink-gray-7"
        :aria-label="title ? __('About {0}').format(title) : __('More information')"
      >
        <span class="lucide-info size-3.5" aria-hidden="true" />
      </button>
    </template>
    <div class="flex max-w-72 flex-col gap-1 p-3">
      <p v-if="title" class="text-sm font-medium text-ink-gray-8">{{ title }}</p>
      <p class="whitespace-pre-line text-sm leading-5 text-ink-gray-6">{{ text }}</p>
    </div>
  </HoverCard>
</template>

<script setup>
import { HoverCard } from 'frappe-ui'
import { translate as __ } from '@/translation'

defineProps({
  text: { type: String, required: true },
  title: { type: String, default: '' },
})
</script>

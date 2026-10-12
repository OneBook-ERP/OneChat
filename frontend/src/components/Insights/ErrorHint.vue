<template>
  <HoverCard :open="info ? undefined : false" :side="side" align="start" :offset="12" :hover-delay="0.15" :leave-delay="0.1">
    <template #trigger>
      <slot />
    </template>

    <div v-if="info" class="flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2.5 p-3">
      <div class="flex items-start justify-between gap-3">
        <p class="min-w-0 break-words text-sm font-medium leading-5 text-ink-gray-9">{{ title }}</p>
        <Badge v-if="info.code" size="sm" variant="subtle" theme="gray" class="shrink-0 tabular-nums">{{ info.code }}</Badge>
      </div>

      <slot name="stats" />

      <div v-if="info.meaning" class="flex flex-col gap-0.5">
        <p class="text-xs font-medium text-ink-gray-5">{{ __('What it means') }}</p>
        <p class="text-sm leading-5 text-ink-gray-7">{{ __(info.meaning) }}</p>
      </div>
      <div v-if="info.action" class="flex items-start gap-2 rounded-4 bg-surface-gray-2 px-2.5 py-2">
        <span class="lucide-lightbulb mt-0.5 size-3.5 shrink-0 text-ink-amber-6" aria-hidden="true" />
        <p class="text-sm leading-5 text-ink-gray-8">{{ __(info.action) }}</p>
      </div>
    </div>
  </HoverCard>
</template>

<script setup>
import { Badge, HoverCard } from 'frappe-ui'
import { translate as __ } from '@/translation'

defineProps({
  title: { type: String, default: '' },
  info: { type: Object, default: null },
  side: { type: String, default: 'left' },
})
</script>

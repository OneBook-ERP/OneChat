<template>
  <button
    type="button"
    class="group flex min-w-0 flex-col overflow-hidden rounded-5 border border-outline-gray-1 bg-surface-base text-left transition-colors hover:border-outline-gray-3 hover:bg-surface-gray-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
  >
    <div class="relative flex aspect-[4/3] w-full items-center justify-center overflow-hidden bg-surface-gray-2">
      <img v-if="item.media_type === 'image'" :src="item.file" :alt="item.title" loading="lazy" class="size-full object-cover" />
      <template v-else-if="item.media_type === 'video'">
        <video :src="`${item.file}#t=0.5`" preload="metadata" muted playsinline class="size-full object-cover" />
        <span class="absolute grid size-9 place-content-center rounded-full bg-surface-base shadow-sm">
          <span class="lucide-play size-4 text-ink-gray-8" aria-hidden="true" />
        </span>
      </template>
      <div v-else class="flex flex-col items-center gap-1.5">
        <span :class="MEDIA_ICONS[item.media_type] || MEDIA_ICONS.document" class="size-7 text-ink-gray-5" aria-hidden="true" />
        <span v-if="extension(item.file)" class="text-xs font-medium text-ink-gray-5">{{ extension(item.file) }}</span>
      </div>
    </div>

    <div class="flex min-w-0 flex-col gap-0.5 px-2.5 py-2">
      <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="item.title" />
      <TruncatedText
        as="p"
        class="truncate text-sm text-ink-gray-5"
        :text="[mediaTypeLabel(item.media_type), fileSize(item.file_size)].filter(Boolean).join(' · ')"
      />
    </div>
  </button>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { MEDIA_ICONS, extension, fileSize, mediaTypeLabel } from './media'

defineProps({
  item: { type: Object, required: true },
})
</script>

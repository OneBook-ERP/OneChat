<template>
  <div
    class="flex flex-col items-center gap-2 text-center"
    :class="compact ? 'px-3 py-6' : 'px-6 py-10'"
  >
    <span v-if="compact" :class="icon" class="size-5 text-ink-gray-4" aria-hidden="true" />
    <EmptyStateIllustration v-else :name="scene" :size="128" class="-mb-1" />
    <div>
      <p class="text-base font-medium text-ink-gray-8">{{ title }}</p>
      <p v-if="description" class="mt-1 max-w-sm text-sm text-ink-gray-5">{{ description }}</p>
    </div>
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EmptyStateIllustration from './EmptyStateIllustration.vue'
import { sceneFor } from '@/utils/illustrations'

const props = defineProps({
  icon: { type: String, default: 'lucide-inbox' },
  illustration: { type: String, default: '' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})

const scene = computed(() => props.illustration || sceneFor(props.icon))
</script>

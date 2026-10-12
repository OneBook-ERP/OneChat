<template>
  <div class="mb-1.5 flex min-w-0 items-center gap-1">
    <TruncatedText class="truncate text-sm text-ink-gray-6" :text="label" />
    <span v-if="required" class="text-sm text-ink-red-4" aria-hidden="true">*</span>
    <InfoHint v-if="description" :text="description" :title="label" />
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import InfoHint from './InfoHint.vue'

defineProps({
  label: { type: String, required: true },
  description: { type: String, default: '' },
  required: { type: Boolean, default: false },
})
</script>

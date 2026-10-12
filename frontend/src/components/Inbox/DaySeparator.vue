<template>
  <div class="sticky top-2 z-[1] flex justify-center py-2" role="separator" :aria-label="label">
    <span class="rounded-full bg-surface-elevation-2 px-3 py-1 text-xs font-medium text-ink-gray-6 shadow-sm">
      {{ label }}
    </span>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
})
</script>

<template>
  <section :id="id" class="scroll-mt-16" :aria-labelledby="`${id}-title`">
    <div class="mb-3">
      <h2 :id="`${id}-title`" class="text-lg font-semibold text-ink-gray-8">{{ title }}</h2>
      <p v-if="description" class="mt-0.5 text-sm text-ink-gray-5">{{ description }}</p>
    </div>
    <slot />
  </section>
</template>

<script setup>
defineProps({
  id: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<template>
  <span
    class="flex shrink-0 items-center justify-center overflow-hidden rounded-5"
    :class="[{ lg: 'size-14', md: 'size-12', sm: 'size-10' }[size], frame]"
  >
    <img
      v-if="logo && !broken"
      :src="logo"
      :alt="label"
      class="size-full object-contain"
      :class="{ 'p-2': !bare }"
      @error="broken = true"
    />
    <span
      v-else
      :class="[icon || 'lucide-blocks', { lg: 'size-7', md: 'size-6', sm: 'size-5' }[size]]"
      class="text-ink-gray-7"
      aria-hidden="true"
    />
  </span>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  logo: { type: String, default: '' },
  icon: { type: String, default: '' },
  label: { type: String, default: '' },
  size: { type: String, default: 'md' },
  bare: { type: Boolean, default: false },
})

const broken = ref(false)

const frame = computed(() => {
  if (!props.logo || broken.value) return 'bg-surface-gray-2'
  return props.bare ? '' : 'border border-outline-gray-1 bg-surface-base'
})

watch(
  () => props.logo,
  () => (broken.value = false),
)
</script>

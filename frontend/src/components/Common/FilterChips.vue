<template>
  <div class="flex flex-col gap-2">
    <p class="text-sm font-medium text-ink-gray-5">{{ label }}</p>
    <div class="flex flex-wrap gap-2">
      <Button
        v-for="option in options"
        :key="option.value"
        size="lg"
        :variant="isSelected(option.value) ? 'solid' : 'subtle'"
        :label="option.label"
        :aria-pressed="isSelected(option.value)"
        @click="value = option.value"
      />
    </div>
  </div>
</template>

<script setup>
import { Button } from 'frappe-ui'

defineProps({
  label: { type: String, default: '' },
  options: { type: Array, default: () => [] },
})

const value = defineModel({ type: [String, Number], default: '' })

function isSelected(option) {
  return String(value.value ?? '') === String(option ?? '')
}
</script>

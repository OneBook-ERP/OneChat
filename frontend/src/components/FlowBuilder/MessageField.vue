<template>
  <div class="flex flex-col gap-1.5">
    <PersonalizedText
      :model-value="modelValue"
      :label="label"
      :required="required"
      :rows="rows"
      :single-line="compact"
      :variables="variables"
      :placeholder="placeholder"
      @update:model-value="(value) => emit('update:modelValue', value)"
    />

    <div class="flex items-start justify-between gap-2">
      <p class="text-xs text-ink-gray-5">{{ description || (compact ? '' : hint) }}</p>
      <span v-if="limit && !compact" class="shrink-0 text-xs tabular-nums" :class="length > limit ? 'text-ink-red-4' : 'text-ink-gray-4'">
        {{ length }} / {{ limit }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import PersonalizedText from '@/components/Common/PersonalizedText.vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  description: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  required: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  rows: { type: Number, default: 4 },
  limit: { type: Number, default: 1024 },
})

const emit = defineEmits(['update:modelValue'])

const variables = inject('flowVariables', ref([]))

const length = computed(() => String(props.modelValue || '').length)
const hint = __('Use *bold* and _italic_. Add personal details from the menu.')
</script>

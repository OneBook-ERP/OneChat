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

    <div v-if="preview" class="rounded-4 bg-surface-gray-1 px-2 py-1.5">
      <p class="text-xs font-medium text-ink-gray-5">{{ __('Preview') }}</p>
      <p class="whitespace-pre-wrap break-words text-sm text-ink-gray-8">{{ preview }}</p>
    </div>

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
  extraVariables: { type: Array, default: () => [] },
  preview: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const flowVariables = inject('flowVariables', ref([]))
const variables = computed(() => [...props.extraVariables, ...flowVariables.value])

const length = computed(() => String(props.modelValue || '').length)
const hint = __('Use *bold* and _italic_. Add personal details from the menu.')
</script>

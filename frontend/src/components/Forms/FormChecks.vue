<template>
  <div class="flex flex-col gap-3">
    <div v-if="!issues.length" class="flex items-center gap-3 rounded-4 bg-surface-green-2 p-3">
      <span class="lucide-circle-check size-4 text-ink-green-6" aria-hidden="true" />
      <p class="text-base text-ink-gray-8">{{ __('Everything looks good.') }}</p>
    </div>

    <p v-else class="text-sm text-ink-gray-6">
      {{ summary }}
    </p>

    <ul v-if="issues.length" class="flex flex-col divide-y divide-outline-gray-1">
      <li v-for="(issue, index) in issues" :key="index">
        <button
          type="button"
          class="flex w-full items-start gap-2 rounded-4 px-1 py-2 text-left hover:bg-surface-gray-2"
          :disabled="!issue.screenKey"
          @click="emit('select', issue)"
        >
          <span
            :class="issue.level === 'error' ? 'lucide-circle-x text-ink-red-3' : 'lucide-triangle-alert text-ink-amber-6'"
            class="mt-0.5 size-4 shrink-0"
            aria-hidden="true"
          />
          <span class="min-w-0 flex-1 text-sm text-ink-gray-8">{{ issue.message }}</span>
        </button>
      </li>
    </ul>

    <div v-if="metaErrors.length" class="flex flex-col gap-2 rounded-4 border border-outline-gray-2 p-3">
      <p class="text-sm font-medium text-ink-gray-8">{{ __('Reported by Meta') }}</p>
      <ul class="flex flex-col gap-1.5">
        <li v-for="(error, index) in metaErrors" :key="index" class="flex items-start gap-2 text-sm text-ink-gray-7">
          <span class="lucide-circle-x mt-0.5 size-4 shrink-0 text-ink-red-3" aria-hidden="true" />
          <span class="min-w-0 break-words">
            {{ error.message || error.error }}
            <span v-if="error.error_type" class="text-ink-gray-5">({{ error.error_type }})</span>
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  issues: { type: Array, default: () => [] },
  metaErrors: { type: Array, default: () => [] },
})

const emit = defineEmits(['select'])

const summary = computed(() => {
  const errors = props.issues.filter((issue) => issue.level === 'error').length
  const warnings = props.issues.length - errors

  return __('{0} to fix, {1} to review before publishing.').format(errors, warnings)
})
</script>

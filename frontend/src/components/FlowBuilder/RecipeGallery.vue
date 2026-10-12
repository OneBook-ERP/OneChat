<template>
  <ResponsiveDialog v-model:open="open" :title="__('New flow')" size="3xl">
    <template #default>
      <p class="mb-4 text-base text-ink-gray-6">
        {{ __('Start from a ready-made flow and change it to fit, or build your own from scratch.') }}
      </p>
      <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        <button
          type="button"
          class="flex items-start gap-3 rounded-5 border border-dashed border-outline-gray-3 p-3.5 text-left transition-colors hover:bg-surface-gray-1"
          @click="pick(null)"
        >
          <span class="flex size-9 shrink-0 items-center justify-center rounded-4 bg-surface-gray-2 text-ink-gray-7">
            <span class="lucide-plus size-4" aria-hidden="true" />
          </span>
          <span class="min-w-0">
            <span class="block text-base font-medium text-ink-gray-8">{{ __('Start from scratch') }}</span>
            <span class="mt-0.5 block text-sm text-ink-gray-5">{{ __('An empty canvas with your own trigger and steps.') }}</span>
          </span>
        </button>

        <button
          v-for="recipe in RECIPES"
          :key="recipe.key"
          type="button"
          class="flex items-start gap-3 rounded-5 border border-outline-gray-2 p-3.5 text-left transition-colors hover:border-outline-gray-3 hover:bg-surface-gray-1"
          @click="pick(recipe)"
        >
          <span class="flex size-9 shrink-0 items-center justify-center rounded-4 bg-surface-green-2 text-ink-green-7">
            <span :class="recipe.icon" class="size-4" aria-hidden="true" />
          </span>
          <span class="min-w-0">
            <span class="flex items-center gap-2">
              <span class="text-base font-medium text-ink-gray-8">{{ __(recipe.title) }}</span>
              <Badge v-if="recipe.needs" size="sm" variant="outline" :label="recipe.needs" />
            </span>
            <span class="mt-0.5 block text-sm text-ink-gray-5">{{ __(recipe.description) }}</span>
          </span>
        </button>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { Badge } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { RECIPES } from './recipes'
import { translate as __ } from '@/translation'

const emit = defineEmits(['pick'])

const open = defineModel('open', { type: Boolean, default: false })

function pick(recipe) {
  open.value = false
  emit('pick', recipe)
}
</script>

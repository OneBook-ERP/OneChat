<template>
  <ResponsiveDialog v-model:open="open" :title="__('Flow check')" size="lg">
    <template #default>
      <div v-if="!issues.length" class="flex items-center gap-3 rounded-4 bg-surface-green-1 p-3">
        <span class="lucide-circle-check size-4 text-ink-green-6" aria-hidden="true" />
        <p class="text-base text-ink-gray-8">{{ __('Everything looks good.') }}</p>
      </div>

      <ul v-else class="flex flex-col divide-y divide-outline-gray-1">
        <li v-for="(issue, index) in issues" :key="index" class="flex items-start gap-3 py-2.5">
          <span
            :class="issue.level === 'error' ? 'lucide-circle-x text-ink-red-6' : 'lucide-triangle-alert text-ink-amber-6'"
            class="mt-0.5 size-4 shrink-0"
            aria-hidden="true"
          />
          <p class="min-w-0 flex-1 text-base text-ink-gray-8">{{ issue.message }}</p>
          <Button v-if="issue.nodeId" size="sm" variant="ghost" :label="__('Show')" @click="show(issue.nodeId)" />
        </li>
      </ul>
    </template>

    <template #actions>
      <div class="flex w-full justify-end">
        <Button variant="solid" :label="__('Done')" @click="open = false" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { Button } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { translate as __ } from '@/translation'

defineProps({
  issues: { type: Array, default: () => [] },
})

const emit = defineEmits(['select'])

const open = defineModel('open', { type: Boolean, default: false })

function show(id) {
  open.value = false
  emit('select', id)
}
</script>

<template>
  <ResponsiveDialog v-if="sheet" v-model:open="open" :title="__('Labels')" size="sm">
    <template #default>
      <LabelChecklist :contact="contact" :model-value="modelValue" large class="-mx-2" />
    </template>
  </ResponsiveDialog>

  <Popover v-else v-model:open="open" align="end">
    <template #trigger>
      <Button variant="ghost" icon="lucide-tag" :label="__('Labels')" :tooltip="__('Labels')" :class="{ 'bg-surface-gray-3': open }" />
    </template>
    <template #default>
      <LabelChecklist :contact="contact" :model-value="modelValue" class="w-60 p-1.5" />
    </template>
  </Popover>
</template>

<script setup>
import { Button, Popover } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import LabelChecklist from './LabelChecklist.vue'
import { translate as __ } from '@/translation'

defineProps({
  contact: { type: String, required: true },
  modelValue: { type: Array, default: () => [] },
  sheet: { type: Boolean, default: false },
})

const open = defineModel('open', { type: Boolean, default: false })
</script>

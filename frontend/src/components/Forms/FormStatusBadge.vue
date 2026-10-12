<template>
  <Badge v-if="status" :theme="STATUS_THEMES[status] || 'gray'" :size="size" :label="__(status)" />
  <span v-else class="text-base text-ink-gray-4">—</span>
</template>

<script setup>
import { Badge } from 'frappe-ui'
import { STATUS_THEMES } from './formSchema'
import { translate as __ } from '@/translation'

defineProps({
  status: { type: String, default: '' },
  size: { type: String, default: 'md' },
})
</script>

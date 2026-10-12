<template>
  <Badge v-if="status" :theme="theme" :size="size" :label="label" />
  <span v-else class="text-base text-ink-gray-4">—</span>
</template>

<script setup>
import { computed } from 'vue'
import { Badge } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  status: { type: String, default: '' },
  size: { type: String, default: 'md' },
})

const THEMES = {
  approved: 'green',
  completed: 'green',
  delivered: 'green',
  read: 'green',
  success: 'green',
  pending: 'amber',
  in_appeal: 'amber',
  pending_deletion: 'amber',
  queued: 'blue',
  'in progress': 'blue',
  sent: 'blue',
  scheduled: 'violet',
  rejected: 'red',
  failed: 'red',
  'partially failed': 'red',
}

const key = computed(() => String(props.status || '').toLowerCase())

const theme = computed(() => THEMES[key.value] || 'gray')

const label = computed(() => {
  const text = key.value.replace(/_/g, ' ')

  return __(text.charAt(0).toUpperCase() + text.slice(1))
})
</script>

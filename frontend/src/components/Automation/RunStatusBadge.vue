<template>
  <Badge :label="__(status || 'Unknown')" :theme="THEMES[status] || 'gray'" variant="subtle">
    <template #prefix>
      <span :class="ICONS[status] || 'lucide-circle-dashed'" class="size-3" aria-hidden="true" />
    </template>
  </Badge>
</template>

<script setup>
import { Badge } from 'frappe-ui'
import { translate as __ } from '@/translation'

defineProps({
  status: { type: String, default: '' },
})

const THEMES = {
  Running: 'blue',
  Waiting: 'violet',
  Started: 'blue',
  Success: 'green',
  Failed: 'red',
  'Partially Failed': 'amber',
  Cancelled: 'gray',
  Skipped: 'gray',
}

const ICONS = {
  Running: 'lucide-loader',
  Waiting: 'lucide-hourglass',
  Started: 'lucide-loader',
  Success: 'lucide-circle-check',
  Failed: 'lucide-circle-x',
  'Partially Failed': 'lucide-circle-alert',
  Cancelled: 'lucide-circle-slash',
  Skipped: 'lucide-circle-dashed',
}
</script>

<template>
  <div class="flex flex-col gap-1">
    <div v-for="row in rows" :key="row" class="flex items-center gap-3 px-1 py-2.5">
      <Skeleton v-if="avatar" class="size-8 rounded-1" />

      <div class="min-w-0 flex-1 space-y-2">
        <Skeleton class="h-4 rounded-full" :class="row % 2 ? 'w-1/3' : 'w-2/5'" />
        <Skeleton class="h-3 rounded-full" :class="row % 2 ? 'w-3/5' : 'w-1/2'" />
      </div>

      <Skeleton class="h-5 w-16 shrink-0 rounded-full" />
    </div>
  </div>
</template>

<script setup>
import { Skeleton } from 'frappe-ui'

defineProps({
  rows: { type: Number, default: 5 },
  avatar: { type: Boolean, default: true },
})
</script>

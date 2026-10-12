<template>
  <ScrollArea orientation="both" class="list-scroll w-full" viewport-class="[&>div]:!min-w-full">
    <slot />
  </ScrollArea>
</template>

<script setup>
import { ScrollArea } from 'frappe-ui'
</script>

<style scoped>
.list-scroll :deep(.overflow-x-auto),
.list-scroll :deep(.overflow-y-auto),
.list-scroll :deep(.overflow-y-hidden) {
  overflow: visible;
}

.list-scroll :deep(.absolute.bottom-6) {
  position: fixed;
  z-index: 20;
}
</style>

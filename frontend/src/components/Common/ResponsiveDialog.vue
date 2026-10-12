<template>
  <Dialog v-if="isDesktop" v-model:open="open" :title="title" :size="size">
    <template v-if="$slots.title" #title>
      <slot name="title" :close="close" />
    </template>
    <template #default>
      <slot :close="close" />
    </template>
    <template v-if="$slots.actions" #actions>
      <slot name="actions" :close="close" />
    </template>
  </Dialog>

  <BottomSheet v-else v-model:open="open" :title="title">
    <div class="flex flex-col gap-4 px-4">
      <slot :close="close" />
    </div>
    <div
      v-if="$slots.actions"
      class="sticky bottom-0 mt-4 border-t border-outline-gray-1 bg-surface-base px-4 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-3"
    >
      <slot name="actions" :close="close" />
    </div>
    <div v-else class="h-[calc(1rem+env(safe-area-inset-bottom))]" />
  </BottomSheet>
</template>

<script setup>
import { BottomSheet, Dialog } from 'frappe-ui'
import { useBreakpoint } from '@/composables/useBreakpoint'

defineProps({
  title: { type: String, default: '' },
  size: { type: String, default: 'lg' },
})

const open = defineModel('open', { type: Boolean, default: false })

const { isDesktop } = useBreakpoint()

function close() {
  open.value = false
}
</script>

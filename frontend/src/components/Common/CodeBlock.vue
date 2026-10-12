<template>
  <div class="overflow-hidden rounded-4 border border-outline-gray-1 bg-surface-gray-1">
    <div class="flex items-center justify-between gap-2 border-b border-outline-gray-1 py-1 pl-3 pr-1">
      <TruncatedText class="truncate text-xs font-medium text-ink-gray-5" :text="title" />
      <div class="flex shrink-0 items-center">
        <Tooltip :text="wrap ? __('Show long lines on one line') : __('Wrap long lines')">
          <Button
            size="sm"
            variant="ghost"
            :icon="wrap ? 'lucide-wrap-text' : 'lucide-move-horizontal'"
            :label="wrap ? __('Unwrap lines') : __('Wrap lines')"
            @click="wrap = !wrap"
          />
        </Tooltip>
        <Tooltip :text="__('Copy')">
          <Button size="sm" variant="ghost" icon="lucide-copy" :label="__('Copy')" @click="copy" />
        </Tooltip>
      </div>
    </div>
    <ScrollArea :orientation="wrap ? 'vertical' : 'both'" :viewport-class="maxHeight">
      <pre
        class="p-3 font-mono text-xs leading-5 text-ink-gray-8"
        :class="wrap ? 'whitespace-pre-wrap break-words [overflow-wrap:anywhere]' : 'whitespace-pre'"
        >{{ code }}</pre
      >
    </ScrollArea>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { ref } from 'vue'
import { Button, ScrollArea, Tooltip, toast } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  code: { type: String, default: '' },
  title: { type: String, default: '' },
  maxHeight: { type: String, default: 'max-h-64' },
})

const wrap = ref(true)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.code || '')
    toast.success(__('Copied'))
  } catch {
    toast.error(__('Could not copy. Select the text and copy it yourself.'))
  }
}
</script>

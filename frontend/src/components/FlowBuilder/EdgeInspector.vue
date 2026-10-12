<template>
  <div class="flex h-full flex-col">
    <div class="flex items-start gap-2.5 border-b border-outline-gray-1 p-3">
      <span class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-4 bg-surface-gray-3 text-ink-gray-7">
        <span class="lucide-arrow-down-right size-4" aria-hidden="true" />
      </span>
      <div class="min-w-0 flex-1">
        <p class="text-base font-medium text-ink-gray-8">{{ __('Connection') }}</p>
        <p class="truncate text-xs text-ink-gray-5">{{ from }} → {{ to }}</p>
      </div>
      <Button variant="ghost" icon="lucide-x" :label="__('Close')" @click="emit('close')" />
    </div>

    <ScrollArea class="min-h-0 flex-1" viewport-class="p-3">
      <div class="flex flex-col gap-4">
        <FormControl
          type="text"
          :label="__('Label')"
          :model-value="edge.label || ''"
          :placeholder="__('Shown on the canvas')"
          @update:model-value="(value) => emit('change', { label: value })"
        />

        <p v-if="edge.sourceHandle" class="rounded-4 bg-surface-gray-2 p-2.5 text-sm text-ink-gray-7">
          {{ __('This path is taken when the step ends with {0}.').format(pathLabel) }}
        </p>

        <div v-else-if="showCondition" class="flex flex-col gap-1.5">
          <FormControl
            type="textarea"
            class="font-mono"
            :rows="3"
            :label="__('Only follow when')"
            :model-value="edge.data?.condition || ''"
            placeholder="context['vars']['total'] > 5000"
            @update:model-value="(value) => emit('change', { condition: value })"
          />
          <p class="text-xs leading-5 text-ink-gray-5">{{ help }}</p>
        </div>
      </div>
    </ScrollArea>

    <div class="flex justify-end border-t border-outline-gray-1 p-3">
      <Button variant="subtle" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="emit('delete')" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, FormControl, ScrollArea } from 'frappe-ui'
import { edgeLabel, nodeDef } from './nodeTypes'
import { translate as __ } from '@/translation'

const props = defineProps({
  edge: { type: Object, required: true },
  source: { type: Object, default: null },
  target: { type: Object, default: null },
})

const emit = defineEmits(['change', 'close', 'delete'])

const pathLabel = computed(() => `"${__(edgeLabel({ sourceHandle: props.edge.sourceHandle }, props.source) || props.edge.sourceHandle)}"`)
const showCondition = computed(() => !!props.edge.data?.condition || nodeDef(props.source?.data?.nodeType).category === 'advanced')

function name(node) {
  if (!node) return '?'
  const def = nodeDef(node.data.nodeType)

  return node.data.label && node.data.label !== def.label ? node.data.label : __(def.label)
}

const from = computed(() => name(props.source))
const to = computed(() => name(props.target))

const help = computed(() => {
  const branch = nodeDef(props.source?.data?.nodeType).type === 'if_else' && ['true', 'false'].includes(props.edge.sourceHandle)
  if (branch) {
    return props.edge.sourceHandle === 'true'
      ? __('Leave empty to follow this when the If condition is true.')
      : __('Leave empty to follow this when the If condition is false.')
  }

  return __('A Python expression evaluated against context. Leave empty to always follow this connection.')
})
</script>

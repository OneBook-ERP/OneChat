<template>
  <div class="flex h-full flex-col">
    <div class="flex items-start gap-2.5 border-b border-outline-gray-1 p-3">
      <span class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-4" :class="color.chip">
        <span :class="def.icon" class="size-4" aria-hidden="true" />
      </span>
      <div class="min-w-0 flex-1">
        <FormControl
          type="text"
          variant="ghost"
          class="-ml-2 text-base font-medium"
          :model-value="label"
          :placeholder="__(def.label)"
          @update:model-value="rename"
        />
        <TruncatedText as="p" class="truncate text-xs text-ink-gray-5" :text="__(def.description)" />
      </div>
      <Button variant="ghost" icon="lucide-x" :label="__('Close')" @click="emit('close')" />
    </div>

    <ScrollArea class="min-h-0 flex-1" viewport-class="p-3">
      <div class="flex flex-col gap-4">
        <div v-if="def.runnable === false" class="flex gap-2 rounded-4 bg-surface-amber-1 p-2.5 text-sm text-ink-amber-7">
          <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{{ __('The server does not run this step yet. The flow passes through it unchanged.') }}</span>
        </div>

        <div v-if="def.hint" class="flex gap-2 rounded-4 bg-surface-gray-2 p-2.5 text-sm text-ink-gray-7">
          <span class="lucide-info mt-0.5 size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
          <span>{{ __(def.hint) }}</span>
        </div>

        <div class="grid grid-cols-2 gap-x-3 gap-y-4">
          <template v-for="(field, index) in fields" :key="field.key || `section-${index}`">
            <p v-if="field.section" class="col-span-2 -mb-1 mt-1 border-t border-outline-gray-1 pt-3 text-sm font-medium text-ink-gray-6">
              {{ __(field.section) }}
            </p>
            <div v-else :class="field.half ? 'col-span-1' : 'col-span-2'">
              <InspectorField
                :field="field"
                :config="config"
                :model-value="config[field.key]"
                @update:model-value="(value) => set(field.key, value)"
              />
            </div>
          </template>
        </div>

        <div v-if="outputs && outputs.length" class="flex flex-col gap-1.5 rounded-4 border border-outline-gray-1 p-2.5">
          <p class="text-sm font-medium text-ink-gray-7">{{ __('Paths') }}</p>
          <p class="text-xs text-ink-gray-5">{{ __('Drag from each dot on the step to where that path should go.') }}</p>
          <div class="flex flex-wrap gap-1">
            <span
              v-for="output in outputs"
              :key="output.id"
              class="rounded-full px-2 py-0.5 text-xs"
              :class="output.muted ? 'bg-surface-gray-2 text-ink-gray-6' : 'bg-surface-green-2 text-ink-green-7'"
            >
              {{ __(output.label) }}
            </span>
          </div>
        </div>

        <EmptyState
          v-if="!def.fields.length && !outputs?.length"
          icon="lucide-sparkles"
          :title="__('Nothing to set up')"
          :description="__('This step is ready to use.')"
        />
      </div>
    </ScrollArea>

    <div class="flex items-center justify-between gap-2 border-t border-outline-gray-1 p-3">
      <Button variant="subtle" icon-left="lucide-copy" :label="__('Duplicate')" @click="emit('duplicate')" />
      <Button variant="subtle" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="emit('delete')" />
    </div>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { Button, FormControl, ScrollArea } from 'frappe-ui'
import InspectorField from './InspectorField.vue'
import { colorOf, nodeDef, outputsOf, visibleFields } from './nodeTypes'
import EmptyState from '@/components/Common/EmptyState.vue'
import { translate as __ } from '@/translation'

const props = defineProps({
  node: { type: Object, required: true },
})

const emit = defineEmits(['change', 'close', 'duplicate', 'delete'])

const def = computed(() => nodeDef(props.node.data.nodeType))
const color = computed(() => colorOf(props.node.data.nodeType))
const config = computed(() => props.node.data.config || {})
const fields = computed(() => visibleFields(props.node.data.nodeType, config.value))
const outputs = computed(() => outputsOf(props.node.data.nodeType, config.value))
const label = computed(() => (props.node.data.label === def.value.label ? __(def.value.label) : props.node.data.label || ''))

function set(key, value) {
  emit('change', { config: { ...config.value, [key]: value } })
}

function rename(value) {
  emit('change', { label: value })
}
</script>

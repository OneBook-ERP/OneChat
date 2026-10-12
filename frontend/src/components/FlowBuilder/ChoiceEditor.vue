<template>
  <div class="flex flex-col gap-1.5">
    <FormLabel :label="label" :required="required" />

    <div class="flex flex-col gap-1.5">
      <div v-for="(row, index) in rows" :key="row.id" class="flex items-start gap-1.5 rounded-4 bg-surface-gray-1 p-1.5">
        <span class="mt-2 w-4 shrink-0 text-center text-xs tabular-nums text-ink-gray-4">{{ index + 1 }}</span>
        <div class="flex min-w-0 flex-1 flex-col gap-1">
          <FormControl
            type="text"
            :model-value="row.title"
            :placeholder="__('Option {0}').format(index + 1)"
            :maxlength="titleLimit"
            @update:model-value="(value) => set(index, { title: value })"
          />
          <FormControl
            type="text"
            v-if="withDescription"
            size="sm"
            :model-value="row.description"
            :placeholder="__('Description (optional)')"
            :maxlength="72"
            @update:model-value="(value) => set(index, { description: value })"
          />
        </div>
        <div class="flex shrink-0 flex-col">
          <Button size="sm" variant="ghost" icon="lucide-chevron-up" :label="__('Move up')" :disabled="!index" @click="move(index, -1)" />
          <Button size="sm" variant="ghost" icon="lucide-x" :label="__('Remove')" @click="remove(index)" />
        </div>
      </div>
    </div>

    <Button v-if="rows.length < max" variant="subtle" icon-left="lucide-plus" :label="__('Add option')" @click="add" />
    <p class="text-xs text-ink-gray-5">
      {{ __('Up to {0} options, {1} characters each. Each option gets its own path on the canvas.').format(max, titleLimit) }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, FormControl, FormLabel } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  required: { type: Boolean, default: false },
  max: { type: Number, default: 3 },
  titleLimit: { type: Number, default: 20 },
  withDescription: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const rows = computed(() => props.modelValue || [])

function newId() {
  return `opt-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`
}

function commit(list) {
  emit('update:modelValue', list)
}

function set(index, patch) {
  commit(rows.value.map((row, position) => (position === index ? { ...row, ...patch } : row)))
}

function add() {
  commit([...rows.value, { id: newId(), title: '', description: '' }])
}

function remove(index) {
  commit(rows.value.filter((_, position) => position !== index))
}

function move(index, step) {
  const list = [...rows.value]
  const [row] = list.splice(index, 1)
  list.splice(index + step, 0, row)
  commit(list)
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="label" />
      <Button size="sm" variant="ghost" icon-left="lucide-plus" :label="__('Add')" @click="add" />
    </div>

    <p v-if="!rows.length" class="rounded-4 border border-dashed border-outline-gray-2 px-3 py-3 text-center text-xs text-ink-gray-5">
      {{ __('Nothing added yet') }}
    </p>

    <div v-for="(row, index) in rows" :key="row.id" class="flex items-center gap-1.5">
      <FormControl
        type="text"
        class="min-w-0 flex-1 font-mono"
        :model-value="row.value"
        :placeholder="placeholder"
        @update:model-value="(value) => set(index, value)"
      />
      <Button variant="ghost" icon="lucide-x" :label="__('Remove')" @click="remove(index)" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, FormControl, FormLabel } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const rows = ref([])
let seed = 0
let last = ''

watch(
  () => props.modelValue,
  (value) => {
    const incoming = JSON.stringify(value || [])
    if (incoming === last) return

    last = incoming
    rows.value = (value || []).map((item) => ({ id: seed++, value: String(item?.value ?? item ?? '') }))
  },
  { immediate: true, deep: true },
)

function commit() {
  const out = rows.value.filter((row) => row.value !== '').map((row) => ({ value: row.value }))
  last = JSON.stringify(out)
  emit('update:modelValue', out)
}

function set(index, value) {
  rows.value[index].value = value ?? ''
  commit()
}

function add() {
  rows.value.push({ id: seed++, value: '' })
}

function remove(index) {
  rows.value.splice(index, 1)
  commit()
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center justify-between">
      <FormLabel :label="__('Options')" :required="true" />
      <Button size="sm" variant="ghost" icon-left="lucide-plus" :label="__('Add option')" @click="add" />
    </div>

    <div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_56px] gap-1.5 px-0.5 text-xs text-ink-gray-5">
      <span>{{ __('Title') }}</span>
      <span>{{ __('ID (saved in the answer)') }}</span>
      <span />
    </div>

    <div v-for="(option, index) in options" :key="index" class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_56px] items-center gap-1.5">
      <FormControl
        type="text"
        size="sm"
        :model-value="option.title"
        :placeholder="__('Option {0}').format(index + 1)"
        @update:model-value="(value) => setTitle(index, value)"
      />
      <FormControl
        type="text"
        size="sm"
        :model-value="option.id"
        placeholder="option_id"
        @update:model-value="(value) => update(index, { id: value })"
      />
      <div class="flex items-center">
        <Button
          size="sm"
          variant="ghost"
          icon="lucide-arrow-up"
          :disabled="index === 0"
          :label="__('Move up')"
          @click="move(index, index - 1)"
        />
        <Button size="sm" variant="ghost" icon="lucide-x" :label="__('Remove')" @click="remove(index)" />
      </div>
    </div>

    <p v-if="!options.length" class="rounded-4 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-5">
      {{ __('Add the choices people can pick from.') }}
    </p>
  </div>
</template>

<script setup>
import { Button, FormControl, FormLabel } from 'frappe-ui'
import { slug } from './formSchema'
import { translate as __ } from '@/translation'

const props = defineProps({
  options: { type: Array, default: () => [] },
})

const emit = defineEmits(['change'])

function commit(next) {
  emit('change', next)
}

function update(index, patch) {
  commit(props.options.map((option, position) => (position === index ? { ...option, ...patch } : option)))
}

function setTitle(index, title) {
  const option = props.options[index]
  const auto = !option.id || option.id === slug(option.title) || /^option_\d+$/.test(option.id)
  update(index, auto && slug(title) ? { title, id: slug(title) } : { title })
}

function add() {
  const taken = props.options.map((option) => option.id)
  let number = props.options.length + 1
  while (taken.includes(`option_${number}`)) number += 1

  commit([...props.options, { id: `option_${number}`, title: '' }])
}

function remove(index) {
  commit(props.options.filter((option, position) => position !== index))
}

function move(from, to) {
  const next = [...props.options]
  next.splice(to, 0, next.splice(from, 1)[0])
  commit(next)
}
</script>

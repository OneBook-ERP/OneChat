<template>
  <form class="flex flex-col gap-3 bg-surface-gray-1 p-3" @submit.prevent="emit('save')" @keydown.esc.stop="emit('cancel')">
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <FormControl type="text" ref="nameInput" v-model="label.label_name" :label="__('Name')" :placeholder="__('VIP')" required />
      <FormControl type="text" v-model="label.description" :label="__('Description')" :placeholder="__('Optional')" />
    </div>

    <div class="flex flex-col gap-1.5">
      <span class="text-xs text-ink-gray-5">{{ __('Colour') }}</span>
      <div class="flex items-center gap-1" role="radiogroup" :aria-label="__('Colour')">
        <button
          v-for="color in LABEL_COLORS"
          :key="color"
          type="button"
          role="radio"
          :aria-checked="label.color === color"
          :aria-label="__(COLOR_NAMES[color])"
          :title="__(COLOR_NAMES[color])"
          class="grid size-7 place-content-center rounded-full border-2 transition-colors focus-visible:focus-ring"
          :class="label.color === color ? 'border-outline-gray-4' : 'border-transparent hover:border-outline-gray-2'"
          @click="label.color = color"
        >
          <span class="size-4 rounded-full" :class="LABEL_DOTS[color]" />
        </button>
      </div>
    </div>

    <ErrorMessage :message="error" />

    <div class="flex justify-end gap-2">
      <Button variant="subtle" :label="__('Cancel')" @click="emit('cancel')" />
      <Button
        variant="solid"
        type="submit"
        :label="label.name ? __('Save') : __('Add label')"
        :loading="saving"
        :disabled="!label.label_name.trim()"
      />
    </div>
  </form>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { Button, ErrorMessage, FormControl } from 'frappe-ui'
import { LABEL_COLORS, LABEL_DOTS } from '@/data/inbox'
import { translate as __ } from '@/translation'

const COLOR_NAMES = {
  gray: 'Gray',
  blue: 'Blue',
  green: 'Green',
  amber: 'Amber',
  red: 'Red',
  violet: 'Violet',
}

defineProps({
  saving: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['save', 'cancel'])

const label = defineModel('label', { type: Object, required: true })

const nameInput = ref(null)

onMounted(() => nextTick(() => nameInput.value?.$el?.querySelector?.('input')?.focus()))
</script>

<template>
  <ScrollArea class="min-h-0 min-w-0 flex-1 bg-surface-gray-1" viewport-class="px-6 py-5">
    <div class="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <section class="flex flex-col gap-3 rounded-5 border border-outline-gray-2 bg-surface-base p-4">
        <div class="flex items-center justify-between gap-2">
          <p class="text-base font-medium text-ink-gray-8">{{ __('Screen') }}</p>
          <Badge v-if="screen.terminal" theme="green" :label="__('Final screen')" />
          <Button v-else size="sm" variant="ghost" icon-left="lucide-flag" :label="__('Make final screen')" @click="emit('terminal')" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <FormControl
            type="text"
            :label="__('Title')"
            :required="true"
            :description="__('Shown in the top bar of the form')"
            :model-value="screen.screen_title"
            @update:model-value="setTitle"
          />
          <FormControl
            type="text"
            :label="__('Screen ID')"
            :description="__('Letters and underscores only')"
            :model-value="screen.screen_id"
            @update:model-value="(value) => emit('change', { screen_id: value.toUpperCase(), autoId: false })"
          />
        </div>

        <FormControl
          v-if="screen.terminal"
          type="text"
          :label="__('Success message')"
          :description="__('Kept with the form for your team; WhatsApp shows its own confirmation.')"
          :model-value="screen.success_message"
          @update:model-value="(value) => emit('change', { success_message: value })"
        />

        <Checkbox
          :label="__('Refresh when someone goes back to this screen')"
          :model-value="screen.refresh_on_back"
          @update:model-value="(value) => emit('change', { refresh_on_back: !!value })"
        />

        <ul v-if="screenIssues.length" class="flex flex-col gap-1">
          <li
            v-for="(issue, index) in screenIssues"
            :key="index"
            class="flex items-start gap-2 text-sm"
            :class="issue.level === 'error' ? 'text-ink-red-3' : 'text-ink-amber-6'"
          >
            <span
              :class="issue.level === 'error' ? 'lucide-circle-x' : 'lucide-triangle-alert'"
              class="mt-0.5 size-3.5 shrink-0"
              aria-hidden="true"
            />
            {{ issue.message }}
          </li>
        </ul>
      </section>

      <div class="flex items-center justify-between">
        <p class="text-base font-medium text-ink-gray-8">
          {{ __('Fields') }}
          <span class="ml-1 font-normal text-ink-gray-5">{{ screen.fields.length }}</span>
        </p>
        <Dropdown :options="addMenu" align="end">
          <Button variant="subtle" icon-left="lucide-plus" :label="__('Add field')" />
        </Dropdown>
      </div>

      <div
        v-if="!screen.fields.length"
        class="flex flex-col items-center gap-2 rounded-5 border border-dashed border-outline-gray-2 px-6 py-10 text-center"
      >
        <span class="lucide-text-cursor-input size-6 text-ink-gray-4" aria-hidden="true" />
        <p class="text-base font-medium text-ink-gray-8">{{ __('This screen is empty') }}</p>
        <p class="max-w-sm text-sm text-ink-gray-5">{{ __('Use Add field to put questions, choices or text on this screen.') }}</p>
      </div>

      <div
        v-for="(field, index) in screen.fields"
        :key="field.key"
        class="rounded-5"
        :class="overIndex === index && dragIndex !== null && dragIndex !== index ? 'ring-2 ring-outline-gray-3' : ''"
        @dragover.prevent="overIndex = index"
        @drop.prevent="onDrop(index)"
      >
        <FieldCard
          :field="field"
          :screens="screens"
          :screen-key="screen.key"
          :expanded="field.key === selectedField"
          :issues="fieldIssues[field.key] || []"
          @select="emit('select-field', field.key === selectedField ? null : field.key)"
          @change="(patch) => emit('change-field', field.key, patch)"
          @duplicate="emit('duplicate-field', field.key)"
          @remove="emit('remove-field', field.key)"
          @move="(target) => emit('move-field-to', field.key, target)"
          @dragstart="(event) => onDragStart(event, index)"
        />
      </div>
    </div>
  </ScrollArea>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Checkbox, Dropdown, FormControl, ScrollArea } from 'frappe-ui'
import FieldCard from './FieldCard.vue'
import { FIELD_GROUPS, FIELD_TYPES, screenSlug } from './formSchema'
import { translate as __ } from '@/translation'

const props = defineProps({
  screen: { type: Object, required: true },
  screens: { type: Array, required: true },
  selectedField: { type: String, default: null },
  issues: { type: Array, default: () => [] },
})

const emit = defineEmits([
  'change',
  'terminal',
  'add-field',
  'select-field',
  'change-field',
  'duplicate-field',
  'remove-field',
  'move-field',
  'move-field-to',
])

const dragIndex = ref(null)
const overIndex = ref(null)

const addMenu = FIELD_GROUPS.map((group) => ({
  group: __(group),
  options: FIELD_TYPES.filter((item) => item.group === group).map((item) => ({
    label: __(item.label),
    icon: item.icon,
    onClick: () => emit('add-field', item.type),
  })),
}))

const screenIssues = computed(() => props.issues.filter((issue) => issue.screenKey === props.screen.key && !issue.fieldKey))

const fieldIssues = computed(() => {
  const out = {}
  for (const issue of props.issues) {
    if (!issue.fieldKey) continue
    out[issue.fieldKey] = [...(out[issue.fieldKey] || []), issue]
  }

  return out
})

function setTitle(value) {
  const patch = { screen_title: value }
  if (props.screen.autoId && screenSlug(value)) patch.screen_id = screenSlug(value)
  emit('change', patch)
}

function onDragStart(event, index) {
  dragIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(index))
  const card = event.target.closest('[class*="rounded-5"]')
  if (card) event.dataTransfer.setDragImage(card, 16, 16)
  window.addEventListener('dragend', reset, { once: true })
}

function onDrop(index) {
  if (dragIndex.value !== null && dragIndex.value !== index) emit('move-field', dragIndex.value, index)
  reset()
}

function reset() {
  dragIndex.value = null
  overIndex.value = null
}
</script>

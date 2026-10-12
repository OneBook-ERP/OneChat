<template>
  <div :id="`note-${note.name}`" class="group my-2 flex justify-center">
    <article
      class="relative w-full max-w-xl rounded-4 border px-3 pb-2 pt-1.5 transition-colors duration-500"
      :class="highlighted ? 'border-outline-amber-4 bg-surface-amber-2' : 'border-outline-amber-2 bg-surface-amber-1'"
      :aria-label="__('Internal note')"
    >
      <header class="flex min-h-7 items-center gap-1.5 text-xs text-ink-amber-7">
        <span class="lucide-lock size-3.5 shrink-0" aria-hidden="true" />
        <p class="min-w-0 flex-1 truncate">
          <span class="font-medium">{{ __('Internal note') }}</span>
          · {{ author }} ·
          <span class="tabular-nums">{{ clock(note.creation) }}</span>
          <span v-if="edited"> · {{ __('edited') }}</span>
        </p>
        <Dropdown v-if="editable && !editing" :options="menu" align="end">
          <Button
            variant="ghost"
            size="sm"
            icon="lucide-ellipsis"
            :label="__('Note actions')"
            class="shrink-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100 sm:opacity-0"
          />
        </Dropdown>
      </header>

      <form v-if="editing" class="mt-1 flex flex-col gap-2" @submit.prevent="save">
        <Textarea ref="editor" v-model="draft" :rows="3" :aria-label="__('Edit note')" @keydown="onKeydown" />
        <div class="flex justify-end gap-2">
          <Button variant="subtle" size="sm" :label="__('Cancel')" @click="editing = false" />
          <Button variant="solid" size="sm" type="submit" :label="__('Save')" :loading="saving" :disabled="!draft.trim()" />
        </div>
      </form>

      <template v-else>
        <p v-if="showTitle" class="mt-0.5 text-sm font-medium text-ink-gray-9">{{ note.title }}</p>
        <p class="mt-0.5 whitespace-pre-wrap break-words text-base leading-relaxed text-ink-gray-9 [overflow-wrap:anywhere]">
          {{ text }}
        </p>
      </template>
    </article>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { Button, Dropdown, Textarea, dayjs, toast } from 'frappe-ui'
import { canEditNote, deleteNote, plainMessage, saveNote } from '@/data/inbox'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { clock, errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  note: { type: Object, required: true },
  contact: { type: String, required: true },
  highlighted: { type: Boolean, default: false },
})

const ui = useUI()
const editing = ref(false)
const draft = ref('')
const saving = ref(false)
const editor = ref(null)

const text = computed(() => plainMessage(props.note.content))
const showTitle = computed(() => !!props.note.title && !text.value.startsWith(props.note.title))
const author = computed(() => (props.note.owner === session.user.name ? __('You') : props.note.owner_name || props.note.owner))
const edited = computed(() => !!props.note.modified && dayjs(props.note.modified).diff(dayjs(props.note.creation), 'second') > 60)
const editable = computed(() => canEditNote(props.note))

const menu = computed(() => [
  { label: __('Edit'), icon: 'lucide-pencil', onClick: edit },
  { label: __('Delete'), icon: 'lucide-trash-2', onClick: remove },
])

function edit() {
  draft.value = text.value
  editing.value = true
  nextTick(() => editor.value?.inputElement?.focus?.())
}

async function save() {
  const content = draft.value.trim()
  if (!content || saving.value) return

  saving.value = true
  try {
    await saveNote(props.contact, content, props.note.name)
    editing.value = false
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    editing.value = false
    return
  }

  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    save()
  }
}

function remove() {
  ui.confirm({
    title: __('Delete this note?'),
    message: __('Your team will no longer see it in this conversation.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await deleteNote(props.contact, props.note)
      toast.success(__('Note deleted'))
    },
  })
}
</script>

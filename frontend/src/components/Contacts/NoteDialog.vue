<template>
  <ResponsiveDialog v-model:open="open" :title="name ? __('Edit note') : __('New note')" size="xl">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-3">
        <Skeleton class="h-9 w-full" />
        <Skeleton class="h-40 w-full" />
      </div>

      <div v-else class="flex flex-col gap-4">
        <FormControl v-model="title" type="text" :label="__('Title')" :placeholder="__('What is this about?')" />
        <FormControl v-model="body" type="textarea" :rows="10" :label="__('Note')" :required="true" />
        <LinkField
          v-model="contact"
          doctype="OneChat Contact"
          :label="__('Contact')"
          :description="__('Optional. Linked notes show up on the contact.')"
        />
        <p v-if="other && !contact" class="text-sm text-ink-gray-5">
          {{ __('Linked to {0} {1}').format(__(other.doctype), other.name) }}
        </p>
      </div>

      <ErrorMessage :message="error" class="mt-4" />
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <div>
          <Button v-if="name" variant="ghost" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="remove" />
        </div>
        <div class="flex items-center gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
          <Button variant="solid" :loading="saving" :label="name ? __('Save') : __('Create')" @click="save" />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, Skeleton, call, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import LinkField from '@/components/Common/LinkField.vue'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
  contactName: { type: String, default: null },
})

const emit = defineEmits(['saved', 'deleted'])

const open = defineModel('open', { type: Boolean, default: false })

const ui = useUI()
const title = ref('')
const body = ref('')
const contact = ref(null)
const other = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')

function toText(html) {
  const element = document.createElement('div')
  element.innerHTML = String(html || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li|h\d)>/gi, '\n')

  return (element.textContent || '').replace(/\n{3,}/g, '\n\n').trim()
}

function toHtml(text) {
  const element = document.createElement('div')

  return text
    .split('\n')
    .map((line) => {
      element.textContent = line
      return `<p>${element.innerHTML || '<br>'}</p>`
    })
    .join('')
}

watch(
  open,
  async (value) => {
    if (!value) return

    error.value = ''
    title.value = ''
    body.value = ''
    contact.value = props.contactName
    other.value = null

    if (!props.name) return

    loading.value = true
    try {
      const doc = await call('frappe.client.get', { doctype: 'OneChat Note', name: props.name })
      title.value = doc.title || ''
      body.value = toText(doc.content)
      contact.value = doc.reference_doctype === 'OneChat Contact' ? doc.reference_docname : null
      if (doc.reference_doctype && doc.reference_doctype !== 'OneChat Contact') {
        other.value = { doctype: doc.reference_doctype, name: doc.reference_docname }
      }
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

async function save() {
  if (!body.value.trim()) {
    error.value = __('Write something first')
    return
  }

  const values = {
    title: title.value.trim() || body.value.trim().split('\n')[0].slice(0, 80),
    content: toHtml(body.value.trim()),
    reference_doctype: contact.value ? 'OneChat Contact' : other.value?.doctype || null,
    reference_docname: contact.value || other.value?.name || null,
  }

  saving.value = true
  error.value = ''

  try {
    const doc = props.name
      ? await call('frappe.client.set_value', { doctype: 'OneChat Note', name: props.name, fieldname: values })
      : await call('frappe.client.insert', { doc: { doctype: 'OneChat Note', ...values } })

    toast.success(props.name ? __('Saved') : __('Created'))
    emit('saved', doc)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function remove() {
  ui.confirm({
    title: __('Delete this note?'),
    message: __('This cannot be undone.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: 'OneChat Note', name: props.name })
      toast.success(__('Deleted'))
      emit('deleted', props.name)
      open.value = false
    },
  })
}
</script>

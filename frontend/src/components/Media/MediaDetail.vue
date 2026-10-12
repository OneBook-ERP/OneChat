<template>
  <ResponsiveDialog v-model:open="open" :title="doc.title || __('Media')" size="2xl">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-3">
        <Skeleton class="aspect-video w-full rounded-5" />
        <Skeleton v-for="row in 3" :key="row" class="h-9 w-full" />
      </div>

      <div v-else class="flex flex-col gap-4">
        <div class="flex items-center justify-center overflow-hidden rounded-5 bg-surface-gray-2">
          <img v-if="doc.media_type === 'image'" :src="doc.file" :alt="doc.title" class="max-h-80 w-auto max-w-full object-contain" />
          <video v-else-if="doc.media_type === 'video'" :src="doc.file" controls class="max-h-80 w-full" />
          <div v-else-if="doc.media_type === 'audio'" class="flex w-full flex-col items-center gap-3 p-6">
            <span class="lucide-audio-lines size-6 text-ink-gray-5" aria-hidden="true" />
            <audio :src="doc.file" controls class="w-full" />
          </div>
          <div v-else class="flex flex-col items-center gap-2 p-8">
            <span class="lucide-file-text size-6 text-ink-gray-5" aria-hidden="true" />
            <TruncatedText as="p" class="max-w-full truncate text-sm text-ink-gray-6" :text="fileName(doc.file)" />
            <Button variant="subtle" icon-left="lucide-external-link" :label="__('Open file')" :link="doc.file" />
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-gray-5">
          <span>{{ mediaTypeLabel(doc.media_type) }}</span>
          <span v-if="extension(doc.file)">{{ extension(doc.file) }}</span>
          <span v-if="doc.file_size">{{ fileSize(doc.file_size) }}</span>
          <span v-if="doc.creation">{{ __('Uploaded {0}').format(formatDate(doc.creation)) }}</span>
        </div>

        <div class="flex items-end gap-2">
          <FormControl class="min-w-0 flex-1" type="text" :label="__('Link')" :model-value="link" readonly />
          <Button icon-left="lucide-copy" :label="__('Copy link')" @click="copy" />
        </div>

        <FormControl v-model="doc.title" type="text" :label="__('Title')" />
        <FormControl v-model="doc.tags" type="text" :label="__('Tags')" :description="__('Separate tags with commas')" />
        <FormControl v-model="doc.description" type="textarea" :label="__('Description')" :rows="3" />

        <ErrorMessage :message="error" />
      </div>
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <Button variant="ghost" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="remove" />
        <div class="flex items-center gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
          <Button variant="solid" :loading="saving" :disabled="loading" :label="__('Save')" @click="save" />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, Skeleton, call, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { absoluteUrl, extension, fileName, fileSize, mediaTypeLabel, splitTags } from './media'
import { useUI } from '@/stores/ui'
import { errorMessage, formatDate } from '@/utils/format'
import { translate as __ } from '@/translation'

const DOCTYPE = 'OneChat Media'

const props = defineProps({
  name: { type: String, default: null },
})

const emit = defineEmits(['saved', 'deleted'])

const open = defineModel('open', { type: Boolean, default: false })

const ui = useUI()
const doc = ref({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const link = computed(() => absoluteUrl(doc.value.file))

watch(
  open,
  async (value) => {
    if (!value || !props.name) return

    error.value = ''
    loading.value = true
    try {
      doc.value = await call('frappe.client.get', { doctype: DOCTYPE, name: props.name })
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

async function copy() {
  try {
    await navigator.clipboard.writeText(link.value)
    toast.success(__('Link copied'))
  } catch {
    toast.error(__('Could not copy the link'))
  }
}

async function save() {
  const title = (doc.value.title || '').trim()
  if (!title) {
    error.value = __('Fill in {0}').format(__('Title'))
    return
  }

  saving.value = true
  error.value = ''

  try {
    const saved = await call('frappe.client.set_value', {
      doctype: DOCTYPE,
      name: props.name,
      fieldname: {
        title,
        tags: splitTags(doc.value.tags).join(', '),
        description: doc.value.description || '',
      },
    })
    toast.success(__('Saved'))
    emit('saved', saved)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function remove() {
  ui.confirm({
    title: __('Delete {0}?').format(doc.value.title || __('this file')),
    message: __('It is removed from the media library. Messages already sent are not affected.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: DOCTYPE, name: props.name })
      toast.success(__('Deleted'))
      emit('deleted', props.name)
      open.value = false
    },
  })
}
</script>

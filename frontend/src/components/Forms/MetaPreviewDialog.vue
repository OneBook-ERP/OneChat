<template>
  <ResponsiveDialog v-model:open="open" :title="__('Preview on WhatsApp')" size="5xl">
    <template #default>
      <div class="flex flex-col gap-3">
        <p class="text-sm text-ink-gray-5">{{ __('This is Meta’s own preview of the version uploaded to WhatsApp.') }}</p>
        <div
          class="flex h-[70vh] items-center justify-center overflow-hidden rounded-5 border border-outline-gray-2 bg-surface-gray-1 sm:h-[min(820px,calc(100vh-14rem))]"
        >
          <LoadingIndicator v-if="loading" class="size-6 text-ink-gray-5" />
          <ErrorMessage v-else-if="error" class="p-4" :message="error" />
          <iframe v-else-if="url" :src="url" class="size-full border-0" :title="__('Preview on WhatsApp')" />
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex w-full justify-between gap-2">
        <Button variant="ghost" icon-left="lucide-external-link" :disabled="!url" :label="__('Open in new tab')" @click="openTab" />
        <Button variant="subtle" :label="__('Close')" @click="open = false" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, ErrorMessage, LoadingIndicator, call } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { docMethod } from './formSchema'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
})

const emit = defineEmits(['loaded'])

const open = defineModel('open', { type: Boolean, default: false })

const url = ref('')
const loading = ref(false)
const error = ref('')

async function load() {
  if (!props.name) return

  loading.value = true
  error.value = ''
  try {
    url.value = previewUrl(await call('run_doc_method', docMethod(props.name, 'get_flow_preview')))
    if (!url.value) error.value = __('Meta did not return a preview link. Check the form was uploaded, then try again.')
    emit('loaded', url.value)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function previewUrl(result) {
  const value = typeof result === 'string' ? result : result?.message || result?.preview_url || ''

  return /^https:\/\//.test(value) ? value : ''
}

function openTab() {
  window.open(url.value, '_blank', 'noopener')
}

watch(open, (value) => {
  if (value) load()
})
</script>

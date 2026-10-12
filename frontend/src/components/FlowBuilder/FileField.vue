<template>
  <div class="flex flex-col gap-1.5">
    <FormLabel :label="label" />
    <div class="flex items-center gap-2">
      <FileUploader :file-types="ACCEPT" :private="privateUpload" @success="(file) => emit('update:modelValue', file.file_url)">
        <template #default="{ openFileSelector, uploading, progress }">
          <Button
            icon-left="lucide-upload"
            :loading="uploading"
            :label="uploading ? __('Uploading {0}%').format(progress) : modelValue ? __('Replace') : __('Upload')"
            @click="openFileSelector"
          />
        </template>
      </FileUploader>
      <TruncatedText
        class="min-w-0 flex-1 truncate text-sm text-ink-gray-6"
        :text="modelValue ? fileName(modelValue) : __('Image, video or document')"
      />
      <Badge
        v-if="modelValue && !modelValue.startsWith('http')"
        size="sm"
        variant="subtle"
        :theme="modelValue.startsWith('/private/') ? 'amber' : 'gray'"
        :label="modelValue.startsWith('/private/') ? __('Private') : __('Public')"
      />
      <Button v-if="modelValue" variant="ghost" icon="lucide-x" :label="__('Remove')" @click="emit('update:modelValue', '')" />
    </div>
    <div v-if="!modelValue" class="flex items-center gap-2">
      <Switch v-model="privateUpload" :label="__('Upload as private')" />
      <InfoHint
        :title="__('Private files')"
        :text="
          __(
            'Public files can be opened by anyone with the link. Private files need a login on this site, so OneChat uploads them to WhatsApp directly when it sends the message.',
          )
        "
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Badge, Button, FileUploader, FormLabel, Switch } from 'frappe-ui'
import InfoHint from '@/components/Common/InfoHint.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { fileName } from '@/data/inbox'
import { translate as __ } from '@/translation'

defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const privateUpload = ref(false)

const ACCEPT = ['image/jpeg', 'image/png', 'video/mp4', 'audio/*', '.pdf', '.doc', '.docx', '.xls', '.xlsx']
</script>

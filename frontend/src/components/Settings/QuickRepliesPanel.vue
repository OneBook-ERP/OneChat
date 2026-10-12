<template>
  <SettingsHeader>
    <div class="flex flex-col gap-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Quick replies') }}</h2>
          <p class="mt-1 text-base text-ink-gray-6">
            {{ __('Saved answers the whole team can insert by typing / in a conversation') }}
          </p>
        </div>
        <Button variant="solid" icon-left="lucide-plus" :label="__('Add quick reply')" data-tour="new-quick-reply" @click="edit(null)" />
      </div>
      <FormControl v-model="search" type="search" :placeholder="__('Search shortcut, title or message')">
        <template #prefix>
          <span class="lucide-search size-4 text-ink-gray-4" aria-hidden="true" />
        </template>
      </FormControl>
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <ListSkeleton v-if="!loaded" class="pt-4" :rows="4" />

    <div v-else-if="filtered.length" class="mt-4 divide-y divide-outline-gray-1 overflow-hidden rounded-4 border border-outline-gray-2">
      <button
        v-for="row in filtered"
        :key="row.name"
        type="button"
        class="flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-gray-1 focus-visible:focus-ring"
        @click="edit(row.name)"
      >
        <Badge theme="gray" variant="subtle" class="mt-0.5 shrink-0 font-mono" :label="`/${row.shortcut}`" />
        <span class="min-w-0 flex-1">
          <TruncatedText class="block truncate text-base text-ink-gray-8" :text="row.title" />
          <TruncatedText class="mt-0.5 block truncate text-sm text-ink-gray-5" :text="row.message" />
        </span>
        <Tooltip v-if="row.attach" :text="fileName(row.attach)">
          <span class="mt-1 flex shrink-0 text-ink-gray-5">
            <span class="lucide-paperclip size-4" aria-hidden="true" />
            <span class="sr-only">{{ __('Has an attachment') }}</span>
          </span>
        </Tooltip>
      </button>
    </div>

    <EmptyState
      v-else
      class="mt-6"
      :icon="search ? 'lucide-search-x' : 'lucide-message-square-quote'"
      :title="search ? __('No quick reply matches that search') : __('No quick replies yet')"
      :description="search ? '' : __('Save answers you send often, then type / in the composer to insert them.')"
    />

    <DocFormDialog
      v-model:open="editing.open"
      doctype="OneChat Quick Reply"
      :name="editing.name"
      :title="editing.name ? __('Edit quick reply') : __('New quick reply')"
      :fields="FIELDS"
      size="xl"
      @saved="reload"
      @deleted="reload"
    >
      <template #field-shortcut="{ doc }">
        <FormControl
          type="text"
          :model-value="doc.shortcut"
          :label="__('Shortcut')"
          :placeholder="__('greeting')"
          :description="__('Lowercase letters, digits and dashes')"
          required
          @update:model-value="(value) => (doc.shortcut = cleanShortcut(value))"
        >
          <template #prefix>
            <span class="font-mono text-ink-gray-5" aria-hidden="true">/</span>
          </template>
        </FormControl>
      </template>

      <template #field-message="{ doc }">
        <div class="flex flex-col gap-1.5">
          <PersonalizedText
            v-model="doc.message"
            :label="__('Message')"
            :rows="5"
            required
            :variables="PLACEHOLDERS"
            :placeholder="__('Hi {0}, thanks for reaching out!').format('{{first_name}}')"
          />
        </div>
      </template>

      <template #field-attach="{ doc }">
        <div class="flex flex-col gap-1.5">
          <FormLabel :label="__('Attachment')" />
          <div class="flex flex-wrap items-center gap-2">
            <img
              v-if="doc.attach && isImage(doc.attach)"
              :src="doc.attach"
              alt=""
              class="size-12 shrink-0 rounded-4 border border-outline-gray-1 object-cover"
            />
            <FileUploader :private="false" :file-types="ACCEPT" @success="(file) => (doc.attach = file.file_url)">
              <template #default="{ openFileSelector, uploading, progress }">
                <Button
                  icon-left="lucide-upload"
                  :loading="uploading"
                  :label="uploading ? __('Uploading {0}%').format(progress) : __('Upload')"
                  @click="openFileSelector"
                />
              </template>
            </FileUploader>
            <Button icon-left="lucide-images" :label="__('Media library')" @click="openLibrary(doc)" />
            <TruncatedText
              class="min-w-0 truncate text-sm text-ink-gray-6"
              :text="doc.attach ? fileName(doc.attach) : __('Optional. An image, video or document sent with the reply.')"
            />
            <Button v-if="doc.attach" variant="ghost" icon="lucide-x" :label="__('Remove attachment')" @click="doc.attach = ''" />
          </div>
        </div>
      </template>
    </DocFormDialog>

    <MediaPicker v-model:open="library" @pick="pickFromLibrary" />
  </SettingsBody>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { Badge, Button, ErrorMessage, FileUploader, FormControl, FormLabel, SettingsBody, SettingsHeader, Tooltip } from 'frappe-ui'
import DocFormDialog from '@/components/Common/DocFormDialog.vue'
import PersonalizedText from '@/components/Common/PersonalizedText.vue'
import { AGENT_DETAILS, CONTACT_DETAILS } from '@/data/personalization'
import MediaPicker from '@/components/Media/MediaPicker.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import ListSkeleton from '@/components/Common/ListSkeleton.vue'
import { fileName, quickReplies } from '@/data/inbox'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const ACCEPT = [
  'image/jpeg',
  'image/png',
  'video/mp4',
  'video/3gpp',
  'audio/*',
  '.pdf',
  '.doc',
  '.docx',
  '.xls',
  '.xlsx',
  '.ppt',
  '.pptx',
  '.txt',
  '.csv',
]

const PLACEHOLDERS = [...CONTACT_DETAILS, ...AGENT_DETAILS]

const FIELDS = [
  { fieldname: 'shortcut', label: 'Shortcut', type: 'data', required: true, half: true },
  { fieldname: 'title', label: 'Title', type: 'data', required: true, half: true },
  { fieldname: 'message', label: 'Message', type: 'textarea' },
  { fieldname: 'attach', label: 'Attachment', type: 'data' },
]

const search = ref('')
const library = ref(false)
let libraryDoc = null

function isImage(url) {
  return /\.(jpe?g|png|webp|gif)$/i.test(String(url || '').split('?')[0])
}

function openLibrary(doc) {
  libraryDoc = doc
  library.value = true
}

function pickFromLibrary(item) {
  if (libraryDoc) libraryDoc.attach = item.file_url
  library.value = false
}
const loaded = ref(false)
const error = ref('')
const editing = reactive({ open: false, name: null })

const filtered = computed(() => {
  const rows = quickReplies.data || []
  const text = search.value.trim().replace(/^\//, '').toLowerCase()
  if (!text) return rows

  return rows.filter((row) => `${row.shortcut} ${row.title} ${row.message}`.toLowerCase().includes(text))
})

function cleanShortcut(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/^\/+/, '')
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
}

function edit(name) {
  editing.name = name
  editing.open = true
}

async function reload() {
  error.value = ''

  try {
    await quickReplies.reload()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loaded.value = true
  }
}

onMounted(reload)
</script>

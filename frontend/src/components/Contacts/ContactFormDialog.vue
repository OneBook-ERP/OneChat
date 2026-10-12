<template>
  <DocFormDialog
    v-model:open="open"
    doctype="OneChat Contact"
    :name="name"
    :title="name ? __('Edit contact') : __('New contact')"
    :fields="fields"
    :defaults="defaults"
    @saved="(doc) => emit('saved', doc)"
    @deleted="(doc) => emit('deleted', doc)"
  >
    <template #field-profile_image="{ doc }">
      <div class="flex items-center gap-3">
        <Avatar :image="doc.profile_image" :label="doc.contact_name || doc.mobile_no || '?'" size="3xl" />
        <FileUploader :file-types="'image/*'" :private="false" @success="(file) => (doc.profile_image = file.file_url)">
          <template #default="{ uploading, progress, openFileSelector }">
            <div class="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="subtle"
                icon-left="lucide-image-up"
                :loading="uploading"
                :label="uploading ? `${progress}%` : doc.profile_image ? __('Replace photo') : __('Upload photo')"
                @click="openFileSelector"
              />
              <Button
                v-if="doc.profile_image && !uploading"
                size="sm"
                variant="ghost"
                :label="__('Remove')"
                @click="doc.profile_image = null"
              />
            </div>
          </template>
        </FileUploader>
      </div>
    </template>

    <template #field-reference_doctype="{ doc }">
      <FormControl
        type="select"
        :label="__('Linked to')"
        :options="typeOptions"
        :model-value="doc.reference_doctype || ''"
        @update:model-value="(value) => setType(doc, value)"
      />
    </template>

    <template #field-reference_docname="{ doc }">
      <LinkField
        v-if="doc.reference_doctype"
        :key="doc.reference_doctype"
        v-model="doc.reference_docname"
        :doctype="doc.reference_doctype"
        :label="__('Linked {0}').format(__(doc.reference_doctype))"
      />
      <p v-else class="pt-6 text-sm text-ink-gray-5">
        {{
          typeOptions.length > 1
            ? __('Pick a record type to link this contact.')
            : __('Install an integration such as ERPNext to link contacts to records.')
        }}
      </p>
    </template>
  </DocFormDialog>
</template>

<script setup>
import { computed } from 'vue'
import { Avatar, Button, FileUploader, FormControl } from 'frappe-ui'
import DocFormDialog from '@/components/Common/DocFormDialog.vue'
import LinkField from '@/components/Common/LinkField.vue'
import { linkTypes } from '@/data/integrations'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
  defaults: { type: Object, default: () => ({ reference_doctype: '', disable: 0 }) },
})

const emit = defineEmits(['saved', 'deleted'])

const open = defineModel('open', { type: Boolean, default: false })

const typeOptions = computed(() => [
  { label: '—', value: '' },
  ...linkTypes.value.map((row) => ({ label: __(row.doctype), value: row.doctype })),
])

const BASE = [
  { fieldname: 'profile_image', label: 'Photo', type: 'data' },
  { fieldname: 'contact_name', label: 'Name', type: 'data', required: true },
  {
    fieldname: 'mobile_no',
    label: 'Mobile number',
    type: 'phone',
    required: true,
    half: true,
    placeholder: '+91 98765 43210',
    description: 'Include the country code',
  },
  { fieldname: 'email', label: 'Email', type: 'email', half: true },
]

const LINK = [
  { section: 'Linked record' },
  { fieldname: 'reference_doctype', label: 'Contact type', type: 'select', half: true },
  { fieldname: 'reference_docname', label: 'Linked record', type: 'link', half: true },
]

const STATUS = [
  { section: 'Status' },
  { fieldname: 'disable', label: 'Disabled', type: 'check', description: 'Hide this contact from pickers and broadcasts' },
]

const fields = computed(() => (props.name ? [...BASE, ...LINK, ...STATUS] : BASE))

function setType(doc, value) {
  if (doc.reference_doctype !== value) doc.reference_docname = null
  doc.reference_doctype = value
}
</script>

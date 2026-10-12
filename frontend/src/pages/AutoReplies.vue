<template>
  <AppHeader>
    <template #actions>
      <Button variant="subtle" icon-left="lucide-flask-conical" :label="__('Test')" @click="tester = true" />
      <Button variant="solid" icon-left="lucide-plus" :label="__('New auto reply')" data-tour="new-auto-reply" @click="openRule(null)" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search by name or keyword')"
      empty-icon="lucide-message-square-reply"
      :empty-title="__('No auto replies yet')"
      :empty-description="__('Reply instantly when a customer message contains a keyword, like price, hours or order status.')"
      export-name="auto-replies"
      @open="(row) => openRule(row.name)"
    >
      <template #cell-rule_name="{ row }">
        <div class="min-w-0">
          <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.rule_name" />
          <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="keywordLine(row.keywords)" />
        </div>
      </template>

      <template #cell-active_when="{ row }">
        <Badge :theme="row.active_when === 'Always' ? 'gray' : 'blue'" :label="__(row.active_when)" />
      </template>

      <template #cell-enabled="{ row }">
        <div class="flex justify-end" @click.stop>
          <Switch :model-value="!!row.enabled" :disabled="toggling === row.name" @update:model-value="(value) => toggle(row, value)" />
        </div>
      </template>
    </DocListView>
  </div>

  <DocFormDialog
    v-model:open="editor"
    doctype="OneChat Auto Reply"
    :name="editing"
    :title="editing ? __('Edit auto reply') : __('New auto reply')"
    :fields="fields"
    :defaults="defaults"
    @saved="list.refresh"
    @deleted="list.refresh"
  >
    <template #field-message="{ doc, field }">
      <PersonalizedText
        v-model="doc.message"
        :label="__(field.label)"
        :required="field.required"
        :rows="field.rows || 4"
        :variables="CONTACT_DETAILS"
        :placeholder="__('Hi {0}, thanks for your message!').format('{{first_name}}')"
      />
    </template>

    <template #field-attach="{ doc }">
      <div class="flex flex-col gap-1.5">
        <FormLabel :label="__('Attachment')" />
        <div class="flex items-center gap-2">
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
          <TruncatedText
            class="min-w-0 truncate text-sm text-ink-gray-6"
            :text="doc.attach ? fileName(doc.attach) : __('Optional. Sent with the reply.')"
          />
          <Button v-if="doc.attach" variant="ghost" icon="lucide-x" :label="__('Remove attachment')" @click="doc.attach = ''" />
        </div>
      </div>
    </template>
  </DocFormDialog>

  <ResponsiveDialog v-model:open="tester" :title="__('Test auto replies')" size="md">
    <template #default>
      <div class="flex flex-col gap-3">
        <FormControl
          type="text"
          v-model="sample"
          :placeholder="__('Type a customer message, e.g. what is the price?')"
          @keydown.enter="runTest"
        />
        <div v-if="result !== undefined" class="rounded-5 bg-surface-gray-1 px-3 py-2.5 text-base">
          <p v-if="result" class="text-ink-gray-7">
            <span class="lucide-circle-check mr-1.5 inline-block size-4 align-[-3px] text-ink-green-3" aria-hidden="true" />
            {{ __('Matches') }} <strong class="font-medium text-ink-gray-9">{{ result.rule_name }}</strong> {{ __('on') }}
            <span class="font-mono text-ink-gray-8">"{{ result.keyword }}"</span>
            <span v-if="result.active_when !== 'Always'" class="mt-1 block text-sm text-ink-gray-5">
              {{ __('Only replies {0}.').format(__(result.active_when).toLowerCase()) }}
            </span>
          </p>
          <p v-else class="text-ink-gray-6">{{ __('No enabled auto reply matches this message.') }}</p>
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex w-full justify-end">
        <Button variant="solid" :loading="testing" :disabled="!sample.trim()" :label="__('Check')" @click="runTest" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { ref, watch } from 'vue'
import { Badge, Button, FileUploader, FormControl, FormLabel, Switch, call, toast } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocFormDialog from '@/components/Common/DocFormDialog.vue'
import DocListView from '@/components/Common/DocListView.vue'
import PersonalizedText from '@/components/Common/PersonalizedText.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { useDocList } from '@/composables/useDocList'
import { fileName } from '@/data/inbox'
import { CONTACT_DETAILS } from '@/data/personalization'
import { errorMessage, formatNumber, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({
  compact: { type: Boolean, default: false },
})

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
const MATCHES = ['Contains', 'Exact', 'Starts with']
const WHEN = ['Always', 'During business hours', 'Outside business hours']

const editor = ref(false)
const editing = ref(null)
const toggling = ref(null)
const tester = ref(false)
const sample = ref('')
const result = ref(undefined)
const testing = ref(false)

const defaults = { enabled: 1, match_type: 'Contains', active_when: 'Always', cooldown_minutes: 60, priority: 0 }

const list = useDocList({
  doctype: 'OneChat Auto Reply',
  fields: ['name', 'rule_name', 'keywords', 'match_type', 'active_when', 'enabled', 'reply_count', 'last_replied_at', 'priority'],
  searchFields: ['rule_name', 'keywords', 'message'],
  orderBy: 'priority desc',
  quickFilters: [
    {
      key: 'enabled',
      label: 'Status',
      options: [
        { label: __('Enabled'), value: '1' },
        { label: __('Disabled'), value: '0' },
      ],
      toFilter: (value) => Number(value),
    },
    { key: 'active_when', label: 'Active', options: WHEN.map((value) => ({ label: __(value), value })) },
  ],
  sortOptions: [
    { label: 'Priority', value: 'priority desc' },
    { label: 'Most used', value: 'reply_count desc' },
    { label: 'Recently used', value: 'last_replied_at desc' },
    { label: 'Name', value: 'rule_name asc' },
  ],
})

const columns = [
  { key: 'rule_name', label: 'Auto reply' },
  { key: 'match_type', label: 'Match', width: '120px', hideOnMobile: true, format: (value) => __(value) },
  { key: 'active_when', label: 'Active', width: '200px', hideOnMobile: true, format: (value) => __(value) },
  { key: 'reply_count', label: 'Replies', width: '90px', align: 'right', hideOnMobile: true, format: (value) => formatNumber(value || 0) },
  {
    key: 'last_replied_at',
    label: 'Last used',
    width: '130px',
    hideOnMobile: true,
    format: (value) => (value ? timeAgo(value) : '—'),
  },
  { key: 'enabled', label: 'Enabled', width: '84px', align: 'right', format: (value) => (value ? __('Yes') : __('No')) },
]

const fields = [
  { fieldname: 'rule_name', label: 'Name', type: 'data', required: true, placeholder: 'Pricing question' },
  {
    fieldname: 'keywords',
    label: 'Keywords',
    type: 'textarea',
    rows: 3,
    required: true,
    placeholder: 'price\nhow much\ncost',
    description: 'One per line or comma separated. Case is ignored and whole words are matched.',
  },
  { fieldname: 'match_type', label: 'Match', type: 'select', options: MATCHES, half: true },
  { fieldname: 'active_when', label: 'Active', type: 'select', options: WHEN, half: true },
  { section: 'Reply' },
  { fieldname: 'message', label: 'Message', type: 'textarea', rows: 4, required: true },
  { fieldname: 'attach', label: 'Attachment', type: 'data' },
  { section: 'Advanced' },
  {
    fieldname: 'cooldown_minutes',
    label: 'Cooldown (minutes)',
    type: 'int',
    half: true,
    description: 'Wait before replying to the same contact again. 0 replies every time.',
  },
  {
    fieldname: 'priority',
    label: 'Priority',
    type: 'int',
    half: true,
    description: 'When several match, the highest priority replies.',
  },
  { fieldname: 'enabled', label: 'Enabled', type: 'check', description: 'Turn off to pause this auto reply' },
]

watch(tester, (open) => {
  if (open) result.value = undefined
})
watch(sample, () => (result.value = undefined))

function keywordLine(value) {
  return (value || '').split('\n').filter(Boolean).join(', ')
}

function openRule(name) {
  editing.value = name
  editor.value = true
}

async function runTest() {
  if (!sample.value.trim()) return

  testing.value = true
  try {
    result.value = (await call('onechat.inbox.auto_reply.test', { text: sample.value })) || null
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    testing.value = false
  }
}

async function toggle(row, enabled) {
  toggling.value = row.name
  list.patch(row.name, { enabled: enabled ? 1 : 0 })

  try {
    await call('frappe.client.set_value', {
      doctype: 'OneChat Auto Reply',
      name: row.name,
      fieldname: 'enabled',
      value: enabled ? 1 : 0,
    })
    toast.success(enabled ? __('Auto reply enabled') : __('Auto reply paused'))
  } catch (err) {
    list.patch(row.name, { enabled: enabled ? 0 : 1 })
    toast.error(errorMessage(err))
  } finally {
    toggling.value = null
  }
}
</script>

<template>
  <AppHeader>
    <template #actions>
      <Button variant="solid" icon-left="lucide-plus" :label="__('New rule')" @click="openRule(null)" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search rules')"
      empty-icon="lucide-bell-ring"
      :empty-title="__('No notification rules yet')"
      :empty-description="__('Send a WhatsApp message automatically when a document changes or on a schedule.')"
      export-name="notification-rules"
      importable
      @open="(row) => openRule(row.name)"
    >
      <template #cell-notification_name="{ row }">
        <div class="min-w-0">
          <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.notification_name || row.name" />
          <p class="truncate text-sm text-ink-gray-5 md:hidden">{{ row.reference_doctype }} · {{ triggerLabel(row) }}</p>
        </div>
      </template>

      <template #cell-trigger="{ row }">
        <TruncatedText class="truncate text-base text-ink-gray-7" :text="triggerLabel(row)" />
      </template>

      <template #cell-template="{ row }">
        <TruncatedText v-if="row.send_plain_message" class="truncate text-base text-ink-gray-5" :text="__('Plain message')" />
        <TruncatedText v-else class="truncate text-base text-ink-gray-7" :text="row.template" />
      </template>

      <template #cell-disabled="{ row }">
        <div class="flex justify-end" @click.stop>
          <Switch :model-value="!row.disabled" :disabled="toggling === row.name" @update:model-value="(value) => toggle(row, value)" />
        </div>
      </template>
    </DocListView>
  </div>

  <RuleEditor v-model:open="editor" :name="editing" @saved="list.refresh" @deleted="list.refresh" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { ref } from 'vue'
import { Button, Switch, call, toast } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import RuleEditor from '@/components/Automation/RuleEditor.vue'
import { useDocList } from '@/composables/useDocList'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({
  compact: { type: Boolean, default: false },
})

const editor = ref(false)
const editing = ref(null)
const toggling = ref(null)

const list = useDocList({
  doctype: 'WhatsApp Notification',
  fields: [
    'name',
    'notification_name',
    'reference_doctype',
    'notification_type',
    'doctype_event',
    'event_frequency',
    'days_in_advance',
    'template',
    'send_plain_message',
    'disabled',
    'modified',
  ],
  searchFields: ['notification_name', 'reference_doctype', 'template'],
  quickFilters: [
    {
      key: 'notification_type',
      label: 'Trigger',
      options: [
        { label: __('Document event'), value: 'DocType Event' },
        { label: __('Schedule'), value: 'Scheduler Event' },
      ],
    },
    {
      key: 'disabled',
      label: 'Status',
      options: [
        { label: __('Enabled'), value: '0' },
        { label: __('Disabled'), value: '1' },
      ],
      toFilter: (value) => Number(value),
    },
  ],
  sortOptions: [
    { label: 'Last modified', value: 'modified desc' },
    { label: 'Name', value: 'notification_name asc' },
    { label: 'Document type', value: 'reference_doctype asc' },
  ],
})

const columns = [
  { key: 'notification_name', label: 'Rule' },
  { key: 'reference_doctype', label: 'Document type', hideOnMobile: true },
  { key: 'trigger', label: 'Trigger', hideOnMobile: true, format: (value, row) => triggerLabel(row) },
  {
    key: 'template',
    label: 'Sends',
    hideOnMobile: true,
    format: (value, row) => (row.send_plain_message ? __('Plain message') : value),
  },
  { key: 'disabled', label: 'Enabled', width: '84px', align: 'right', format: (value) => (value ? __('No') : __('Yes')) },
]

function triggerLabel(row) {
  if (row.notification_type === 'Scheduler Event') {
    return row.event_frequency ? __('Scheduled · {0}').format(__(row.event_frequency)) : __('Schedule')
  }
  if (['Days Before', 'Days After'].includes(row.doctype_event)) {
    return __('{0} ({1} days)').format(__(row.doctype_event), row.days_in_advance || 0)
  }

  return row.doctype_event ? __(row.doctype_event) : __('Document event')
}

function openRule(name) {
  editing.value = name
  editor.value = true
}

async function toggle(row, enabled) {
  toggling.value = row.name
  list.patch(row.name, { disabled: enabled ? 0 : 1 })

  try {
    await call('frappe.client.set_value', {
      doctype: 'WhatsApp Notification',
      name: row.name,
      fieldname: 'disabled',
      value: enabled ? 0 : 1,
    })
    toast.success(enabled ? __('Rule enabled') : __('Rule disabled'))
  } catch (err) {
    list.patch(row.name, { disabled: enabled ? 1 : 0 })
    toast.error(errorMessage(err))
  } finally {
    toggling.value = null
  }
}
</script>

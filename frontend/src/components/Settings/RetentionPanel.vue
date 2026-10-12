<template>
  <SettingsHeader>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Data retention') }}</h2>
        <p class="mt-1 text-base text-ink-gray-6">
          {{ __('Delete old conversations and logs automatically to keep your data lean and compliant') }}
        </p>
      </div>
      <Button variant="solid" :label="__('Save')" :loading="saving" :disabled="loading || !dirty || !!problem" @click="save" />
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <div v-if="loading" class="flex flex-col gap-3 pt-6">
      <Skeleton v-for="row in 3" :key="row" class="h-12 w-full" />
    </div>

    <template v-else>
      <div class="divide-y divide-outline-gray-1 pt-6">
        <SettingsRow
          :title="__('Delete old data automatically')"
          :description="__('A cleanup runs once a day. Turn this off to keep everything.')"
        >
          <Switch v-model="form.retention_enabled" />
        </SettingsRow>

        <SettingsRow
          :title="__('Keep messages for')"
          :description="__('Older messages are deleted together with their media. Minimum {0} days.').format(limits.messages)"
        >
          <div class="flex items-center gap-2">
            <FormControl
              v-model="form.message_retention_days"
              class="w-24"
              type="number"
              :min="limits.messages"
              :disabled="!form.retention_enabled"
            />
            <span class="text-base text-ink-gray-6">{{ __('days') }}</span>
          </div>
        </SettingsRow>

        <SettingsRow
          :title="__('Keep media files for')"
          :description="__('Photos, videos, voice notes and documents. The message text stays. Minimum {0} days.').format(limits.media)"
        >
          <div class="flex items-center gap-2">
            <FormControl
              v-model="form.media_retention_days"
              class="w-24"
              type="number"
              :min="limits.media"
              :disabled="!form.retention_enabled"
            />
            <span class="text-base text-ink-gray-6">{{ __('days') }}</span>
          </div>
        </SettingsRow>
      </div>

      <div class="mt-8 flex items-center gap-1">
        <p class="text-sm font-medium text-ink-gray-5">{{ __('Other records') }}</p>
        <InfoHint
          :title="__('Other records')"
          :text="
            __(
              'Logs and history OneChat keeps next to your chats. Leave a row empty to keep those records forever. Contacts, notes, conversations and broadcasts are never deleted.',
            )
          "
        />
      </div>
      <div class="divide-y divide-outline-gray-1">
        <SettingsRow v-for="row in RECORD_ROWS" :key="row.key" :title="__(row.title)" :description="recordDescription(row)">
          <div class="flex items-center gap-2">
            <FormControl
              v-model="form.records[row.key]"
              class="w-24"
              type="number"
              :min="minOf(row.key)"
              :placeholder="__('Keep')"
              :disabled="!form.retention_enabled"
            />
            <span class="text-base text-ink-gray-6">{{ __('days') }}</span>
          </div>
        </SettingsRow>
      </div>

      <p v-if="problem" class="mt-3 text-sm text-ink-red-3">{{ problem }}</p>

      <Alert
        class="mt-6"
        :theme="estimate.messages || estimate.media ? 'amber' : 'gray'"
        :title="estimateTitle"
        :description="__('Files in the Media library, quick replies and templates are never deleted.')"
      />

      <p class="mt-8 text-sm font-medium text-ink-gray-5">{{ __('Cleanup') }}</p>
      <div class="divide-y divide-outline-gray-1">
        <SettingsRow
          :title="__('Last cleanup')"
          :description="estimate.last_run ? `${timeAgo(estimate.last_run)} · ${estimate.last_summary || ''}` : __('Not run yet')"
        >
          <Button
            variant="subtle"
            theme="red"
            icon-left="lucide-trash-2"
            :label="__('Run cleanup now')"
            :disabled="dirty || !form.retention_enabled || !(estimate.messages || estimate.media || recordsDue)"
            @click="runNow"
          />
        </SettingsRow>
      </div>
    </template>
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Alert,
  Button,
  ErrorMessage,
  FormControl,
  SettingsBody,
  SettingsHeader,
  SettingsRow,
  Skeleton,
  Switch,
  call,
  toast,
} from 'frappe-ui'
import InfoHint from '@/components/Common/InfoHint.vue'
import { useUI } from '@/stores/ui'
import { errorMessage, formatNumber, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const SETTINGS = 'OneChat Settings'
const FIELDS = ['retention_enabled', 'message_retention_days', 'media_retention_days', 'retention_records']
const RECORD_ROWS = [
  {
    key: 'notification_logs',
    title: 'Notification send log',
    description: 'A row for every automatic WhatsApp notification sent. Webhook logs are already cleared on their own.',
  },
  {
    key: 'flow_runs',
    title: 'Flow run logs',
    description: 'Step-by-step history of finished flow runs. Runs still going are never deleted.',
  },
  { key: 'flow_sessions', title: 'Finished bot sessions', description: 'Completed, stopped, failed or expired flow sessions.' },
  { key: 'reminders', title: 'Done reminders', description: 'Follow-up reminders that were sent, skipped or cancelled.' },
  {
    key: 'contact_history',
    title: 'Contact change history',
    description: 'Assignments, status and label changes behind the Audit log. Older entries disappear from it.',
  },
]

const ui = useUI()
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saved = ref({})
const form = reactive({
  retention_enabled: false,
  message_retention_days: 365,
  media_retention_days: 90,
  records: Object.fromEntries(RECORD_ROWS.map((row) => [row.key, ''])),
})
const estimate = ref({})
const limits = computed(() => ({ messages: estimate.value.min_message_days || 30, media: estimate.value.min_media_days || 7 }))

const current = computed(() => ({
  retention_enabled: form.retention_enabled ? 1 : 0,
  message_retention_days: Number(form.message_retention_days) || 0,
  media_retention_days: Number(form.media_retention_days) || 0,
  retention_records: JSON.stringify(
    Object.fromEntries(RECORD_ROWS.map((row) => [row.key, Number(form.records[row.key]) || 0]).filter(([, days]) => days > 0)),
  ),
}))

const recordInfo = computed(() => Object.fromEntries((estimate.value.records || []).map((row) => [row.key, row])))
const recordsDue = computed(() => (estimate.value.records || []).reduce((sum, row) => sum + (row.due || 0), 0))

function minOf(key) {
  return recordInfo.value[key]?.min || 7
}

function recordDescription(row) {
  const info = recordInfo.value[row.key]
  const parts = [__(row.description)]
  if (info) parts.push(__('{0} now, minimum {1} days.').format(formatNumber(info.total), info.min))
  return parts.join(' ')
}

const dirty = computed(() => FIELDS.some((field) => current.value[field] !== saved.value[field]))

const problem = computed(() => {
  if (!form.retention_enabled) return ''
  if (current.value.message_retention_days < limits.value.messages)
    return __('Keep messages for at least {0} days.').format(limits.value.messages)
  if (current.value.media_retention_days < limits.value.media)
    return __('Keep media files for at least {0} days.').format(limits.value.media)
  if (current.value.media_retention_days > current.value.message_retention_days)
    return __('Media can’t be kept longer than the messages they belong to.')
  for (const row of RECORD_ROWS) {
    const days = Number(form.records[row.key]) || 0
    if (days > 0 && days < minOf(row.key))
      return __('Keep {0} for at least {1} days, or leave it empty.').format(__(row.title).toLowerCase(), minOf(row.key))
  }

  return ''
})

const estimateTitle = computed(() => {
  if (dirty.value) return __('Save to see what the next cleanup would remove')
  if (!form.retention_enabled) return __('Automatic cleanup is off. Nothing is deleted.')
  if (!estimate.value.messages && !estimate.value.media && !recordsDue.value) return __('Nothing is old enough to delete right now')

  const base = __('The next cleanup removes about {0} messages and {1} media files').format(
    formatNumber(estimate.value.messages),
    formatNumber(estimate.value.media),
  )
  return recordsDue.value ? __('{0}, plus {1} log and history records').format(base, formatNumber(recordsDue.value)) : base
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [doc, preview] = await Promise.all([
      call('frappe.client.get', { doctype: SETTINGS, name: SETTINGS }),
      call('onechat.workspace.retention.preview'),
    ])
    estimate.value = preview
    form.retention_enabled = !!doc.retention_enabled
    form.message_retention_days = doc.message_retention_days || 365
    form.media_retention_days = doc.media_retention_days || 90
    const stored = parseRecords(doc.retention_records)
    for (const row of RECORD_ROWS) form.records[row.key] = stored[row.key] || ''
    saved.value = { ...current.value }
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function parseRecords(value) {
  try {
    const data = value ? JSON.parse(value) : {}
    return data && typeof data === 'object' ? data : {}
  } catch {
    return {}
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    await call('frappe.client.set_value', { doctype: SETTINGS, name: SETTINGS, fieldname: current.value })
    saved.value = { ...current.value }
    estimate.value = await call('onechat.workspace.retention.preview')
    toast.success(__('Retention settings saved'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function runNow() {
  ui.confirm({
    title: __('Delete old data now?'),
    message: __(
      'About {0} messages, {1} media files and {2} log and history records will be permanently deleted. This can’t be undone.',
    ).format(formatNumber(estimate.value.messages), formatNumber(estimate.value.media), formatNumber(recordsDue.value)),
    action: __('Delete now'),
    theme: 'red',
    onConfirm: async () => {
      toast.success(await call('onechat.workspace.retention.run_now'))
    },
  })
}

onMounted(load)
</script>

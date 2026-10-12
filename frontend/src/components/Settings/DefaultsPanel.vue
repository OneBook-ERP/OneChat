<template>
  <SettingsHeader
    :title="__('Defaults')"
    :description="__('Shared settings for every channel')"
  />

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <div v-if="loading" class="flex flex-col gap-3 pt-6">
      <Skeleton v-for="row in 2" :key="row" class="h-12 w-full" />
    </div>

    <div v-else class="divide-y divide-outline-gray-1 pt-6">
      <SettingsRow
        :title="__('Default team')"
        :description="
          __(
            'New conversations join this team when their account does not belong to exactly one team. Auto-assign then picks from its members.',
          )
        "
      >
        <Select
          class="w-56"
          :options="teamOptions"
          :model-value="settings.default_team || ''"
          :disabled="saving === 'default_team'"
          @update:model-value="(value) => update('default_team', value)"
        />
      </SettingsRow>
      <SettingsRow
        :title="__('Duplicate contacts')"
        :description="
          mergeMode === 'Automatic'
            ? __(
                'Contacts with the same phone number merge on their own, every night and when a new contact arrives. Other possible matches wait in Contacts → Duplicates.',
              )
            : __('Possible duplicates wait in Contacts → Duplicates until someone reviews and merges them.')
        "
      >
        <Select
          class="w-56"
          :options="MERGE_MODES"
          :model-value="mergeMode"
          :disabled="saving === 'merge'"
          @update:model-value="changeMergeMode"
        />
      </SettingsRow>
    </div>

    <p v-if="!loading && !teams.length" class="mt-4 text-sm text-ink-gray-5">
      {{ __('Create a team to pick a default team.') }}
      <Button variant="ghost" size="sm" :label="__('Go to teams')" @click="ui.openSettings('teams')" />
    </p>
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Button, ErrorMessage, Select, SettingsBody, SettingsHeader, SettingsRow, Skeleton, call, toast } from 'frappe-ui'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const SETTINGS = 'WhatsApp Settings'

const ui = useUI()

const settings = ref({})
const teams = ref([])
const mergeMode = ref('Manual')
const MERGE_MODES = [
  { label: __('Merge manually'), value: 'Manual' },
  { label: __('Merge automatically'), value: 'Automatic' },
]

async function changeMergeMode(value) {
  if (value === mergeMode.value) return
  saving.value = 'merge'
  error.value = ''
  try {
    mergeMode.value = await call('onechat.inbox.duplicates.set_mode', { mode: value })
    toast.success(
      value === 'Automatic' ? __('Duplicates will merge automatically. Merging existing ones now.') : __('Duplicates will wait for review'),
    )
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = null
  }
}

const teamOptions = computed(() => [
  { label: __('None'), value: '' },
  ...teams.value.map((team) => ({ label: team.team_name || team.name, value: team.name })),
])
const loading = ref(true)
const saving = ref(null)
const error = ref('')

async function load() {
  error.value = ''

  try {
    const [doc, teamRows, merge] = await Promise.all([
      call('frappe.client.get', { doctype: SETTINGS, name: SETTINGS }),
      call('frappe.client.get_list', {
        doctype: 'OneChat Team',
        fields: ['name', 'team_name'],
        order_by: 'team_name asc',
        limit_page_length: 0,
      }),
      call('onechat.inbox.duplicates.get_mode').catch(() => 'Manual'),
    ])
    mergeMode.value = merge || 'Manual'
    settings.value = doc
    teams.value = teamRows
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function update(fieldname, value) {
  const previous = settings.value[fieldname]
  settings.value = { ...settings.value, [fieldname]: value || null }
  saving.value = fieldname
  error.value = ''

  try {
    await call('frappe.client.set_value', { doctype: SETTINGS, name: SETTINGS, fieldname, value: value || '' })
    toast.success(__('Saved'))
  } catch (err) {
    settings.value = { ...settings.value, [fieldname]: previous }
    error.value = errorMessage(err)
  } finally {
    saving.value = null
  }
}

onMounted(load)
</script>

<template>
  <SettingsHeader :title="__('WhatsApp')" :description="__('Which WhatsApp account OneChat uses when nothing else decides')" />

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <div v-if="loading" class="flex flex-col gap-3 pt-6">
      <Skeleton v-for="row in 2" :key="row" class="h-12 w-full" />
    </div>

    <div v-else class="divide-y divide-outline-gray-1 pt-6">
      <SettingsRow :title="__('Default incoming account')" :description="__('Receives messages that do not match a specific account')">
        <Select
          class="w-56"
          :options="options"
          :model-value="settings.default_incoming_account || ''"
          :disabled="saving === 'default_incoming_account'"
          @update:model-value="(value) => update('default_incoming_account', value)"
        />
      </SettingsRow>
      <SettingsRow
        :title="__('Default outgoing account')"
        :description="__('Sends replies, broadcasts and notifications unless one is chosen')"
      >
        <Select
          class="w-56"
          :options="options"
          :model-value="settings.default_outgoing_account || ''"
          :disabled="saving === 'default_outgoing_account'"
          @update:model-value="(value) => update('default_outgoing_account', value)"
        />
      </SettingsRow>
      <SettingsRow
        :title="__('Default country code')"
        :description="__('Added in front of mobile numbers saved without one, such as contacts created through the API')"
      >
        <FormControl
          class="w-56"
          type="text"
          inputmode="numeric"
          placeholder="91"
          :model-value="settings.default_country_code || ''"
          :disabled="saving === 'default_country_code'"
          @change="(event) => update('default_country_code', event.target.value.replace(/\D/g, ''))"
        />
      </SettingsRow>
    </div>

    <p v-if="!loading && !accounts.length" class="mt-4 text-sm text-ink-gray-5">
      {{ __('Add a WhatsApp account first, then pick it here.') }}
      <Button variant="ghost" size="sm" :label="__('Go to accounts')" @click="ui.openSettings('accounts')" />
    </p>
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Button, ErrorMessage, FormControl, Select, SettingsBody, SettingsHeader, SettingsRow, Skeleton, call, toast } from 'frappe-ui'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const SETTINGS = 'WhatsApp Settings'

const ui = useUI()

const settings = ref({})
const accounts = ref([])
const loading = ref(true)
const saving = ref(null)
const error = ref('')

const options = computed(() => [
  { label: __('None'), value: '' },
  ...accounts.value.map((account) => ({
    label:
      account.status === 'Active'
        ? account.account_name || account.name
        : __('{0} (inactive)').format(account.account_name || account.name),
    value: account.name,
  })),
])

async function load() {
  error.value = ''
  try {
    const [doc, rows] = await Promise.all([
      call('frappe.client.get', { doctype: SETTINGS, name: SETTINGS }),
      call('frappe.client.get_list', {
        doctype: 'OneChat Account',
        filters: { channel: ['!=', 'Instagram'] },
        fields: ['name', 'account_name', 'status'],
        order_by: 'account_name asc',
        limit_page_length: 0,
      }),
    ])
    settings.value = doc
    accounts.value = rows
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

<template>
  <AccountEditor v-if="editing" :name="editing === NEW ? null : editing" @back="editing = null" @saved="done" @deleted="done" />

  <template v-else>
    <SettingsHeader
      :title="__('Accounts')"
      :description="__('The WhatsApp numbers and Instagram accounts OneChat sends and receives through')"
    >
      <template #actions>
        <Button variant="solid" icon-left="lucide-plus" :label="__('New account')" data-tour="new-account" @click="editing = NEW" />
      </template>
    </SettingsHeader>

    <SettingsBody>
      <ErrorMessage :message="error" class="pt-4" />

      <ListSkeleton v-if="loading" class="pt-4" :rows="3" :avatar="false" />

      <List
        v-else-if="accounts.length"
        class="-mx-3 pt-4"
        :columns="{ base: ['minmax(0,1fr)', '9.5rem'], md: ['minmax(0,1fr)', '10rem', '11rem'] }"
        :row-height="56"
      >
        <ListHeader>
          <ListHeaderCell>{{ __('Account') }}</ListHeaderCell>
          <ListHeaderCell>{{ __('Status') }}</ListHeaderCell>
          <ListHeaderCell class="max-md:hidden">{{ __('Default for') }}</ListHeaderCell>
        </ListHeader>
        <ListRows :items="accounts" v-slot="{ item }">
          <ListRow data-tour="account-row" @click="editing = item.name">
            <ListCell>
              <div class="flex min-w-0 items-center gap-2.5">
                <ChannelIcon :channel="item.channel" show-whatsapp class="size-5 shrink-0" />
                <div class="min-w-0">
                  <div class="flex min-w-0 items-center gap-1.5">
                    <TruncatedText as="div" class="truncate text-base text-ink-gray-8" :text="item.account_name || item.name" />
                    <Badge v-if="item.channel === 'Instagram'" theme="amber" variant="subtle" size="sm" :label="__('Beta')" />
                  </div>
                  <TruncatedText as="div" class="mt-0.5 truncate text-sm text-ink-gray-5" :text="subtitle(item)" />
                </div>
              </div>
            </ListCell>
            <ListCell>
              <Tooltip :text="item.account_alert || item.connection_message || ''">
                <Badge variant="subtle" :theme="badge(item).theme" :label="__(badge(item).label)" />
              </Tooltip>
            </ListCell>
            <ListCell class="max-md:hidden">
              <div class="flex flex-wrap gap-1">
                <Badge v-if="item.is_default_incoming" theme="blue" variant="outline" :label="__('Incoming')" />
                <Badge v-if="item.is_default_outgoing" theme="blue" variant="outline" :label="__('Outgoing')" />
                <span v-if="!item.is_default_incoming && !item.is_default_outgoing" class="text-sm text-ink-gray-4">—</span>
              </div>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>

      <EmptyState
        v-else
        class="mt-6"
        icon="lucide-smartphone"
        :title="__('No accounts yet')"
        :description="__('Connect a WhatsApp Business number or an Instagram professional account from Meta to start messaging.')"
      >
        <Button icon-left="lucide-plus" :label="__('New account')" data-tour="new-account" @click="editing = NEW" />
      </EmptyState>
    </SettingsBody>
  </template>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { onMounted, ref } from 'vue'
import { Badge, Button, ErrorMessage, SettingsBody, SettingsHeader, Tooltip, call } from 'frappe-ui'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from 'frappe-ui/list'
import AccountEditor from './AccountEditor.vue'
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import ListSkeleton from '@/components/Common/ListSkeleton.vue'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const NEW = '__new__'

function badge(item) {
  if (item.status === 'Inactive') return { theme: 'gray', label: 'Inactive' }
  if (item.account_alert && item.account_alert_level === 'Critical') return { theme: 'red', label: 'Action needed' }
  if (item.account_alert && item.account_alert_level === 'Warning') return { theme: 'amber', label: 'Warning' }
  if (item.connection_status === 'Error') return { theme: 'red', label: 'Connection problem' }
  if (item.connection_status === 'Connected') return { theme: 'green', label: 'Connected' }

  return { theme: 'green', label: 'Active' }
}

function subtitle(item) {
  if (item.channel === 'Instagram') return item.ig_username ? `Instagram · @${item.ig_username}` : __('Instagram · not connected yet')
  return item.display_phone_number || (item.phone_id ? __('Phone ID {0}').format(item.phone_id) : __('No phone ID'))
}

const accounts = ref([])
const loading = ref(true)
const error = ref('')
const editing = ref(null)

async function load() {
  error.value = ''

  try {
    accounts.value = await call('frappe.client.get_list', {
      doctype: 'OneChat Account',
      fields: [
        'name',
        'account_name',
        'channel',
        'ig_username',
        'phone_id',
        'display_phone_number',
        'status',
        'connection_status',
        'connection_message',
        'account_alert',
        'account_alert_level',
        'is_default_incoming',
        'is_default_outgoing',
      ],
      order_by: 'account_name asc',
      limit_page_length: 0,
    })
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function done() {
  editing.value = null
  load()
}

onMounted(load)
</script>

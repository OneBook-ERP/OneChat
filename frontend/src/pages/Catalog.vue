<template>
  <AppHeader>
    <template #actions>
      <Select v-if="erpnext && accounts.length > 1" class="w-56" :options="accountOptions" v-model="account" />
      <Button
        v-if="erpnext && account"
        variant="ghost"
        icon="lucide-rotate-cw"
        :label="__('Refresh')"
        :tooltip="__('Refresh')"
        :loading="manager?.loading"
        @click="manager?.load()"
      />
    </template>
  </AppHeader>

  <ScrollArea class="min-h-0 flex-1">
    <div class="mx-auto flex w-full max-w-[1100px] flex-col gap-5 px-3 pb-10 pt-5 sm:px-5">
      <ErrorMessage :message="error" />
      <EmptyState
        v-if="!erpnext"
        icon="lucide-plug"
        :title="__('Turn on the ERPNext integration')"
        :description="__('The catalog is available when ERPNext is connected in Settings → Integrations.')"
      />
      <EmptyState
        v-else-if="loaded && !accounts.length"
        icon="lucide-smartphone"
        :title="__('No WhatsApp numbers yet')"
        :description="__('Add a WhatsApp number with its Business Account ID in Settings to manage its catalog.')"
      />
      <CatalogManager v-else-if="account" ref="manager" :account="account" />
    </div>
  </ScrollArea>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button, ErrorMessage, ScrollArea, Select, call } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import CatalogManager from '@/components/Campaigns/CatalogManager.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import { activeIntegrations } from '@/data/integrations'
import { useNumbers } from '@/stores/numbers'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const route = useRoute()
const numbers = useNumbers()
const accounts = ref([])
const account = ref('')
const loaded = ref(false)
const error = ref('')
const manager = ref(null)
const erpnext = computed(() => activeIntegrations.value.some((row) => row.name === 'erpnext'))

const accountOptions = computed(() => accounts.value.map((row) => ({ label: row.account_name || row.name, value: row.name })))

onMounted(async () => {
  try {
    if (!numbers.loaded) await numbers.load()
    const rows = await call('frappe.client.get_list', {
      doctype: 'OneChat Account',
      fields: ['name', 'account_name'],
      filters: { business_id: ['is', 'set'], status: 'Active' },
      order_by: 'account_name asc',
      limit_page_length: 0,
    })
    accounts.value = rows.filter((row) => !numbers.isHidden(row.name))
    const wanted = route.query.account
    account.value = accounts.value.find((row) => row.name === wanted)?.name || accounts.value[0]?.name || ''
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loaded.value = true
  }
})
watch(
  () => route.query.account,
  (wanted) => {
    if (wanted && accounts.value.some((row) => row.name === wanted)) account.value = wanted
  },
)
</script>

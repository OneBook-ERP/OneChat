<template>
  <ResponsiveDialog v-model:open="open" :title="__('Import from Meta')" size="2xl">
    <template #default>
      <div class="flex flex-col gap-4">
        <p class="text-sm text-ink-gray-5">
          {{ __('Pick a WhatsApp account to see the forms already built in Meta’s WhatsApp Manager.') }}
        </p>

        <div class="flex items-end gap-2">
          <LinkField
            v-model="account"
            class="min-w-0 flex-1"
            doctype="OneChat Account"
            :filters="{ channel: ['!=', 'Instagram'] }"
            :label="__('WhatsApp account')"
          />
          <Button
            variant="subtle"
            icon-left="lucide-refresh-cw"
            :loading="loading"
            :disabled="!account"
            :label="__('Load forms')"
            @click="load"
          />
        </div>

        <ErrorMessage :message="error" />

        <div v-if="loading && !flows.length" class="flex flex-col gap-2">
          <Skeleton v-for="row in 4" :key="row" class="h-10 w-full" />
        </div>

        <p v-else-if="loaded && !flows.length" class="rounded-4 bg-surface-gray-1 px-3 py-6 text-center text-sm text-ink-gray-5">
          {{ __('This account has no forms on Meta yet.') }}
        </p>

        <div v-else-if="flows.length" class="overflow-hidden rounded-4 border border-outline-gray-1">
          <ScrollArea viewport-class="max-h-80">
            <div
              v-for="flow in flows"
              :key="flow.id"
              class="flex items-center gap-3 border-b border-outline-gray-1 px-3 py-2 last:border-b-0"
            >
              <div class="min-w-0 flex-1">
                <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="flow.name" />
                <TruncatedText
                  as="p"
                  class="truncate text-sm text-ink-gray-5"
                  :text="(flow.categories || []).map(categoryLabel).join(', ') || flow.id"
                />
              </div>
              <FormStatusBadge :status="titleCase(flow.status)" size="sm" />
              <Button
                v-if="flow.exists_locally"
                size="sm"
                variant="ghost"
                icon-right="lucide-arrow-right"
                :label="__('Open')"
                @click="openForm(flow.local_name)"
              />
              <Button
                v-else
                size="sm"
                variant="subtle"
                :loading="importing === flow.id"
                :disabled="!!importing"
                :label="__('Import')"
                @click="importOne(flow)"
              />
            </div>
          </ScrollArea>
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <Button
          variant="ghost"
          icon-left="lucide-download"
          :loading="importing === '*'"
          :disabled="!account || !!importing || !flows.some((flow) => !flow.exists_locally)"
          :label="__('Import all')"
          @click="importAll"
        />
        <Button variant="subtle" :label="__('Close')" @click="open = false" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, ErrorMessage, ScrollArea, Skeleton, call, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import LinkField from '@/components/Common/LinkField.vue'
import FormStatusBadge from './FormStatusBadge.vue'
import { categoryLabel } from './formSchema'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const MODULE = 'onechat.onechat.doctype.whatsapp_flow.whatsapp_flow'

const emit = defineEmits(['imported'])

const open = defineModel('open', { type: Boolean, default: false })

const router = useRouter()
const account = ref(null)
const flows = ref([])
const loading = ref(false)
const loaded = ref(false)
const importing = ref('')
const error = ref('')

function titleCase(value) {
  const text = String(value || '').toLowerCase()

  return text ? text.charAt(0).toUpperCase() + text.slice(1) : ''
}

async function load() {
  if (!account.value) return

  loading.value = true
  error.value = ''
  try {
    flows.value = (await call(`${MODULE}.get_whatsapp_flows`, { whatsapp_account: account.value })) || []
    loaded.value = true
  } catch (err) {
    flows.value = []
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function importOne(flow) {
  importing.value = flow.id
  try {
    const name = await call(`${MODULE}.import_flow_from_whatsapp`, {
      whatsapp_account: account.value,
      flow_id: flow.id,
      flow_name: flow.name,
    })
    toast.success(__('Imported {0}').format(flow.name))
    emit('imported')
    flows.value = flows.value.map((item) => (item.id === flow.id ? { ...item, exists_locally: true, local_name: name } : item))
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    importing.value = ''
  }
}

async function importAll() {
  importing.value = '*'
  try {
    const result = await call(`${MODULE}.sync_all_flows`, { whatsapp_account: account.value })
    toast.success(__('{0} imported, {1} updated, {2} skipped').format(result?.imported || 0, result?.updated || 0, result?.skipped || 0))
    emit('imported')
    await load()
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    importing.value = ''
  }
}

function openForm(name) {
  open.value = false
  router.push({ name: 'FormBuilder', params: { name } })
}

watch(account, () => {
  flows.value = []
  loaded.value = false
  error.value = ''
  if (account.value) load()
})
</script>

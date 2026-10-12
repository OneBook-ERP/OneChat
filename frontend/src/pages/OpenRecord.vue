<template>
  <div class="flex h-full items-center justify-center p-6">
    <div class="flex w-full max-w-md flex-col gap-4">
      <div v-if="loading" class="flex items-center justify-center gap-2 text-sm text-ink-gray-5">
        <Spinner class="size-4" />
        {{ __('Opening the chat…') }}
      </div>

      <EmptyState v-else-if="error" icon="lucide-message-circle-off" :title="__('Could not open the chat')" :description="error">
        <Button variant="subtle" :label="__('Go to inbox')" :route="{ name: 'Inbox' }" />
      </EmptyState>

      <template v-else-if="rows.length > 1">
        <div>
          <h1 class="text-lg font-semibold text-ink-gray-9">{{ __('Pick a chat') }}</h1>
          <p class="mt-0.5 text-sm text-ink-gray-5">
            {{ __('{0} {1} is linked to {2} chats.').format(__(doctype), name, rows.length) }}
          </p>
        </div>
        <div class="flex flex-col divide-y divide-outline-gray-1 rounded-5 border border-outline-gray-2">
          <router-link
            v-for="row in rows"
            :key="row.name"
            :to="{ name: 'Inbox', params: { contact: row.name } }"
            class="flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-surface-gray-1"
          >
            <Avatar :label="row.contact_name || row.mobile_no" size="lg" />
            <div class="min-w-0 flex-1">
              <TruncatedText as="p" class="truncate text-sm font-medium text-ink-gray-9" :text="row.contact_name || row.mobile_no" />
              <TruncatedText
                as="p"
                class="truncate text-xs text-ink-gray-5"
                :text="[row.mobile_no, row.last_message].filter(Boolean).join(' · ')"
              />
            </div>
            <span v-if="row.main" class="inline-flex shrink-0 items-center gap-0.5 text-xs font-medium text-ink-amber-7">
              <span class="lucide-star size-3" aria-hidden="true" />{{ __('Main') }}
            </span>
            <span class="lucide-chevron-right size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
          </router-link>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Avatar, Button, Spinner } from 'frappe-ui'
import EmptyState from '@/components/Common/EmptyState.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { recordChats } from '@/data/integrations'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const route = useRoute()
const router = useRouter()

const doctype = String(route.query.doctype || '')
const name = String(route.query.name || '')
const rows = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  if (!doctype || !name) {
    error.value = __('The link is missing the record type or name.')
    loading.value = false
    return
  }
  try {
    rows.value = await recordChats(doctype, name)
    if (rows.value.length === 1) {
      router.replace({ name: 'Inbox', params: { contact: rows.value[0].name } })
      return
    }
  } catch (err) {
    error.value = errorMessage(err)
  }
  loading.value = false
})
</script>

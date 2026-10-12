<template>
  <AppHeader>
    <template #actions>
      <Button variant="solid" icon-left="lucide-plus" :label="__('New link')" data-tour="new-chat-link" @click="openEditor(null)" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search links')"
      empty-icon="lucide-qr-code"
      :empty-title="__('No links yet')"
      :empty-description="
        __('Create a click-to-chat link or QR code for posters, ads and your website, and see how many conversations it starts.')
      "
      export-name="whatsapp-chat-links"
      @open="(row) => openEditor(row.name)"
    >
      <template #cell-title="{ row }">
        <div class="min-w-0">
          <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.title" />
          <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="row.short_url || row.link_url || __('No number yet')" />
        </div>
      </template>

      <template #cell-ref_code="{ value }">
        <code class="text-sm text-ink-gray-7">{{ value }}</code>
      </template>

      <template #cell-conversations="{ value }">
        <span class="inline-flex items-center gap-1.5 text-base text-ink-gray-7">
          <span class="lucide-message-circle size-3.5 text-ink-gray-5" aria-hidden="true" />
          {{ formatNumber(value || 0) }}
        </span>
      </template>
    </DocListView>
  </div>

  <ChatLinkEditor v-model:open="editorOpen" :name="editing" @saved="list.refresh" @deleted="list.refresh" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { ref } from 'vue'
import { Button } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import ChatLinkEditor from '@/components/Campaigns/ChatLinkEditor.vue'
import { useDocList } from '@/composables/useDocList'
import { formatDate, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const editorOpen = ref(false)
const editing = ref(null)

const list = useDocList({
  doctype: 'OneChat Chat Link',
  fields: ['name', 'title', 'display_number', 'ref_code', 'clicks', 'conversations', 'link_url', 'short_url', 'creation'],
  searchFields: ['title', 'ref_code', 'prefilled_message', 'display_number'],
  orderBy: 'creation desc',
  sortOptions: [
    { label: 'Newest first', value: 'creation desc' },
    { label: 'Most conversations', value: 'conversations desc' },
    { label: 'Title', value: 'title asc' },
  ],
})

const columns = [
  { key: 'title', label: 'Title', width: 'minmax(0,2fr)' },
  { key: 'display_number', label: 'Number', hideOnMobile: true },
  { key: 'ref_code', label: 'Ref code', width: '110px', hideOnMobile: true },
  { key: 'clicks', label: 'Clicks', width: '90px', align: 'right', hideOnMobile: true },
  { key: 'conversations', label: 'Conversations', width: '130px', align: 'right' },
  { key: 'creation', label: 'Created', width: '120px', hideOnMobile: true, format: formatDate },
]

function openEditor(name) {
  editing.value = name
  editorOpen.value = true
}
</script>

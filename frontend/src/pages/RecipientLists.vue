<template>
  <AppHeader>
    <template #actions>
      <Button variant="solid" icon-left="lucide-plus" :label="__('New list')" @click="openEditor(null)" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search lists')"
      empty-icon="lucide-list-checks"
      :empty-title="__('No recipient lists yet')"
      :empty-description="__('Group numbers once and reuse them across broadcasts.')"
      export-name="recipient-lists"
      @open="(row) => openEditor(row.name)"
    >
      <template #cell-list_name="{ row }">
        <div class="min-w-0">
          <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.list_name || row.name" />
          <TruncatedText as="p" v-if="row.description" class="truncate text-sm text-ink-gray-5 md:hidden" :text="row.description" />
        </div>
      </template>

      <template #cell-count="{ row }">
        <span class="inline-flex items-center gap-1.5 text-base text-ink-gray-7">
          <span class="lucide-users size-3.5 text-ink-gray-5" aria-hidden="true" />
          {{ row.name in counts ? formatNumber(counts[row.name]) : '…' }}
        </span>
      </template>
    </DocListView>
  </div>

  <RecipientListEditor v-model:open="editorOpen" :name="editing" @saved="refresh" @deleted="refresh" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { reactive, ref, watch } from 'vue'
import { Button, call } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import RecipientListEditor from '@/components/Campaigns/RecipientListEditor.vue'
import { useDocList } from '@/composables/useDocList'
import { formatNumber, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const editorOpen = ref(false)
const editing = ref(null)
const counts = reactive({})

const list = useDocList({
  doctype: 'WhatsApp Recipient List',
  fields: ['name', 'list_name', 'description', 'doctype_to_import', 'modified'],
  searchFields: ['list_name', 'description'],
  sortOptions: [
    { label: 'Recently updated', value: 'modified desc' },
    { label: 'Name', value: 'list_name asc' },
  ],
})

const columns = [
  { key: 'list_name', label: 'Name', width: 'minmax(0,2fr)' },
  { key: 'description', label: 'Description', width: 'minmax(0,2fr)', hideOnMobile: true },
  { key: 'count', label: 'Recipients', width: '120px', format: (value, row) => counts[row.name] ?? '' },
  { key: 'doctype_to_import', label: 'Source', hideOnMobile: true, format: (value) => (value ? __(value) : __('Manual')) },
  { key: 'modified', label: 'Updated', width: '120px', hideOnMobile: true, format: timeAgo },
]

async function loadCounts(names) {
  if (!names.length) return

  const data = await call('onechat.campaigns.broadcasts.recipient_counts', { names }).catch(() => ({}))
  for (const name of names) counts[name] = data[name] || 0
}

watch(list.rows, (rows) => loadCounts(rows.map((row) => row.name).filter((name) => !(name in counts))))

function refresh() {
  for (const name of Object.keys(counts)) delete counts[name]
  list.refresh()
}

function openEditor(name) {
  editing.value = name
  editorOpen.value = true
}
</script>

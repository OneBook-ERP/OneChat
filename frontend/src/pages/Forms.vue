<template>
  <AppHeader>
    <template #actions>
      <Button
        variant="subtle"
        icon-left="lucide-download"
        :label="compact ? __('Import') : __('Import from Meta')"
        @click="importOpen = true"
      />
      <Button variant="solid" icon-left="lucide-plus" :label="__('New form')" @click="openForm('new')" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search forms')"
      empty-icon="lucide-clipboard-list"
      :empty-title="__('No forms yet')"
      :empty-description="__('Forms open inside WhatsApp so customers can book, sign up or answer a survey without leaving the chat.')"
      export-name="whatsapp-forms"
      :deletable="false"
      @open="(row) => openForm(row.name)"
    >
      <template #cell-flow_name="{ row }">
        <div class="min-w-0">
          <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.flow_name || row.name" />
          <TruncatedText as="p" v-if="row.description" class="truncate text-sm text-ink-gray-5" :text="row.description" />
        </div>
      </template>

      <template #cell-status="{ value }">
        <FormStatusBadge :status="value" />
      </template>

      <template #cell-responses="{ row }">
        <span class="text-base tabular-nums text-ink-gray-7">
          {{ counts[row.name] === undefined ? '—' : formatNumber(counts[row.name]) }}
        </span>
      </template>
    </DocListView>
  </div>

  <ImportDialog v-model:open="importOpen" @imported="list.refresh" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, call } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import FormStatusBadge from '@/components/Forms/FormStatusBadge.vue'
import ImportDialog from '@/components/Forms/ImportDialog.vue'
import { CATEGORIES, categoryLabel } from '@/components/Forms/formSchema'
import { useDocList } from '@/composables/useDocList'
import { formatNumber, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const router = useRouter()
const importOpen = ref(false)
const counts = ref({})

const list = useDocList({
  doctype: 'WhatsApp Flow',
  fields: ['name', 'flow_name', 'description', 'category', 'status', 'whatsapp_account', 'flow_id', 'modified'],
  searchFields: ['flow_name', 'description', 'flow_id'],
  quickFilters: [
    {
      key: 'status',
      label: 'Status',
      options: ['Draft', 'Published', 'Deprecated', 'Blocked', 'Throttled'].map((value) => ({ label: __(value), value })),
    },
    {
      key: 'category',
      label: 'Category',
      options: CATEGORIES.map((value) => ({ label: categoryLabel(value), value })),
    },
  ],
  sortOptions: [
    { label: 'Recently updated', value: 'modified desc' },
    { label: 'Name', value: 'flow_name asc' },
    { label: 'Status', value: 'status asc' },
  ],
})

const columns = [
  { key: 'flow_name', label: 'Name', width: 'minmax(0,2fr)' },
  { key: 'category', label: 'Category', hideOnMobile: true, format: categoryLabel },
  { key: 'status', label: 'Status', width: '120px' },
  { key: 'whatsapp_account', label: 'Account', hideOnMobile: true },
  { key: 'responses', label: 'Responses', width: '100px', align: 'right', hideOnMobile: true },
  { key: 'modified', label: 'Updated', width: '120px', hideOnMobile: true, format: timeAgo },
]

function openForm(name) {
  router.push({ name: 'FormBuilder', params: { name } })
}

watch(
  () => list.rows.value,
  async (rows) => {
    const names = rows.map((row) => row.name)
    if (!names.length) return

    try {
      const result = await call('onechat.campaigns.forms.response_counts', { names })
      counts.value = { ...counts.value, ...Object.fromEntries(names.map((name) => [name, result?.[name] || 0])) }
    } catch {
      return
    }
  },
)
</script>

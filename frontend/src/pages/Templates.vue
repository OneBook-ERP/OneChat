<template>
  <AppHeader>
    <template #actions>
      <Button
        variant="subtle"
        icon-left="lucide-refresh-cw"
        :loading="syncing"
        :label="compact ? __('Sync') : __('Sync from Meta')"
        data-tour="sync-templates"
        @click="sync"
      />
      <Button variant="solid" icon-left="lucide-plus" :label="__('New template')" data-tour="new-template" @click="openEditor(null)" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <TemplateGrid v-if="view === 'grid'" :list="list" @open="(row) => openEditor(row.name)">
      <template #toolbar>
        <TabButtons v-model="view" :options="views" />
      </template>
    </TemplateGrid>

    <DocListView
      v-else
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search templates')"
      empty-icon="lucide-layout-template"
      :empty-title="__('No templates yet')"
      :empty-description="__('Templates are pre-approved messages you can send outside the 24 hour window.')"
      export-name="whatsapp-templates"
      :deletable="false"
      @open="(row) => openEditor(row.name)"
    >
      <template #toolbar>
        <TabButtons v-model="view" :options="views" />
      </template>

      <template #cell-template_name="{ row }">
        <div class="min-w-0">
          <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.template_name" />
          <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="row.actual_name" />
        </div>
      </template>

      <template #cell-status="{ value }">
        <CampaignStatusBadge :status="value" />
      </template>

      <template #cell-quality_score="{ value }">
        <QualityDot :score="value" />
      </template>

      <template #cell-read_rate="{ row }">
        <span class="text-base text-ink-gray-7">{{ readRate(row.name) }}</span>
      </template>
    </DocListView>
  </div>

  <TemplateEditor v-model:open="editorOpen" :name="editing" @saved="refresh" @deleted="refresh" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { reactive, ref, watch } from 'vue'
import { Button, TabButtons, call, toast } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import QualityDot, { qualityLabel } from '@/components/Campaigns/TemplateQualityDot.vue'
import CampaignStatusBadge from '@/components/Campaigns/CampaignStatusBadge.vue'
import TemplateEditor from '@/components/Campaigns/TemplateEditor.vue'
import TemplateGrid from '@/components/Campaigns/TemplateGrid.vue'
import { useDocList } from '@/composables/useDocList'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const VIEW_KEY = 'onechat.templates.view'

const rates = reactive({})
const editorOpen = ref(false)
const editing = ref(null)
const syncing = ref(false)
const view = ref(readView())

const views = [
  { label: __('List'), value: 'list', iconLeft: 'lucide-list' },
  { label: __('Grid'), value: 'grid', iconLeft: 'lucide-layout-grid' },
]

const categoryLabel = (value) => (value ? __(value.charAt(0) + value.slice(1).toLowerCase()) : '')

const list = useDocList({
  doctype: 'WhatsApp Templates',
  fields: [
    'name',
    'template_name',
    'actual_name',
    'category',
    'language',
    'language_code',
    'status',
    'header_type',
    'header',
    'template',
    'sample_values',
    'quality_score',
    'modified',
  ],
  searchFields: ['template_name', 'actual_name', 'template'],
  quickFilters: [
    {
      key: 'status',
      label: 'Status',
      options: ['APPROVED', 'PENDING', 'REJECTED', 'PAUSED', 'DISABLED'].map((value) => ({
        label: __(value.charAt(0) + value.slice(1).toLowerCase()),
        value,
      })),
    },
    {
      key: 'category',
      label: 'Category',
      options: ['MARKETING', 'UTILITY', 'AUTHENTICATION', 'TRANSACTIONAL', 'OTP'].map((value) => ({
        label: categoryLabel(value),
        value,
      })),
    },
  ],
  sortOptions: [
    { label: 'Recently updated', value: 'modified desc' },
    { label: 'Name', value: 'template_name asc' },
    { label: 'Status', value: 'status asc' },
  ],
})

const columns = [
  { key: 'template_name', label: 'Name', width: 'minmax(0,2fr)' },
  { key: 'category', label: 'Category', hideOnMobile: true, format: categoryLabel },
  { key: 'language_code', label: 'Language', width: '100px', hideOnMobile: true },
  { key: 'status', label: 'Status', width: '120px' },
  { key: 'quality_score', label: 'Quality', width: '90px', hideOnMobile: true, format: (value) => __(qualityLabel(value)) },
  { key: 'read_rate', label: 'Read (30d)', width: '100px', align: 'right', hideOnMobile: true, format: (value, row) => readRate(row.name) },
  { key: 'modified', label: 'Updated', width: '120px', hideOnMobile: true, format: timeAgo },
]

function readRate(name) {
  if (!(name in rates)) return '…'
  const row = rates[name]

  return row?.sent ? `${Math.round(row.read_rate)}%` : '—'
}

async function loadRates(names) {
  if (!names.length) return

  const data = await call('onechat.campaigns.template_stats.summary', { templates: names, days: 30 }).catch(() => ({}))
  for (const name of names) rates[name] = data[name] || null
}

watch(list.rows, (rows) => loadRates(rows.map((row) => row.name).filter((name) => !(name in rates))))

function refresh() {
  for (const name of Object.keys(rates)) delete rates[name]
  list.refresh()
}

function readView() {
  try {
    return localStorage.getItem(VIEW_KEY) === 'grid' ? 'grid' : 'list'
  } catch {
    return 'list'
  }
}

watch(view, (value) => {
  try {
    localStorage.setItem(VIEW_KEY, value)
  } catch {
    return
  }
})

function openEditor(name) {
  editing.value = name
  editorOpen.value = true
}

async function sync() {
  syncing.value = true
  try {
    const message = await call('onechat.onechat.doctype.whatsapp_templates.whatsapp_templates.fetch')
    toast.success(message ? __(message) : __('Templates synced'))
    refresh()
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    syncing.value = false
  }
}
</script>

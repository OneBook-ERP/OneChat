<template>
  <AppHeader>
    <template #actions>
      <Button variant="solid" icon-left="lucide-plus" :label="__('New flow')" data-tour="new-flow" @click="gallery = true" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search flows')"
      empty-icon="lucide-git-fork"
      :empty-title="__('No flows yet')"
      :empty-description="
        __(
          'Build chatbots and automations for WhatsApp and Instagram: welcome menus, questions, lead capture, order lookups and reminders.',
        )
      "
      export-name="automation-flows"
      importable
      @open="(row) => openFlow(row.name)"
    >
      <template #cell-flow_name="{ row }">
        <div class="flex min-w-0 items-center gap-3">
          <span
            class="flex size-8 shrink-0 items-center justify-center rounded-4"
            :class="(TRIGGER_STYLES[row.trigger_type] || TRIGGER_STYLES.Manual).tile"
          >
            <span :class="(TRIGGER_STYLES[row.trigger_type] || TRIGGER_STYLES.Manual).icon" class="size-4" aria-hidden="true" />
          </span>
          <div class="min-w-0">
            <div class="flex min-w-0 items-center gap-1.5">
              <TruncatedText as="p" class="truncate text-base font-medium text-ink-gray-9" :text="row.flow_name || row.name" />
              <span
                class="size-1.5 shrink-0 rounded-full"
                :class="row.is_active ? 'bg-surface-green-6' : 'bg-surface-gray-4'"
                :title="row.is_active ? __('Active') : __('Inactive')"
              />
            </div>
            <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="row.description || __('No description')" />
          </div>
        </div>
      </template>

      <template #cell-trigger_type="{ row }">
        <Badge v-if="row.trigger_type" :label="__(triggerLabel(row.trigger_type))" :theme="TRIGGER_THEMES[row.trigger_type] || 'gray'" />
        <span v-else class="text-base text-ink-gray-4">{{ __('None') }}</span>
      </template>

      <template #cell-last_run="{ row }">
        <div v-if="lastRuns[row.name]" class="flex min-w-0 items-center gap-2">
          <RunStatusBadge :status="lastRuns[row.name].status" />
          <TruncatedText class="truncate text-sm text-ink-gray-5" :text="timeAgo(lastRuns[row.name].start_time)" />
        </div>
        <span v-else class="text-base text-ink-gray-4">{{ __('Never') }}</span>
      </template>

      <template #cell-is_active="{ row }">
        <div class="flex justify-end" @click.stop>
          <Switch :model-value="!!row.is_active" :disabled="toggling === row.name" @update:model-value="(value) => toggle(row, value)" />
        </div>
      </template>

      <template #cell-actions="{ row }">
        <div class="flex justify-end" @click.stop>
          <Dropdown :options="rowMenu(row)" align="end">
            <Button variant="ghost" icon="lucide-ellipsis" :label="__('Actions')" />
          </Dropdown>
        </div>
      </template>
    </DocListView>
  </div>

  <RecipeGallery v-model:open="gallery" @pick="create" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, Dropdown, Switch, call, toast } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import RunStatusBadge from '@/components/Automation/RunStatusBadge.vue'
import RecipeGallery from '@/components/FlowBuilder/RecipeGallery.vue'
import { FLOW_CATEGORIES, FLOW_TRIGGER_TYPES, triggerLabel } from '@/components/FlowBuilder/nodeTypes'
import { useDocList } from '@/composables/useDocList'
import { useUI } from '@/stores/ui'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({
  compact: { type: Boolean, default: false },
})

const TRIGGER_STYLES = {
  'WhatsApp Incoming': { icon: 'lucide-message-circle', tile: 'bg-surface-green-2 text-ink-green-7' },
  'ERPNext Document Event': { icon: 'lucide-file-text', tile: 'bg-surface-blue-2 text-ink-blue-7' },
  Scheduled: { icon: 'lucide-calendar-clock', tile: 'bg-surface-amber-2 text-ink-amber-7' },
  Manual: { icon: 'lucide-hand', tile: 'bg-surface-gray-2 text-ink-gray-7' },
  Webhook: { icon: 'lucide-webhook', tile: 'bg-surface-gray-2 text-ink-gray-7' },
}

const TRIGGER_THEMES = {
  'WhatsApp Incoming': 'green',
  'ERPNext Document Event': 'blue',
  Scheduled: 'amber',
  Manual: 'gray',
  Webhook: 'gray',
}

const router = useRouter()
const ui = useUI()
const toggling = ref(null)
const lastRuns = ref({})
const gallery = ref(false)

const list = useDocList({
  doctype: 'Automation Flow',
  fields: ['name', 'flow_name', 'description', 'trigger_type', 'category', 'is_active', 'modified'],
  searchFields: ['flow_name', 'description'],
  quickFilters: [
    {
      key: 'trigger_type',
      label: 'Trigger',
      options: FLOW_TRIGGER_TYPES.map((value) => ({ label: __(triggerLabel(value)), value })),
    },
    {
      key: 'category',
      label: 'Category',
      options: FLOW_CATEGORIES.map((value) => ({ label: __(value), value })),
    },
    {
      key: 'is_active',
      label: 'Status',
      options: [
        { label: __('Active'), value: '1' },
        { label: __('Inactive'), value: '0' },
      ],
      toFilter: (value) => Number(value),
    },
  ],
  sortOptions: [
    { label: 'Last modified', value: 'modified desc' },
    { label: 'Name', value: 'flow_name asc' },
    { label: 'Trigger', value: 'trigger_type asc' },
  ],
})

const columns = [
  { key: 'flow_name', label: 'Flow', width: 3 },
  { key: 'trigger_type', label: 'Trigger', width: '170px', hideOnMobile: true },
  { key: 'category', label: 'Category', width: '150px', hideOnMobile: true, format: (value) => (value ? __(value) : '') },
  {
    key: 'last_run',
    label: 'Last run',
    width: '170px',
    hideOnMobile: true,
    format: (value, row) => lastRuns.value[row.name]?.status || '',
  },
  { key: 'modified', label: 'Modified', width: '120px', hideOnMobile: true, format: (value) => timeAgo(value) },
  { key: 'is_active', label: 'Active', width: '72px', align: 'right', format: (value) => (value ? __('Yes') : __('No')) },
  { key: 'actions', label: '', width: '48px', align: 'right', format: () => '' },
]

watch(
  () => list.rows.value.map((row) => row.name).join('|'),
  async () => {
    const names = list.rows.value.map((row) => row.name)
    if (!names.length) return

    try {
      const logs = await call('frappe.client.get_list', {
        doctype: 'Automation Execution Log',
        fields: ['flow', 'status', 'start_time'],
        filters: { flow: ['in', names] },
        order_by: 'start_time desc',
        limit_page_length: 500,
      })
      const out = { ...lastRuns.value }
      for (const log of logs) {
        if (!out[log.flow] || out[log.flow].start_time < log.start_time) out[log.flow] = log
      }
      lastRuns.value = out
    } catch {
      lastRuns.value = { ...lastRuns.value }
    }
  },
)

function openFlow(name) {
  router.push({ name: 'FlowBuilder', params: { name } })
}

async function create(recipe) {
  if (!recipe) {
    openFlow('new')
    return
  }

  const graph = recipe.build()
  for (let attempt = 1; attempt <= 5; attempt++) {
    const name = attempt === 1 ? __(recipe.title) : `${__(recipe.title)} ${attempt}`
    try {
      const saved = await call('onechat.automation.flows.save_flow', {
        flow_name: null,
        flow_data: {
          flow_name: name,
          description: __(recipe.description),
          category: recipe.category,
          trigger_type: graph.trigger_type,
          is_active: 0,
          graph_json: JSON.stringify({ nodes: graph.nodes, edges: graph.edges }, null, 2),
        },
      })
      toast.success(__('Created from the {0} recipe. Edit it, try it in Test chat, then switch it on.').format(__(recipe.title)))
      openFlow(saved.name)
      return
    } catch (err) {
      if (!/exist|duplicate/i.test(errorMessage(err)) || attempt === 5) {
        toast.error(errorMessage(err))
        return
      }
    }
  }
}

function rowMenu(row) {
  return [
    { label: __('Open'), icon: 'lucide-square-pen', onClick: () => openFlow(row.name) },
    { label: __('Duplicate'), icon: 'lucide-copy', onClick: () => duplicate(row) },
    {
      label: __('View runs'),
      icon: 'lucide-scroll-text',
      onClick: () => router.push({ name: 'ExecutionLogs', query: { flow: row.name } }),
    },
    { label: __('Delete'), icon: 'lucide-trash-2', onClick: () => remove(row) },
  ]
}

async function toggle(row, active) {
  toggling.value = row.name
  list.patch(row.name, { is_active: active ? 1 : 0 })

  try {
    await call('frappe.client.set_value', {
      doctype: 'Automation Flow',
      name: row.name,
      fieldname: 'is_active',
      value: active ? 1 : 0,
    })
    toast.success(active ? __('Flow activated') : __('Flow paused'))
  } catch (err) {
    list.patch(row.name, { is_active: active ? 0 : 1 })
    toast.error(errorMessage(err))
  } finally {
    toggling.value = null
  }
}

async function duplicate(row) {
  try {
    const flow = await call('frappe.client.get', { doctype: 'Automation Flow', name: row.name })
    const saved = await call('onechat.automation.flows.save_flow', {
      flow_name: null,
      flow_data: {
        flow_name: __('{0} (copy)').format(flow.flow_name || flow.name),
        description: flow.description,
        trigger_type: flow.trigger_type,
        category: flow.category,
        graph_json: flow.graph_json,
        is_active: 0,
      },
    })
    toast.success(__('Flow duplicated'))
    list.refresh()
    openFlow(saved.name)
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

function remove(row) {
  ui.confirm({
    title: __('Delete {0}?').format(row.flow_name || row.name),
    message: __('The flow stops running, and its canvas and run history are removed. This cannot be undone.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('onechat.automation.flows.delete_flow', { flow_name: row.name })
      list.refresh()
      toast.success(__('Flow deleted'))
    },
  })
}
</script>

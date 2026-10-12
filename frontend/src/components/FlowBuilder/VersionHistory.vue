<template>
  <ResponsiveDialog v-model:open="open" :title="__('Version history')" size="md">
    <template #default>
      <p class="mb-3 text-sm text-ink-gray-6">
        {{ __('Every publish is kept here. Restoring a version puts it in your draft, so you can check it before publishing again.') }}
      </p>
      <ErrorMessage :message="error" class="mb-2" />
      <div v-if="loading" class="flex flex-col gap-2">
        <Skeleton v-for="row in 3" :key="row" class="h-12 w-full" />
      </div>
      <p v-else-if="!rows.length" class="py-6 text-center text-sm text-ink-gray-5">
        {{ __('No published versions yet. Publish this flow to start its history.') }}
      </p>
      <div v-else class="divide-y divide-outline-gray-1 rounded border border-outline-gray-1">
        <div v-for="row in rows" :key="row.name" class="flex items-center gap-3 px-3 py-2.5">
          <div class="min-w-0 flex-1">
            <p class="flex items-center gap-2 text-base font-medium text-ink-gray-8">
              {{ __('Version {0}').format(row.version) }}
              <Badge v-if="row.version === current" theme="green" variant="subtle" size="sm" :label="__('Live')" />
            </p>
            <p class="truncate text-sm text-ink-gray-5">
              {{ timeAgo(row.creation) }}<template v-if="row.published_by"> · {{ agentName(row.published_by) }}</template>
              <template v-if="row.note"> · {{ row.note }}</template>
            </p>
          </div>
          <Button
            v-if="row.version !== current"
            size="sm"
            variant="subtle"
            :label="__('Restore')"
            :loading="restoring === row.name"
            @click="restore(row)"
          />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Badge, Button, ErrorMessage, Skeleton, call, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { agentName, agents } from '@/data/inbox'
import { useUI } from '@/stores/ui'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  flow: { type: String, default: null },
  current: { type: Number, default: 0 },
  unsaved: { type: Boolean, default: false },
})

const emit = defineEmits(['restored'])
const open = defineModel('open', { type: Boolean, default: false })

const ui = useUI()
const rows = ref([])
const loading = ref(false)
const error = ref('')
const restoring = ref(null)

async function load() {
  if (!props.flow) return
  if (!agents.data) agents.fetch()
  loading.value = true
  error.value = ''
  try {
    rows.value = await call('onechat.automation.flows.versions', { flow_name: props.flow })
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function restore(row) {
  if (!props.unsaved) return apply(row)
  ui.confirm({
    title: __('Replace your changes?'),
    message: __('Restoring version {0} replaces your draft and any unsaved edits.').format(row.version),
    action: __('Restore'),
    theme: 'red',
    onConfirm: () => apply(row),
  })
}

async function apply(row) {
  restoring.value = row.name
  try {
    const flow = await call('onechat.automation.flows.restore_version', { flow_name: props.flow, version: row.name })
    toast.success(
      flow.draft
        ? __('Version {0} is in your draft. Publish to make it live.').format(row.version)
        : __('Version {0} restored').format(row.version),
    )
    open.value = false
    emit('restored')
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    restoring.value = null
  }
}

watch(open, (value) => value && load())
</script>

<template>
  <SettingsHeader :title="__('Integrations')" :description="__('Connect conversations to the other apps on this site')" />

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <div v-if="integrations.loading && !rows.length" class="grid grid-cols-1 gap-3 pt-6 sm:grid-cols-2">
      <Skeleton v-for="row in 2" :key="row" class="h-36 w-full rounded-6" />
    </div>

    <template v-else>
      <div class="grid grid-cols-1 gap-3 pt-6 sm:grid-cols-2" data-tour="integrations">
        <IntegrationCard
          v-for="row in visible"
          :key="row.name"
          :row="row"
          :busy="saving === row.name"
          @connect="connect(row)"
          @disconnect="disconnect(row)"
          @details="details = row.name"
          @setup="setup = row.name"
        />
      </div>

      <p v-if="!visible.length" class="pt-6 text-sm text-ink-gray-5">{{ __('No integrations are registered.') }}</p>

      <p class="mt-6 flex items-center gap-1.5 text-xs text-ink-gray-5">
        <span class="lucide-code-xml size-3.5 shrink-0" aria-hidden="true" />
        {{ __('Building your own Frappe app? Register it in hooks.py under onechat_integrations and it shows up here.') }}
      </p>
    </template>

    <IntegrationDetails
      v-model:open="detailsOpen"
      :row="selected"
      :busy="saving === selected?.name"
      @connect="connect(selected)"
      @disconnect="disconnect(selected)"
      @setup="openSetup(selected)"
    />

    <ResponsiveDialog
      :open="setupOpen && !!PANELS[setupRow?.setup]"
      :title="setupRow?.label || ''"
      size="2xl"
      @update:open="(value) => !value && (setup = '')"
    >
      <template #default>
        <component :is="PANELS[setupRow.setup]" v-if="setupRow && PANELS[setupRow.setup]" dialog @saved="setup = ''" />
      </template>
    </ResponsiveDialog>

    <ConnectionSetup
      v-model:open="connectionOpen"
      :integration="setupRow?.setup || ''"
      :label="setupRow?.label || ''"
      :enabled="!!setupRow?.enabled && !!setupRow?.installed"
      @disconnect="disconnectSetup"
    />
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ErrorMessage, SettingsBody, SettingsHeader, Skeleton, toast } from 'frappe-ui'
import AssistantSettingsPanel from './AssistantSettingsPanel.vue'
import ConnectionSetup from './ConnectionSetup.vue'
import PaymentsPanel from './PaymentsPanel.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import IntegrationCard from './IntegrationCard.vue'
import IntegrationDetails from './IntegrationDetails.vue'
import { integrations, setIntegration } from '@/data/integrations'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const ui = useUI()

const saving = ref('')
const error = ref('')
const details = ref('')
const setup = ref('')

const rows = computed(() => integrations.data?.integrations || [])
const selected = computed(() => rows.value.find((row) => row.name === details.value) || null)

const setupRow = computed(() => rows.value.find((row) => row.name === setup.value) || null)

const PANELS = { assistant: AssistantSettingsPanel, payments: PaymentsPanel }

const setupOpen = computed({
  get: () => !!setup.value,
  set: (value) => {
    if (!value) setup.value = ''
  },
})

const connectionOpen = computed({
  get: () => setupOpen.value && !PANELS[setupRow.value?.setup],
  set: (value) => {
    if (!value) setup.value = ''
  },
})

function openSetup(row) {
  details.value = ''
  setup.value = row?.name || ''
}

function disconnectSetup() {
  const row = setupRow.value
  setup.value = ''
  disconnect(row)
}

const detailsOpen = computed({
  get: () => !!details.value,
  set: (value) => {
    if (!value) details.value = ''
  },
})

const visible = computed(() =>
  [...rows.value].sort((a, b) => Number(b.enabled && b.installed) - Number(a.enabled && a.installed) || a.label.localeCompare(b.label)),
)

async function save(key, work, message) {
  saving.value = key
  error.value = ''
  try {
    await work()
    toast.success(message)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = ''
  }
}

function connect(row) {
  if (!row) return
  return save(row.name, () => setIntegration(row.name, true), __('{0} connected').format(row.label))
}

function disconnect(row) {
  if (!row) return
  ui.confirm({
    title: __('Disconnect {0}?').format(row.label),
    message: __(
      'Its panels and actions disappear from the inbox. Existing links on contacts are kept and come back if you connect it again.',
    ),
    action: __('Disconnect'),
    theme: 'red',
    onConfirm: () => save(row.name, () => setIntegration(row.name, false), __('{0} disconnected').format(row.label)),
  })
}

onMounted(() => integrations.reload())
</script>

<template>
  <SettingsHeader>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Labels') }}</h2>
        <p class="mt-1 text-base text-ink-gray-6">
          {{ __('Tag conversations so the team can group and find them from the inbox sidebar') }}
        </p>
      </div>
      <Button
        variant="solid"
        icon-left="lucide-plus"
        :label="__('Add label')"
        data-tour="new-label"
        :disabled="!!draft && !draft.name"
        @click="edit(null)"
      />
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <ListSkeleton v-if="!loaded" class="pt-4" :rows="4" />

    <div
      v-else-if="rows.length || draft"
      class="mt-4 divide-y divide-outline-gray-1 overflow-hidden rounded-4 border border-outline-gray-2"
    >
      <LabelForm
        v-if="draft && !draft.name"
        v-model:label="draft"
        :saving="saving"
        :error="formError"
        @save="save"
        @cancel="draft = null"
      />

      <template v-for="row in rows" :key="row.name">
        <LabelForm
          v-if="draft?.name === row.name"
          v-model:label="draft"
          :saving="saving"
          :error="formError"
          @save="save"
          @cancel="draft = null"
        />

        <div v-else class="flex items-center gap-3 px-3 py-2.5">
          <span class="size-2.5 shrink-0 rounded-full" :class="LABEL_DOTS[row.color] || LABEL_DOTS.gray" aria-hidden="true" />
          <div class="min-w-0 flex-1">
            <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.label_name || row.name" />
            <TruncatedText as="p" v-if="row.description" class="mt-0.5 truncate text-sm text-ink-gray-5" :text="row.description" />
          </div>
          <span class="hidden shrink-0 text-sm tabular-nums text-ink-gray-5 sm:inline">
            {{ usage(row.count) }}
          </span>
          <Button variant="ghost" icon="lucide-pencil" :label="__('Edit')" :tooltip="__('Edit')" @click="edit(row)" />
          <Button variant="ghost" icon="lucide-trash-2" :label="__('Delete')" :tooltip="__('Delete')" @click="remove(row)" />
        </div>
      </template>
    </div>

    <EmptyState
      v-else
      class="mt-6"
      icon="lucide-tags"
      :title="__('No labels yet')"
      :description="__('Labels like VIP, Refund or Follow-up help your team group conversations.')"
    />
  </SettingsBody>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { onMounted, ref } from 'vue'
import { Button, ErrorMessage, SettingsBody, SettingsHeader, call, toast } from 'frappe-ui'
import EmptyState from '@/components/Common/EmptyState.vue'
import ListSkeleton from '@/components/Common/ListSkeleton.vue'
import LabelForm from '@/components/Labels/LabelForm.vue'
import { LABEL_DOTS, labels } from '@/data/inbox'
import { useUI } from '@/stores/ui'
import { countLabel, errorMessage, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const METHOD = 'onechat.inbox.conversations.'

const ui = useUI()
const rows = ref([])
const loaded = ref(false)
const error = ref('')
const draft = ref(null)
const saving = ref(false)
const formError = ref('')

function usage(count) {
  if (!count) return __('Not used yet')
  return count === 1 ? __('1 conversation') : __('{0} conversations').format(countLabel(count))
}

async function reload() {
  error.value = ''

  try {
    rows.value = await call(`${METHOD}labels`, { with_counts: 1 })
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loaded.value = true
  }
}

function edit(row) {
  formError.value = ''
  draft.value = row
    ? {
        name: row.name,
        label_name: row.label_name || row.name,
        color: row.color || 'gray',
        description: row.description || '',
      }
    : { name: null, label_name: '', color: 'gray', description: '' }
}

async function save() {
  const values = draft.value
  if (!values?.label_name.trim() || saving.value) return

  saving.value = true
  formError.value = ''

  try {
    await call(`${METHOD}save_label`, {
      name: values.name,
      label_name: values.label_name.trim(),
      color: values.color,
      description: values.description.trim() || null,
    })
    toast.success(values.name ? __('Label saved') : __('Label added'))
    draft.value = null
    await reload()
    labels.reload()
  } catch (err) {
    formError.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function remove(row) {
  const count = row.count || 0
  const impact = !count
    ? __('No conversation uses it yet.')
    : count === 1
    ? __('It will be removed from 1 conversation.')
    : __('It will be removed from {0} conversations.').format(formatNumber(count))

  ui.confirm({
    title: __('Delete the label {0}?').format(row.label_name || row.name),
    message: `${impact} ${__('This cannot be undone.')}`,
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call(`${METHOD}delete_label`, { name: row.name })
      toast.success(__('Label deleted'))
      if (draft.value?.name === row.name) draft.value = null
      await reload()
      labels.reload()
    },
  })
}

onMounted(reload)
</script>

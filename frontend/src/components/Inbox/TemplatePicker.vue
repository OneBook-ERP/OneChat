<template>
  <ResponsiveDialog v-model:open="open" :title="__('Send a template')" size="3xl">
    <template #default>
      <div class="flex flex-col gap-4 md:min-h-[26rem] md:flex-row">
        <div class="flex shrink-0 flex-col gap-2 md:w-64">
          <Select
            v-if="accountOptions.length > 1"
            :model-value="account"
            :options="accountOptions"
            :placeholder="__('Send from')"
            @update:model-value="pickAccount"
          />
          <FormControl v-model="query" type="search" :placeholder="__('Search templates')">
            <template #prefix>
              <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
            </template>
          </FormControl>

          <ScrollArea class="-mx-1" viewport-class="max-h-44 px-1 md:max-h-[26rem]">
            <div class="flex flex-col gap-0.5" role="listbox">
              <div v-if="templates.loading && !rows.length" class="flex flex-col gap-2 py-1">
                <Skeleton v-for="index in 5" :key="index" class="h-11 w-full rounded-4" />
              </div>

              <p v-else-if="!rows.length" class="px-2 py-6 text-center text-sm text-ink-gray-5">
                {{ query ? __('No approved template matches your search.') : __('There are no approved templates yet.') }}
              </p>

              <button
                v-for="row in rows"
                :key="row.name"
                type="button"
                role="option"
                :aria-selected="selected?.name === row.name"
                class="rounded-4 px-2.5 py-2 text-left transition-colors"
                :class="selected?.name === row.name ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
                @click="choose(row)"
              >
                <TruncatedText class="block truncate text-base font-medium text-ink-gray-8" :text="row.template_name || row.actual_name" />
                <TruncatedText
                  class="mt-0.5 block truncate text-xs text-ink-gray-5"
                  :text="[row.category, row.language_code].filter(Boolean).join(' · ').toLowerCase()"
                />
              </button>
            </div>
          </ScrollArea>
        </div>

        <div v-if="selected" class="flex min-w-0 flex-1 flex-col gap-4">
          <div class="rounded-5 bg-surface-gray-1 p-4">
            <div class="max-w-sm rounded-5 rounded-tr-1 bg-surface-green-2 px-2.5 py-2 shadow-sm md:ml-auto">
              <p v-if="selected.header" class="pb-1 text-base font-semibold text-ink-gray-9">{{ selected.header }}</p>
              <p
                class="whitespace-pre-wrap break-words text-base leading-relaxed text-ink-gray-9 [overflow-wrap:anywhere]"
                v-html="preview"
              />
              <p v-if="selected.footer" class="pt-1 text-xs text-ink-gray-5">{{ selected.footer }}</p>
            </div>
          </div>

          <div v-if="values.length" class="flex flex-col gap-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="flex items-center gap-1.5 text-sm font-medium text-ink-gray-7">
                {{ __('Variables') }}
                <Spinner v-if="filling" class="size-3.5" />
              </p>
              <Select
                v-if="documents.length"
                class="w-full sm:w-64"
                :model-value="documentKey"
                :options="documentOptions"
                :placeholder="__('Fill from…')"
                @update:model-value="pickDocument"
              />
            </div>
            <div class="grid gap-x-3 gap-y-2.5 sm:grid-cols-2">
              <div v-for="(value, index) in values" :key="index" class="flex min-w-0 flex-col gap-1">
                <div class="flex items-center justify-between gap-2">
                  <label :for="`template-var-${index}`" class="truncate text-xs text-ink-gray-5">
                    <span class="font-mono" v-text="token(index)" />
                    <span v-if="meta[index]?.label"> · {{ meta[index].label }}</span>
                  </label>
                  <Dropdown v-if="suggestions.length" :options="insertOptions(index)" placement="right">
                    <Button size="sm" variant="ghost" icon="lucide-list-plus" :tooltip="__('Insert a value')" />
                  </Dropdown>
                </div>
                <TextInput
                  :id="`template-var-${index}`"
                  v-model="values[index]"
                  type="text"
                  :placeholder="samples[index] || __('Value for {0}').format(token(index))"
                  @input="edited.add(index)"
                />
                <TruncatedText v-if="meta[index]?.source" class="truncate text-xs text-ink-gray-5" :text="meta[index].source" />
              </div>
            </div>
          </div>
          <p v-else class="text-sm text-ink-gray-5">{{ __('This template has no variables.') }}</p>
        </div>

        <div v-else class="hidden flex-1 items-center justify-center rounded-5 bg-surface-gray-1 md:flex">
          <p class="flex items-center gap-2 text-sm text-ink-gray-5">
            <span class="lucide-layout-template size-4" aria-hidden="true" />
            {{ __('Pick a template to preview it') }}
          </p>
        </div>
      </div>

      <ErrorMessage :message="error" class="mt-3" />
    </template>

    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button
          variant="solid"
          icon-left="lucide-send-horizontal"
          :label="__('Send template')"
          :disabled="!ready"
          :loading="sending"
          @click="send"
        />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import {
  Button,
  Dropdown,
  ErrorMessage,
  FormControl,
  ScrollArea,
  Select,
  Skeleton,
  Spinner,
  TextInput,
  call,
  createResource,
  debounce,
} from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { richText, sendTemplate } from '@/data/inbox'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contact: { type: String, required: true },
})

const emit = defineEmits(['sent'])

const open = defineModel('open', { type: Boolean, default: false })

const query = ref('')
const selected = ref(null)
const values = ref([])
const samples = ref([])
const meta = ref([])
const documents = ref([])
const documentKey = ref('')
const suggestions = ref([])
const filling = ref(false)
const edited = new Set()
let fillTicket = 0
const sending = ref(false)
const error = ref('')

const account = ref('')
const accountRows = ref([])

const templates = createResource({
  url: 'onechat.inbox.conversations.templates',
  makeParams: () => ({ search: query.value || null, account: account.value || null }),
})

const accountOptions = computed(() =>
  accountRows.value.map((row) => ({ label: row.phone ? `${row.label} · ${row.phone}` : row.label, value: row.name })),
)

async function loadAccounts() {
  try {
    const result = await call('onechat.inbox.accounts.choices', { contact: props.contact })
    accountRows.value = result.accounts || []
    account.value = result.selected || ''
  } catch (err) {
    accountRows.value = []
    account.value = ''
    error.value = errorMessage(err)
  }
}

function pickAccount(value) {
  if (value === account.value) return
  account.value = value
  selected.value = null
  templates.reload()
}

const rows = computed(() => (templates.data || []).filter((row) => String(row.status || '').toUpperCase() === 'APPROVED'))

const ready = computed(() => !!selected.value && values.value.every((value) => String(value || '').trim()))

const preview = computed(() => {
  const text = String(selected.value?.template || '').replace(/{{\s*(\d+)\s*}}/g, (match, index) => {
    const value = values.value[Number(index) - 1]
    return String(value || '').trim() || match
  })

  return richText(text)
})

const search = debounce(() => templates.reload(), 300)

watch(query, search)

watch(open, async (value) => {
  if (!value) return

  error.value = ''
  await loadAccounts()
  templates.fetch()
})

function token(index) {
  return `{{${index + 1}}}`
}

function variableCount(text) {
  const indexes = [...String(text || '').matchAll(/{{\s*(\d+)\s*}}/g)].map((match) => Number(match[1]))
  return indexes.length ? Math.max(...indexes) : 0
}

const documentOptions = computed(() =>
  documents.value.map((row) => ({ label: row.hint ? `${row.label} · ${row.hint}` : row.label, value: `${row.doctype}::${row.name}` })),
)

function insertOptions(index) {
  return suggestions.value.map((row) => ({
    label: `${row.label}: ${row.value}`,
    onClick: () => {
      values.value[index] = row.value
      meta.value[index] = { ...(meta.value[index] || {}), source: row.source }
      edited.add(index)
    },
  }))
}

async function loadFill(doctype, name) {
  if (!selected.value) return
  const ticket = ++fillTicket
  filling.value = true
  try {
    const result = await call('onechat.inbox.template_fill.fill', {
      contact: props.contact,
      template: selected.value.name,
      doctype: doctype || undefined,
      name: name || undefined,
    })
    if (ticket !== fillTicket) return
    documents.value = result.documents || []
    documentKey.value = result.document ? `${result.document.doctype}::${result.document.name}` : ''
    suggestions.value = result.suggestions || []
    ;(result.values || []).forEach((row, index) => {
      if (index >= values.value.length) return
      meta.value[index] = { label: row.label, source: edited.has(index) ? meta.value[index]?.source : row.source }
      if (!edited.has(index) && row.value) values.value[index] = row.value
    })
  } catch (err) {
    if (ticket === fillTicket) error.value = errorMessage(err)
  } finally {
    if (ticket === fillTicket) filling.value = false
  }
}

function pickDocument(key) {
  const [doctype, name] = String(key || '').split('::')
  documentKey.value = key
  loadFill(doctype, name)
}

function choose(row) {
  selected.value = row
  error.value = ''
  edited.clear()

  const count = variableCount(row.template)
  samples.value = String(row.sample_values || '')
    .split(',')
    .map((value) => value.trim())
  values.value = Array.from({ length: count }, () => '')
  meta.value = Array.from({ length: count }, () => ({}))
  documents.value = []
  suggestions.value = []
  documentKey.value = ''
  if (count) loadFill()
}

async function send() {
  if (!ready.value) return

  sending.value = true
  error.value = ''

  try {
    await sendTemplate(
      props.contact,
      selected.value.name,
      values.value.map((value) => String(value).trim()),
      account.value,
    )
    emit('sent')
    open.value = false
    selected.value = null
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    sending.value = false
  }
}
</script>

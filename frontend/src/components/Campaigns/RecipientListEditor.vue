<template>
  <ResponsiveDialog v-model:open="open" :title="name ? __('Edit recipient list') : __('New recipient list')" size="3xl">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-3">
        <Skeleton v-for="row in 5" :key="row" class="h-9 w-full" />
      </div>

      <div v-else class="flex flex-col gap-6">
        <section class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormControl
            v-model="doc.list_name"
            type="text"
            :label="__('List name')"
            :required="true"
            :disabled="!!name"
            :placeholder="__('Diwali offer customers')"
          />
          <FormControl v-model="doc.description" type="text" :label="__('Description')" />
        </section>

        <section class="flex flex-col gap-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h3 class="text-base font-semibold text-ink-gray-8">
              {{ __('Recipients') }}
              <span class="ml-1 font-normal text-ink-gray-5">{{ formatNumber(doc.recipients.length) }}</span>
            </h3>
            <div class="flex items-center gap-1">
              <FileUploader :file-types="FILE_TYPES" :validate-file="checkFile" @success="readUploaded" @failure="uploadFailed">
                <template #default="{ openFileSelector, uploading, progress }">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon-left="lucide-file-up"
                    :label="uploading ? __('Uploading {0}%').format(progress) : __('Upload file')"
                    :loading="uploading || upload.loading"
                    @click="openFileSelector"
                  />
                </template>
              </FileUploader>
              <Button
                variant="ghost"
                size="sm"
                icon-left="lucide-clipboard-paste"
                :label="__('Paste numbers')"
                @click="pasting = !pasting"
              />
              <Button variant="ghost" size="sm" icon-left="lucide-plus" :label="__('Add row')" @click="addRow" />
              <Button
                v-if="doc.recipients.length"
                variant="ghost"
                size="sm"
                theme="red"
                icon-left="lucide-eraser"
                :label="__('Clear')"
                @click="doc.recipients = []"
              />
            </div>
          </div>

          <FormControl
            v-if="doc.recipients.length > PAGE_SIZES[0]"
            v-model="query"
            type="text"
            size="sm"
            :placeholder="__('Search number or name')"
          >
            <template #prefix>
              <span class="lucide-search size-3.5 text-ink-gray-5" aria-hidden="true" />
            </template>
          </FormControl>

          <div v-if="upload.headers.length" class="flex flex-col gap-3 rounded-4 bg-surface-gray-1 p-3">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <TruncatedText as="p" class="truncate text-sm font-medium text-ink-gray-8" :text="upload.filename" />
                <p class="text-sm text-ink-gray-5">
                  {{ __('{0} rows, {1} columns').format(formatNumber(upload.total), upload.headers.length) }}
                  <template v-if="upload.truncated">
                    · {{ __('only the first {0} are read').format(formatNumber(upload.rows.length)) }}</template
                  >
                </p>
              </div>
              <Button variant="ghost" size="sm" icon="lucide-x" :label="__('Close')" @click="resetUpload" />
            </div>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FormControl v-model="upload.mobile" type="select" :label="__('Mobile number column')" :options="columnOptions" />
              <FormControl
                v-model="upload.name"
                type="select"
                :label="__('Name column')"
                :options="[{ label: __('No name column'), value: '' }, ...columnOptions]"
              />
            </div>

            <p class="text-sm text-ink-gray-6">
              <template v-if="extraColumns.length">
                {{ __('Saved with each recipient for template variables:') }}
                <span class="font-medium text-ink-gray-8">{{ extraColumns.map((column) => column.key).join(', ') }}</span>
              </template>
              <template v-else>{{ __('No other columns to save.') }}</template>
            </p>

            <div v-if="upload.mobile" class="overflow-hidden rounded-3 border border-outline-gray-1 bg-surface-base">
              <ScrollArea orientation="horizontal" viewport-class="pb-1">
                <table class="w-full text-left text-sm">
                  <thead class="bg-surface-gray-1 text-ink-gray-5">
                    <tr>
                      <th v-for="header in upload.headers" :key="header" class="whitespace-nowrap px-2 py-1.5 font-normal">{{ header }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(line, index) in upload.rows.slice(0, 3)" :key="index" class="border-t border-outline-gray-1">
                      <td
                        v-for="(value, column) in line"
                        :key="column"
                        class="max-w-48 truncate whitespace-nowrap px-2 py-1.5 text-ink-gray-8"
                      >
                        {{ value }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </ScrollArea>
            </div>

            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm text-ink-gray-5">
                {{ __('{0} ready to add').format(formatNumber(uploaded.rows.length)) }}
                <template v-if="uploaded.duplicates">
                  · {{ __('{0} duplicates skipped').format(formatNumber(uploaded.duplicates)) }}</template
                >
                <template v-if="uploaded.invalid">
                  · {{ __('{0} without a valid number skipped').format(formatNumber(uploaded.invalid)) }}</template
                >
              </p>
              <Button
                variant="solid"
                size="sm"
                :label="__('Add {0}').format(formatNumber(uploaded.rows.length))"
                :disabled="!uploaded.rows.length"
                @click="addUploaded"
              />
            </div>
          </div>

          <div v-if="pasting" class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-3">
            <Textarea
              v-model="pasted"
              :rows="5"
              :placeholder="__('One per line: number, name (optional)') + '\n+919876543210, Asha\n+971501234567'"
            />
            <div class="flex items-center justify-between gap-2">
              <p class="text-sm text-ink-gray-5">{{ __('Duplicates and blank lines are skipped.') }}</p>
              <Button
                variant="solid"
                size="sm"
                :label="__('Add {0}').format(parsed.length)"
                :disabled="!parsed.length"
                @click="addPasted"
              />
            </div>
          </div>

          <div v-if="doc.recipients.length" class="overflow-hidden rounded-4 border border-outline-gray-1">
            <div
              class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_32px] gap-2 border-b border-outline-gray-1 bg-surface-gray-1 px-2 py-1.5 text-sm text-ink-gray-5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_32px]"
            >
              <span>{{ __('Mobile number') }}</span>
              <span>{{ __('Name') }}</span>
              <span class="max-sm:hidden">{{ __('Data') }}</span>
              <span />
            </div>
            <ScrollArea viewport-class="max-h-80">
              <div
                v-for="row in visibleRows"
                :key="row.name || row.key"
                class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_32px] items-center gap-2 px-2 py-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_32px]"
              >
                <PhoneField v-model="row.mobile_number" />
                <FormControl type="text" v-model="row.recipient_name" size="sm" />
                <TruncatedText
                  class="truncate text-sm text-ink-gray-5 max-sm:hidden"
                  :text="dataKeys(row.recipient_data)"
                  :tip="row.recipient_data"
                />
                <Button variant="ghost" size="sm" icon="lucide-x" :label="__('Remove')" @click="removeRow(row)" />
              </div>
              <p v-if="!filtered.length" class="px-2 py-4 text-center text-sm text-ink-gray-5">{{ __('No recipients match.') }}</p>
            </ScrollArea>
            <Pagination v-if="filtered.length > PAGE_SIZES[0]" v-model:page="page" :total="filtered.length" inline class="px-2 pb-2" />
          </div>
          <p v-else class="text-sm text-ink-gray-5">
            {{ __('Add numbers by hand, paste them, upload a CSV or Excel file, or import them from records below.') }}
          </p>
        </section>

        <section class="flex flex-col gap-3 rounded-5 border border-outline-gray-1 p-3">
          <div>
            <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Import from records') }}</h3>
            <p class="mt-0.5 text-sm text-ink-gray-5">
              {{ __('Pull numbers from any document type in your apps. Importing replaces the recipients above.') }}
            </p>
          </div>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <LinkField v-model="doc.doctype_to_import" doctype="DocType" :label="__('Document type')" :filters="{ istable: 0 }" />
            <FormControl v-model="doc.import_limit" type="number" :label="__('Limit')" :placeholder="__('No limit')" />
            <FormControl
              v-model="doc.mobile_field"
              type="select"
              :label="__('Mobile field')"
              :options="fieldOptions"
              :disabled="!fieldOptions.length"
            />
            <FormControl
              v-model="doc.name_field"
              type="select"
              :label="__('Name field')"
              :options="[{ label: '—', value: '' }, ...fieldOptions]"
              :disabled="!fieldOptions.length"
            />
            <FormControl
              v-model="dataFields"
              class="sm:col-span-2"
              type="text"
              :label="__('Data fields')"
              :description="__('Comma separated fieldnames saved with each recipient to fill template variables')"
              :placeholder="
                fieldOptions
                  .slice(1, 4)
                  .map((option) => option.value)
                  .join(', ')
              "
            />
            <div class="flex flex-col gap-1.5 sm:col-span-2">
              <FormLabel :label="__('Filters')" />
              <RecordFilters
                v-model="filterRows"
                :fields="fields"
                :empty-text="
                  doc.doctype_to_import
                    ? __('No filters. Every {0} with a mobile number is imported.').format(__(doc.doctype_to_import))
                    : __('Pick a document type to add filters.')
                "
              />
            </div>
          </div>
          <div class="flex justify-end">
            <Button
              variant="subtle"
              icon-left="lucide-download"
              :loading="importing"
              :disabled="!doc.doctype_to_import || !doc.mobile_field"
              :label="__('Import recipients')"
              @click="runImport"
            />
          </div>
        </section>

        <ErrorMessage :message="error" />
      </div>
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <div>
          <Button v-if="name" variant="ghost" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="remove" />
        </div>
        <div class="flex items-center gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
          <Button variant="solid" :loading="saving" :label="name ? __('Save') : __('Create')" @click="save" />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, ref, watch } from 'vue'
import { Button, ErrorMessage, FileUploader, FormControl, FormLabel, ScrollArea, Skeleton, Textarea, call, toast } from 'frappe-ui'
import PhoneField from '@/components/Common/PhoneField.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import LinkField from '@/components/Common/LinkField.vue'
import RecordFilters from '@/components/Common/RecordFilters.vue'
import Pagination from '@/components/Common/Pagination.vue'
import { PAGE_SIZES, pageLength, pageOf } from '@/utils/paging'
import { useUI } from '@/stores/ui'
import { errorMessage, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
})

const emit = defineEmits(['saved', 'deleted'])

const open = defineModel('open', { type: Boolean, default: false })

const ui = useUI()
const doc = ref({ recipients: [] })
const fields = ref([])
const dataFields = ref('')
const pasting = ref(false)
const pasted = ref('')
const upload = reactive({ loading: false, filename: '', headers: [], rows: [], total: 0, truncated: false, mobile: '', name: '' })
const FILE_LIMIT = 5 * 1024 * 1024
const FILE_TYPES = ['.csv', '.xlsx', '.xls']
const MOBILE_HEADER = /mobile|phone|whatsapp|cell|contact.?no|number/i
const NAME_HEADER = /name|customer|contact/i
const page = ref(1)
const query = ref('')
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const error = ref('')
let counter = 0

const filtered = computed(() => {
  const text = query.value.trim().toLowerCase()
  if (!text) return doc.value.recipients
  const digits = text.replace(/\D/g, '')
  return doc.value.recipients.filter(
    (row) =>
      (row.recipient_name || '').toLowerCase().includes(text) ||
      (digits &&
        String(row.mobile_number || '')
          .replace(/\D/g, '')
          .includes(digits)),
  )
})

const visibleRows = computed(() => pageOf(filtered.value, page.value))

watch([query, pageLength], () => (page.value = 1))

watch(
  () => filtered.value.length,
  (count) => {
    const last = Math.max(1, Math.ceil(count / pageLength.value))
    if (page.value > last) page.value = last
  },
)

function removeRow(row) {
  const index = doc.value.recipients.indexOf(row)
  if (index >= 0) doc.value.recipients.splice(index, 1)
}

const fieldOptions = computed(() =>
  fields.value
    .filter((field) => ['Data', 'Phone', 'Link', 'Dynamic Link', 'Select', 'Small Text'].includes(field.fieldtype))
    .map((field) => ({ label: `${field.label} (${field.fieldname})`, value: field.fieldname })),
)

const parsed = computed(() => {
  const seen = new Set(doc.value.recipients.map((row) => clean(row.mobile_number)))
  const out = []

  for (const line of pasted.value.split(/\r?\n/)) {
    const [number, ...rest] = line.split(/[,\t;]/)
    const mobile = clean(number)
    if (mobile.replace('+', '').length < 6 || seen.has(mobile)) continue

    seen.add(mobile)
    out.push({ mobile_number: mobile, recipient_name: rest.join(' ').trim() })
  }

  return out
})

const columnOptions = computed(() => upload.headers.map((header) => ({ label: header, value: header })))

const extraColumns = computed(() =>
  upload.headers
    .map((header, index) => ({ header, index, key: keyOf(header) }))
    .filter((column) => column.key && column.header !== upload.mobile && column.header !== upload.name),
)

const uploaded = computed(() => {
  const out = { rows: [], duplicates: 0, invalid: 0 }
  const at = upload.headers.indexOf(upload.mobile)
  if (at < 0) return out
  const named = upload.headers.indexOf(upload.name)
  const seen = new Set(doc.value.recipients.map((row) => clean(row.mobile_number)))
  for (const line of upload.rows) {
    const mobile = clean(line[at])
    if (mobile.replace('+', '').length < 6) {
      out.invalid += 1
      continue
    }
    if (seen.has(mobile)) {
      out.duplicates += 1
      continue
    }
    seen.add(mobile)
    const data = {}
    for (const column of extraColumns.value) {
      if (line[column.index] !== '') data[column.key] = line[column.index]
    }
    out.rows.push({ mobile_number: mobile, recipient_name: named >= 0 ? line[named] : '', recipient_data: JSON.stringify(data) })
  }
  return out
})

function keyOf(header) {
  return String(header || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function resetUpload() {
  Object.assign(upload, { loading: false, filename: '', headers: [], rows: [], total: 0, truncated: false, mobile: '', name: '' })
}

function checkFile(file) {
  if (!FILE_TYPES.some((type) => file.name.toLowerCase().endsWith(type))) return __('Upload a CSV or Excel file (.csv, .xlsx or .xls).')
  if (file.size > FILE_LIMIT) return __('The file is larger than 5 MB. Split it into smaller files.')
  return null
}

function uploadFailed(err) {
  error.value = typeof err === 'string' ? err : errorMessage(err)
}

async function readUploaded(file) {
  error.value = ''
  upload.loading = true
  try {
    const result = await call('onechat.campaigns.bulk_messaging.read_recipient_file', { file_url: file.file_url })
    Object.assign(upload, {
      filename: file.file_name,
      headers: result.headers,
      rows: result.rows,
      total: result.total,
      truncated: result.truncated,
      mobile: result.headers.find((header) => MOBILE_HEADER.test(header)) || result.headers[0],
      name: result.headers.find((header) => NAME_HEADER.test(header) && !MOBILE_HEADER.test(header)) || '',
    })
    pasting.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    upload.loading = false
  }
}

function addUploaded() {
  doc.value.recipients.push(...uploaded.value.rows.map((values) => row(values)))
  if (!doc.value.doctype_to_import) {
    const keys = new Set(
      dataFields.value
        .split(',')
        .map((field) => field.trim())
        .filter(Boolean),
    )
    extraColumns.value.forEach((column) => keys.add(column.key))
    dataFields.value = [...keys].join(', ')
  }
  resetUpload()
}

function clean(value) {
  return String(value || '').replace(/[^\d+]/g, '')
}

function dataKeys(value) {
  try {
    const keys = Object.keys(JSON.parse(value || '{}'))
    return keys.length ? keys.join(', ') : '—'
  } catch {
    return '—'
  }
}

function row(values = {}) {
  counter += 1
  return { key: `new-${counter}`, mobile_number: '', recipient_name: '', recipient_data: '{}', ...values }
}

function addRow() {
  query.value = ''
  page.value = 1
  doc.value.recipients.unshift(row())
}

function addPasted() {
  doc.value.recipients.push(...parsed.value.map((values) => row(values)))
  pasted.value = ''
  pasting.value = false
}

async function load() {
  const loaded = await call('frappe.client.get', { doctype: 'WhatsApp Recipient List', name: props.name })
  doc.value = { ...loaded, recipients: loaded.recipients || [] }
  dataFields.value = parseList(loaded.data_fields).join(', ')
}

function parseList(value) {
  try {
    const list = JSON.parse(value || '[]')
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

watch(
  open,
  async (value) => {
    if (!value) return

    error.value = ''
    pasting.value = false
    resetUpload()
    page.value = 1
    query.value = ''
    if (!props.name) {
      doc.value = { list_name: '', description: '', recipients: [] }
      dataFields.value = ''
      return
    }

    loading.value = true
    try {
      await load()
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

watch(
  () => doc.value.doctype_to_import,
  async (doctype) => {
    fields.value = []
    if (!doctype) return

    fields.value = await call('onechat.campaigns.broadcasts.doctype_fields', { doctype }).catch(() => [])
  },
)

function parseFilters(text) {
  let value = null
  try {
    value = text ? JSON.parse(text) : null
  } catch {
    return []
  }
  if (Array.isArray(value)) return value.filter((row) => Array.isArray(row))
  if (value && typeof value === 'object') {
    return Object.entries(value).map(([field, rule]) => (Array.isArray(rule) ? [field, rule[0], rule[1]] : [field, '=', rule]))
  }
  return []
}

const filterRows = computed({
  get: () => parseFilters((doc.value.import_filters || '').trim()),
  set: (rows) => (doc.value.import_filters = rows.length ? JSON.stringify(rows) : ''),
})

function filtersJson() {
  const rows = parseFilters((doc.value.import_filters || '').trim())
  return rows.length ? rows : null
}

function payload() {
  const keys = dataFields.value
    .split(',')
    .map((field) => field.trim())
    .filter(Boolean)

  return {
    ...doc.value,
    import_from_doctype: doc.value.doctype_to_import ? 1 : 0,
    data_fields: keys.length ? JSON.stringify(keys) : null,
    recipients: doc.value.recipients
      .filter((recipient) => clean(recipient.mobile_number))
      .map(({ key, ...recipient }) => ({ ...recipient, mobile_number: clean(recipient.mobile_number) })),
  }
}

async function persist() {
  const values = payload()
  if (!values.list_name?.trim()) throw new Error(__('Give the list a name'))
  filtersJson()

  if (props.name || doc.value.creation) return call('frappe.client.save', { doc: values })

  return call('frappe.client.insert', { doc: { ...values, doctype: 'WhatsApp Recipient List' } })
}

async function save() {
  saving.value = true
  error.value = ''

  try {
    const saved = await persist()
    toast.success(props.name ? __('Saved') : __('Created'))
    emit('saved', saved)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function runImport() {
  ui.confirm({
    title: __('Import recipients?'),
    message: __('The current recipients are replaced with numbers from {0}.').format(__(doc.value.doctype_to_import)),
    action: __('Import'),
    onConfirm: importNow,
  })
}

async function importNow() {
  importing.value = true
  error.value = ''

  try {
    const filters = filtersJson()
    const saved = doc.value.creation ? doc.value : await persist()
    const settings = {
      import_from_doctype: 1,
      name_field: doc.value.name_field || null,
      import_filters: filters ? JSON.stringify(filters, null, 2) : null,
    }

    const keys = dataFields.value
      .split(',')
      .map((field) => field.trim())
      .filter(Boolean)

    const count = await call('onechat.campaigns.bulk_messaging.import_recipients', {
      list_name: saved.name,
      doctype: doc.value.doctype_to_import,
      mobile_field: doc.value.mobile_field,
      name_field: doc.value.name_field || null,
      filters: filters ? JSON.stringify(filters) : null,
      limit: doc.value.import_limit || null,
      data_fields: keys.length ? JSON.stringify(keys) : null,
    })

    const loaded = await call('frappe.client.set_value', {
      doctype: 'WhatsApp Recipient List',
      name: saved.name,
      fieldname: settings,
    })
    doc.value = { ...loaded, recipients: loaded.recipients || [] }
    toast.success(__('Imported {0} recipients').format(count))
    emit('saved', loaded)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    importing.value = false
  }
}

function remove() {
  ui.confirm({
    title: __('Delete this list?'),
    message: __('Broadcasts that already used it keep their history.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: 'WhatsApp Recipient List', name: props.name })
      toast.success(__('Deleted'))
      emit('deleted', props.name)
      open.value = false
    },
  })
}
</script>

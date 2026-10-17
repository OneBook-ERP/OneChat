<template>
  <ResponsiveDialog v-model:open="open" :title="name ? __('Edit notification rule') : __('New notification rule')" size="4xl">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-3 py-2">
        <Skeleton v-for="row in 5" :key="row" class="h-9 w-full" />
      </div>

      <div v-else class="flex flex-col gap-5">
        <div class="flex items-start gap-3 rounded-4 bg-surface-gray-2 px-4 py-3">
          <span class="lucide-bell-ring mt-0.5 size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
          <p class="text-base leading-6 text-ink-gray-8">{{ summary }}</p>
        </div>

        <div class="flex flex-col gap-5 sm:flex-row">
          <ScrollArea orientation="horizontal" class="shrink-0 sm:w-44">
            <nav class="flex gap-1 sm:flex-col">
              <button
                v-for="(item, index) in STEPS"
                :key="item.key"
                type="button"
                class="flex shrink-0 items-center gap-2.5 rounded-4 px-2.5 py-2 text-left text-base transition-colors"
                :class="step === item.key ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6 hover:bg-surface-gray-2'"
                @click="step = item.key"
              >
                <span
                  class="flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-medium"
                  :class="problems[item.key] ? 'bg-surface-red-2 text-ink-red-7' : 'bg-surface-gray-4 text-ink-gray-8'"
                >
                  {{ index + 1 }}
                </span>
                <span>{{ __(item.label) }}</span>
              </button>
            </nav>
          </ScrollArea>

          <div class="min-w-0 flex-1">
            <div v-show="step === 'when'" class="flex flex-col gap-4">
              <FormControl
                v-model="doc.notification_name"
                type="text"
                :label="__('Rule name')"
                :placeholder="__('Invoice ready')"
                :disabled="!!name"
                required
              />
              <LinkField
                v-model="doc.reference_doctype"
                doctype="DocType"
                :filters="{ istable: 0 }"
                :label="__('Document type')"
                :description="__('The kind of document this rule watches.')"
                required
              />
              <div class="flex flex-col gap-1.5">
                <FormLabel :label="__('Send')" />
                <TabButtons
                  v-model="doc.notification_type"
                  :options="[
                    { label: __('On a document event'), value: 'DocType Event' },
                    { label: __('On a schedule'), value: 'Scheduler Event' },
                  ]"
                />
              </div>

              <template v-if="doc.notification_type === 'DocType Event'">
                <Select
                  v-model="doc.doctype_event"
                  :label="__('Event')"
                  :placeholder="__('Pick an event')"
                  :options="DOCTYPE_EVENTS.map((value) => ({ label: __(value), value }))"
                />
                <div v-if="isDays" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormControl
                    v-model="doc.days_in_advance"
                    type="number"
                    :label="doc.doctype_event === 'Days Before' ? __('Days before') : __('Days after')"
                    required
                  />
                  <FieldPicker
                    v-model="doc.date_changed"
                    :doctype="doc.reference_doctype"
                    :fieldtypes="['Date', 'Datetime']"
                    :extra="DATE_EXTRAS"
                    :label="__('Date field')"
                    required
                  />
                </div>
              </template>

              <Select
                v-else
                v-model="doc.event_frequency"
                :label="__('How often')"
                :placeholder="__('Pick a frequency')"
                :options="FREQUENCIES.map((value) => ({ label: __(value), value }))"
              />

              <ConditionBuilder
                v-model="doc.condition"
                :doctype="doc.reference_doctype"
                :label="__('Only when (optional)')"
                :empty-text="__('No conditions, so it sends every time')"
              >
                <template #code-help>
                  {{ __('A Python expression. The message goes out only when it is true, for example') }}
                  <code class="rounded-1 bg-surface-gray-2 px-1 font-mono">doc.status == 'Paid'</code>.
                  <template v-if="doc.notification_type === 'Scheduler Event'">
                    {{ __('On a schedule you can also pick recipients, for example') }}
                    <code class="rounded-1 bg-surface-gray-2 px-1 font-mono">doc.set("_contact_list", ["919123456789"])</code>.
                  </template>
                </template>
              </ConditionBuilder>
            </div>

            <div v-show="step === 'who'" class="flex flex-col gap-4">
              <FieldPicker
                v-model="doc.field_name"
                :doctype="doc.reference_doctype"
                :fieldtypes="['Data', 'Phone', 'Small Text', 'Link', 'Read Only']"
                :label="__('Mobile number field')"
                :description="__('The field on the document that holds the recipient’s WhatsApp number.')"
              />
              <FormControl
                v-model="doc.mobile_numbers"
                type="textarea"
                :rows="3"
                :label="__('Fixed numbers')"
                :description="__('Comma separated, with country code. These always get the message.')"
                placeholder="919876543210, 14155550123"
              />
              <p v-if="doc.notification_type === 'Scheduler Event'" class="text-sm text-ink-gray-5">
                {{ __('Scheduled rules send to the fixed numbers, or to the numbers your condition sets.') }}
              </p>
            </div>

            <div v-show="step === 'what'" class="flex flex-col gap-4">
              <TabButtons
                :model-value="doc.send_plain_message ? 'plain' : 'template'"
                :options="[
                  { label: __('Approved template'), value: 'template' },
                  { label: __('Plain message'), value: 'plain' },
                ]"
                @update:model-value="setPlain"
              />

              <template v-if="!doc.send_plain_message">
                <LinkField v-model="doc.template" doctype="WhatsApp Templates" :label="__('Template')" required />
                <div v-if="template" class="rounded-4 border border-outline-gray-2 p-3">
                  <div class="mb-2 flex items-center gap-2">
                    <Badge v-if="template.header_type" :label="template.header_type" theme="gray" />
                    <Badge v-if="template.status" :label="template.status" :theme="approved ? 'green' : 'amber'" />
                    <span class="text-xs text-ink-gray-5">{{ template.language_code }}</span>
                  </div>
                  <p class="whitespace-pre-wrap text-sm leading-5 text-ink-gray-7">{{ template.template }}</p>
                </div>
              </template>

              <FormControl
                v-else
                v-model="doc.message_body"
                type="textarea"
                :rows="5"
                :label="__('Message')"
                :description="__('Use {0}, {1} … for values from the document.').format('{{1}}', '{{2}}')"
                required
              />

              <div v-if="variableCount || doc.fields.length" class="flex flex-col gap-2">
                <FormLabel :label="__('Fill the variables from')" />
                <div v-for="(row, index) in doc.fields" :key="index" class="flex items-end gap-2">
                  <span class="mb-1.5 w-12 shrink-0 font-mono text-sm text-ink-gray-6">{{ variableTag(index) }}</span>
                  <FieldPicker v-model="row.field_name" class="min-w-0 flex-1" :doctype="doc.reference_doctype" />
                  <Button
                    v-if="index >= variableCount"
                    variant="ghost"
                    icon="lucide-x"
                    :label="__('Remove')"
                    @click="doc.fields.splice(index, 1)"
                  />
                </div>
              </div>

              <template v-if="!doc.send_plain_message && hasMediaHeader">
                <div class="flex flex-col gap-1.5">
                  <FormLabel :label="__('Header attachment')" />
                  <TabButtons
                    :model-value="attachmentMode"
                    :options="[
                      { label: __('Template file'), value: 'template' },
                      { label: __('Document print (PDF)'), value: 'print' },
                      { label: __('Custom file'), value: 'custom' },
                    ]"
                    @update:model-value="setAttachment"
                  />
                  <p
                    v-if="attachmentMode === 'template'"
                    class="flex items-center gap-1.5 text-sm"
                    :class="template?.sample ? 'text-ink-gray-5' : 'text-ink-amber-8'"
                  >
                    <span
                      :class="template?.sample ? 'lucide-paperclip' : 'lucide-triangle-alert'"
                      class="size-3.5 shrink-0"
                      aria-hidden="true"
                    />
                    <TruncatedText
                      class="min-w-0 truncate"
                      :text="
                        template?.sample
                          ? __('Sends the file uploaded with the template: {0}').format(template.sample.split('/').pop())
                          : __('This template has no header file yet. Upload one on the template, or pick another option.')
                      "
                    />
                  </p>
                </div>

                <template v-if="doc.custom_attachment">
                  <div class="flex flex-col gap-1.5">
                    <FormLabel :label="__('File')" />
                    <div class="flex items-center gap-2">
                      <FileUploader :private="privateUpload" @success="(file) => (doc.attach = file.file_url)">
                        <template #default="{ openFileSelector, uploading, progress }">
                          <Button
                            icon-left="lucide-upload"
                            :loading="uploading"
                            :label="uploading ? __('Uploading {0}%').format(progress) : __('Upload')"
                            @click="openFileSelector"
                          />
                        </template>
                      </FileUploader>
                      <TruncatedText class="min-w-0 flex-1 truncate text-sm text-ink-gray-6" :text="doc.attach || __('No file yet')" />
                      <Badge
                        v-if="doc.attach"
                        size="sm"
                        variant="subtle"
                        :theme="doc.attach.startsWith('/private/') ? 'amber' : 'gray'"
                        :label="doc.attach.startsWith('/private/') ? __('Private') : __('Public')"
                      />
                      <Button v-if="doc.attach" variant="ghost" icon="lucide-x" :label="__('Remove')" @click="doc.attach = ''" />
                    </div>
                    <div v-if="!doc.attach" class="flex items-center gap-2">
                      <Switch v-model="privateUpload" :label="__('Upload as private')" />
                      <InfoHint
                        :title="__('Private files')"
                        :text="
                          __(
                            'Public files can be opened by anyone with the link. Private files need a login on this site, so OneChat uploads them to WhatsApp directly when it sends the message.',
                          )
                        "
                      />
                    </div>
                  </div>
                  <FieldPicker
                    v-model="doc.attach_from_field"
                    :doctype="doc.reference_doctype"
                    :fieldtypes="['Attach', 'Attach Image']"
                    :label="__('Or take the file from a field')"
                  />
                </template>
                <FormControl v-model="doc.file_name" type="text" :label="__('File name')" placeholder="invoice.pdf" />
              </template>

              <FormControl
                v-if="!doc.send_plain_message && dynamicButtons"
                v-model="doc.button_fields"
                type="text"
                :label="__('Button URL fields')"
                :description="__('Comma separated field names, one per dynamic URL button, in order.')"
                placeholder="name"
              />
            </div>

            <div v-show="step === 'after'" class="flex flex-col gap-4">
              <p class="text-sm text-ink-gray-6">
                {{ __('Optionally mark the document once the message is sent, so it is not sent twice.') }}
              </p>
              <FieldPicker v-model="doc.set_property_after_alert" :doctype="doc.reference_doctype" :label="__('Set this field')" />
              <FormControl
                v-if="doc.set_property_after_alert"
                v-model="doc.property_value"
                type="text"
                :label="__('To this value')"
                placeholder="1"
              />
            </div>
          </div>
        </div>

        <ErrorMessage :message="error" />
      </div>
    </template>

    <template #actions>
      <div class="flex w-full flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-3">
          <Button v-if="name" variant="ghost" theme="red" icon="lucide-trash-2" :label="__('Delete')" @click="remove" />
          <Switch :model-value="!doc.disabled" :label="__('Enabled')" @update:model-value="(value) => (doc.disabled = value ? 0 : 1)" />
        </div>
        <div class="flex items-center gap-2">
          <Button v-if="stepIndex > 0" variant="subtle" :label="__('Back')" @click="move(-1)" />
          <Button v-if="stepIndex < STEPS.length - 1" variant="subtle" :label="__('Next')" @click="move(1)" />
          <Button variant="solid" :loading="saving" :label="name ? __('Save') : __('Create')" @click="save" />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import {
  Badge,
  Button,
  ErrorMessage,
  FileUploader,
  FormControl,
  FormLabel,
  ScrollArea,
  Select,
  Skeleton,
  Switch,
  TabButtons,
  call,
  toast,
} from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import InfoHint from '@/components/Common/InfoHint.vue'
import ConditionBuilder from './ConditionBuilder.vue'
import FieldPicker from './FieldPicker.vue'
import LinkField from '@/components/Common/LinkField.vue'
import { doctypeFields, placeholderCount, templateDetails } from '@/components/FlowBuilder/api'
import { useUI } from '@/stores/ui'
import { describe } from '@/utils/condition'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
})

const emit = defineEmits(['saved', 'deleted'])

const open = defineModel('open', { type: Boolean, default: false })

const STEPS = [
  { key: 'when', label: 'When' },
  { key: 'who', label: 'Who' },
  { key: 'what', label: 'What' },
  { key: 'after', label: 'After sending' },
]

const DOCTYPE_EVENTS = [
  'After Insert',
  'After Save',
  'After Submit',
  'After Cancel',
  'After Delete',
  'After Save (Submitted Document)',
  'Before Insert',
  'Before Validate',
  'Before Save',
  'Before Submit',
  'Before Cancel',
  'Before Delete',
  'Before Save (Submitted Document)',
  'Days Before',
  'Days After',
]

const FREQUENCIES = ['All', 'Hourly', 'Daily', 'Weekly', 'Monthly', 'Yearly', 'Hourly Long', 'Daily Long', 'Weekly Long', 'Monthly Long']

const DATE_EXTRAS = [
  { label: 'Created on', value: 'creation', description: 'creation' },
  { label: 'Last modified', value: 'modified', description: 'modified' },
]

const EVENT_PHRASES = {
  'After Insert': 'created',
  'After Save': 'saved',
  'After Submit': 'submitted',
  'After Cancel': 'cancelled',
  'After Delete': 'deleted',
  'After Save (Submitted Document)': 'updated after submit',
  'Before Insert': 'about to be created',
  'Before Validate': 'about to be validated',
  'Before Save': 'about to be saved',
  'Before Submit': 'about to be submitted',
  'Before Cancel': 'about to be cancelled',
  'Before Delete': 'about to be deleted',
  'Before Save (Submitted Document)': 'about to be updated after submit',
}

const FIELDS = [
  'notification_name',
  'reference_doctype',
  'notification_type',
  'doctype_event',
  'event_frequency',
  'days_in_advance',
  'date_changed',
  'condition',
  'field_name',
  'mobile_numbers',
  'send_plain_message',
  'message_body',
  'template',
  'code',
  'header_type',
  'attach_document_print',
  'custom_attachment',
  'attach',
  'file_name',
  'attach_from_field',
  'button_fields',
  'set_property_after_alert',
  'property_value',
  'disabled',
]

const ui = useUI()
const doc = ref(blank())
const loaded = ref(null)
const template = ref(null)
const fieldLabels = ref({})
const step = ref('when')
const loading = ref(false)
const saving = ref(false)
const error = ref('')

function blank() {
  return {
    notification_name: '',
    reference_doctype: '',
    notification_type: 'DocType Event',
    doctype_event: 'After Save',
    event_frequency: '',
    days_in_advance: 1,
    date_changed: '',
    condition: '',
    field_name: '',
    mobile_numbers: '',
    send_plain_message: 0,
    message_body: '',
    template: '',
    code: '',
    header_type: '',
    attach_document_print: 0,
    custom_attachment: 0,
    attach: '',
    file_name: '',
    attach_from_field: '',
    button_fields: '',
    set_property_after_alert: '',
    property_value: '',
    disabled: 0,
    fields: [],
  }
}

watch(
  open,
  async (value) => {
    if (!value) return

    error.value = ''
    step.value = 'when'
    template.value = null
    loaded.value = null

    if (!props.name) {
      doc.value = blank()
      return
    }

    loading.value = true
    try {
      const data = await call('frappe.client.get', { doctype: 'WhatsApp Notification', name: props.name })
      loaded.value = data
      doc.value = {
        ...blank(),
        ...Object.fromEntries(FIELDS.map((field) => [field, data[field] ?? blank()[field]])),
        fields: (data.fields || []).map((row) => ({ field_name: row.field_name || '' })),
      }
      pad()
      loadTemplate(false)
      loadLabels()
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

async function loadTemplate(prefill) {
  const name = doc.value.template
  template.value = null
  if (!name || doc.value.send_plain_message) return

  try {
    const data = await templateDetails(name)
    if (doc.value.template !== name) return

    template.value = data
    doc.value.header_type = data.header_type || ''
    doc.value.code = data.template || ''

    if (!['DOCUMENT', 'IMAGE'].includes(data.header_type)) {
      doc.value.attach_document_print = 0
      doc.value.custom_attachment = 0
    }

    const hint = String(data.field_names || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    if (prefill && hint.length && !doc.value.fields.some((row) => row.field_name)) {
      doc.value.fields = hint.map((field_name) => ({ field_name }))
    }
    pad()
  } catch {
    template.value = null
  }
}

async function loadLabels() {
  const doctype = doc.value.reference_doctype
  fieldLabels.value = {}
  if (!doctype) return

  try {
    const fields = await doctypeFields(doctype)
    if (doc.value.reference_doctype !== doctype) return

    fieldLabels.value = Object.fromEntries(fields.map((field) => [field.fieldname, field.label || field.fieldname]))
  } catch {
    fieldLabels.value = {}
  }
}

watch(
  () => doc.value.template,
  () => loadTemplate(true),
)

watch(
  () => doc.value.reference_doctype,
  () => loadLabels(),
)

const stepIndex = computed(() => STEPS.findIndex((item) => item.key === step.value))

const isDays = computed(() => ['Days Before', 'Days After'].includes(doc.value.doctype_event))

const approved = computed(() => String(template.value?.status || '').toUpperCase() === 'APPROVED')

const hasMediaHeader = computed(() => ['DOCUMENT', 'IMAGE'].includes(template.value?.header_type || doc.value.header_type))

const dynamicButtons = computed(() =>
  (template.value?.buttons || []).some((button) => button.button_type === 'Visit Website' && button.url_type === 'Dynamic'),
)

const variableCount = computed(() =>
  placeholderCount(doc.value.send_plain_message ? doc.value.message_body : template.value?.template || doc.value.code),
)

function pad() {
  while (doc.value.fields.length < variableCount.value) doc.value.fields.push({ field_name: '' })
}

watch(variableCount, pad)

function variableTag(index) {
  return `{{${index + 1}}}`
}

function fieldLabel(fieldname) {
  return fieldLabels.value[fieldname] || fieldname
}

const summary = computed(() => {
  const value = doc.value
  const doctype = value.reference_doctype || __('document')
  const message = value.send_plain_message ? __('a plain message') : value.template ? `‘${value.template}’` : __('a template')

  const people = []
  if (value.field_name) people.push(__('the {0} on it').format(fieldLabel(value.field_name).toLowerCase()))
  const numbers = String(value.mobile_numbers || '')
    .split(',')
    .filter((item) => item.trim()).length
  if (numbers) people.push(numbers === 1 ? __('1 fixed number') : __('{0} fixed numbers').format(numbers))
  const who = people.length ? people.join(__(' and ')) : __('nobody yet')

  let text
  if (value.notification_type === 'Scheduler Event') {
    const frequency = value.event_frequency ? __(value.event_frequency).toLowerCase() : __('on a schedule')
    text = __('Run {0} for {1} and send {2} to {3}').format(frequency, doctype, message, who)
  } else if (isDays.value) {
    const when = value.doctype_event === 'Days Before' ? __('before') : __('after')
    const date = value.date_changed ? fieldLabel(value.date_changed).toLowerCase() : __('date')
    text = __('{0} days {1} a {2}’s {3}, send {4} to {5}').format(value.days_in_advance || 0, when, doctype, date, message, who)
  } else {
    const phrase = EVENT_PHRASES[value.doctype_event] ? __(EVENT_PHRASES[value.doctype_event]) : __('changed')
    text = __('When a {0} is {1}, send {2} to {3}').format(doctype, phrase, message, who)
  }

  if (value.condition) {
    const readable = describe(value.condition, (field) => fieldLabel(field), __)
    text += `, ${readable ? __('if {0}').format(readable) : __('if the condition holds')}`
  }
  if (value.set_property_after_alert) {
    text += `, ${__('then set {0}').format(fieldLabel(value.set_property_after_alert).toLowerCase())}`
  }

  return `${text}.`
})

const problems = computed(() => {
  const value = doc.value
  const out = { when: '', who: '', what: '', after: '' }

  if (!value.notification_name) out.when = __('Give the rule a name.')
  else if (!value.reference_doctype) out.when = __('Pick a document type.')
  else if (value.notification_type === 'DocType Event' && !value.doctype_event) out.when = __('Pick an event.')
  else if (value.notification_type === 'Scheduler Event' && !value.event_frequency) out.when = __('Pick how often it runs.')
  else if (isDays.value && (!value.days_in_advance || !value.date_changed)) out.when = __('Set the days and the date field.')

  const needsRecipient = value.send_plain_message || value.notification_type === 'DocType Event'
  if (needsRecipient && !value.field_name && !String(value.mobile_numbers || '').trim()) {
    out.who = __('Pick a mobile number field or add fixed numbers.')
  }

  if (value.send_plain_message && !String(value.message_body || '').trim()) out.what = __('Write the message.')
  else if (!value.send_plain_message && !value.template) out.what = __('Pick a template.')
  else if (!value.send_plain_message && value.custom_attachment && !value.attach && !value.attach_from_field) {
    out.what = __('Upload a file or pick a field to take it from.')
  } else if (
    !value.send_plain_message &&
    hasMediaHeader.value &&
    attachmentMode.value === 'template' &&
    template.value &&
    !template.value.sample
  ) {
    out.what = __('This template has no header file. Upload one on the template, or pick Document print or Custom file.')
  }

  if (value.set_property_after_alert && value.property_value === '') out.after = __('Set the value to write.')

  return out
})

function move(delta) {
  step.value = STEPS[Math.min(Math.max(stepIndex.value + delta, 0), STEPS.length - 1)].key
}

function setPlain(mode) {
  doc.value.send_plain_message = mode === 'plain' ? 1 : 0
  if (mode === 'plain') {
    doc.value.template = ''
    doc.value.code = ''
    doc.value.header_type = ''
    doc.value.attach_document_print = 0
    doc.value.custom_attachment = 0
  }
}

const privateUpload = ref(false)
const attachmentMode = computed(() => (doc.value.custom_attachment ? 'custom' : doc.value.attach_document_print ? 'print' : 'template'))

function setAttachment(mode) {
  doc.value.custom_attachment = mode === 'custom' ? 1 : 0
  doc.value.attach_document_print = mode === 'print' ? 1 : 0
}

function payload() {
  const value = doc.value
  const out = Object.fromEntries(FIELDS.map((field) => [field, value[field] ?? null]))

  if (value.notification_type === 'DocType Event') out.event_frequency = null
  else out.doctype_event = null
  if (!isDays.value) {
    out.days_in_advance = 0
    out.date_changed = null
  }

  const count = variableCount.value
  out.fields = value.fields.filter((row, index) => row.field_name || index < count).map((row) => ({ field_name: row.field_name || '' }))

  return out
}

async function save() {
  const failing = STEPS.find((item) => problems.value[item.key])
  if (failing) {
    step.value = failing.key
    error.value = problems.value[failing.key]
    return
  }

  saving.value = true
  error.value = ''

  try {
    const saved = props.name
      ? await call('frappe.client.save', { doc: { ...loaded.value, ...payload() } })
      : await call('frappe.client.insert', { doc: { doctype: 'WhatsApp Notification', ...payload() } })

    toast.success(props.name ? __('Rule saved') : __('Rule created'))
    emit('saved', saved)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function remove() {
  ui.confirm({
    title: __('Delete this rule?'),
    message: __('Messages will stop going out for it. This cannot be undone.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: 'WhatsApp Notification', name: props.name })
      toast.success(__('Rule deleted'))
      emit('deleted', props.name)
      open.value = false
    },
  })
}
</script>

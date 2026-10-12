<template>
  <ResponsiveDialog v-model:open="open" :title="name ? __('Edit template') : __('New template')" size="5xl">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-3">
        <Skeleton v-for="row in 6" :key="row" class="h-9 w-full" />
      </div>

      <div v-else class="flex h-[min(720px,calc(100vh-14rem))] flex-col gap-4">
        <Alert v-if="warning" class="shrink-0" :theme="warning.theme" :title="warning.title" :description="warning.description" />
        <TabButtons v-if="name" v-model="tab" class="shrink-0 self-start" :options="tabs" />
        <ScrollArea v-if="name && tab === 'analytics'" class="min-h-0 flex-1" viewport-class="pr-3">
          <TemplateAnalytics :template="name" />
        </ScrollArea>
        <div v-else class="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <ScrollArea class="min-h-0" viewport-class="pr-3">
            <div class="flex min-w-0 flex-col gap-6 pb-2">
              <Alert
                v-if="name"
                theme="amber"
                :title="__('Saving sends this template to Meta again')"
                :description="__('Meta reviews every change before the template can be used. Messages sent meanwhile may fail.')"
              />

              <section class="flex flex-col gap-3">
                <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Basics') }}</h3>
                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <FormControl
                    v-if="!name"
                    v-model="sampleKey"
                    class="sm:col-span-2"
                    type="select"
                    :label="__('Start from')"
                    :options="sampleOptions"
                    :description="sampleHint"
                    @update:model-value="applySample"
                  />
                  <FormControl
                    v-model="doc.template_name"
                    type="text"
                    :label="__('Template name')"
                    :required="true"
                    :disabled="!!name"
                    :description="
                      name ? __('Meta name: {0}').format(doc.actual_name || '—') : __('Lowercase with underscores is sent to Meta')
                    "
                  />
                  <FormControl v-model="doc.category" type="select" :label="__('Category')" :required="true" :options="categories" />
                  <LinkField v-model="doc.language" doctype="Language" :label="__('Language')" :required="true" />
                  <LinkField
                    v-model="doc.whatsapp_account"
                    doctype="OneChat Account"
                    :filters="{ channel: ['!=', 'Instagram'] }"
                    :label="__('WhatsApp account')"
                    :description="__('Leave empty to use the default account')"
                  />
                </div>
              </section>

              <section class="flex flex-col gap-3">
                <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Header') }}</h3>
                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <FormControl
                    :model-value="doc.header_type || ''"
                    type="select"
                    :label="__('Header type')"
                    :options="headerTypes"
                    @update:model-value="setHeaderType"
                  />
                  <template v-if="doc.header_type === 'TEXT'">
                    <FormControl
                      v-model="doc.header"
                      type="text"
                      :label="__('Header text')"
                      :maxlength="60"
                      :placeholder="__('Order update')"
                    />
                    <FormControl
                      v-if="variableCount(doc.header)"
                      v-model="doc.sample"
                      class="sm:col-span-2"
                      type="text"
                      :label="__('Header sample')"
                      :description="__('Example value for {0} in the header').format(token(1))"
                    />
                  </template>
                  <div v-else-if="doc.header_type" class="flex flex-col gap-1.5">
                    <FormLabel :label="doc.header_type === 'IMAGE' ? __('Sample image') : __('Sample document')" />
                    <FileUploader
                      :file-types="doc.header_type === 'IMAGE' ? 'image/*' : '.pdf'"
                      :private="false"
                      @success="(file) => (doc.sample = file.file_url)"
                    >
                      <template #default="{ uploading, progress, openFileSelector }">
                        <div class="flex min-w-0 items-center gap-2">
                          <Button
                            variant="subtle"
                            icon-left="lucide-upload"
                            :loading="uploading"
                            :label="uploading ? `${progress}%` : doc.sample ? __('Replace') : __('Upload')"
                            @click="openFileSelector"
                          />
                          <TruncatedText v-if="doc.sample" class="truncate text-sm text-ink-gray-6" :text="doc.sample.split('/').pop()" />
                        </div>
                      </template>
                    </FileUploader>
                  </div>
                </div>
              </section>

              <section class="flex flex-col gap-3">
                <div class="flex items-center justify-between gap-2">
                  <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Body') }}</h3>
                  <Button variant="subtle" size="sm" icon-left="lucide-braces" :label="__('Add variable')" @click="addVariable" />
                </div>
                <div ref="bodyBox" class="template-body">
                  <Textarea
                    v-model="doc.template"
                    :rows="7"
                    :placeholder="__('Hi {0}, your order {1} is on its way.').format(token(1), token(2))"
                  />
                </div>
                <p class="-mt-1 text-right text-xs text-ink-gray-5">
                  {{ __('*bold* _italic_ ~strike~') }} · {{ (doc.template || '').length }}/1024
                </p>

                <div v-if="count" class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-3">
                  <p class="text-sm text-ink-gray-6">{{ __('Sample values help Meta approve the template. Avoid commas.') }}</p>
                  <div v-for="index in count" :key="index" class="flex items-center gap-2">
                    <code class="w-12 shrink-0 text-sm text-ink-gray-6">{{ token(index) }}</code>
                    <FormControl
                      type="text"
                      v-model="samples[index - 1]"
                      class="flex-1"
                      :placeholder="__('Sample for {0}').format(token(index))"
                    />
                  </div>
                </div>
              </section>

              <section class="flex flex-col gap-3">
                <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Footer') }}</h3>
                <FormControl v-model="doc.footer" type="text" :maxlength="60" :placeholder="__('Reply STOP to opt out')" />
              </section>

              <section class="flex flex-col gap-3">
                <div class="flex items-center justify-between gap-2">
                  <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Buttons') }}</h3>
                  <Dropdown :options="buttonMenu" align="end">
                    <Button variant="subtle" size="sm" icon-left="lucide-plus" :label="__('Add button')" />
                  </Dropdown>
                </div>
                <p v-if="!doc.buttons?.length" class="text-sm text-ink-gray-5">
                  {{ __('Up to 3 quick replies, 2 website links, 1 phone number and 1 flow.') }}
                </p>
                <div
                  v-for="(button, index) in doc.buttons"
                  :key="button.name || index"
                  class="grid grid-cols-1 gap-2 rounded-4 border border-outline-gray-1 p-3 sm:grid-cols-2"
                >
                  <div class="flex items-center justify-between gap-2 sm:col-span-2">
                    <span class="inline-flex items-center gap-1.5 text-sm font-medium text-ink-gray-7">
                      <span :class="BUTTON_ICONS[button.button_type]" class="size-3.5" aria-hidden="true" />
                      {{ __(button.button_type) }}
                    </span>
                    <div class="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon="lucide-arrow-up"
                        :label="__('Move up')"
                        :disabled="!index"
                        @click="move(index, -1)"
                      />
                      <Button variant="ghost" size="sm" icon="lucide-x" :label="__('Remove')" @click="doc.buttons.splice(index, 1)" />
                    </div>
                  </div>
                  <FormControl v-model="button.button_label" type="text" :label="__('Label')" :maxlength="25" :required="true" />
                  <PhoneField
                    v-if="button.button_type === 'Call Phone'"
                    v-model="button.phone_number"
                    :label="__('Phone number')"
                    required
                  />
                  <template v-else-if="button.button_type === 'Visit Website'">
                    <FormControl v-model="button.url_type" type="select" :label="__('URL type')" :options="['Static', 'Dynamic']" />
                    <FormControl
                      v-model="button.website_url"
                      class="sm:col-span-2"
                      type="url"
                      :label="__('Website URL')"
                      :placeholder="button.url_type === 'Dynamic' ? 'https://example.com/order/{{1}}' : 'https://example.com'"
                    />
                    <FormControl
                      v-if="button.url_type === 'Dynamic'"
                      v-model="button.example_url"
                      class="sm:col-span-2"
                      type="url"
                      :label="__('Example URL')"
                      placeholder="https://example.com/order/1234"
                    />
                  </template>
                  <LinkField
                    v-else-if="button.button_type === 'Flow'"
                    v-model="button.whatsapp_flow"
                    doctype="WhatsApp Flow"
                    :label="__('Flow')"
                  />
                </div>
              </section>

              <section class="flex flex-col gap-3">
                <div>
                  <h3 class="text-base font-semibold text-ink-gray-8">{{ __('Field mapping') }}</h3>
                  <p class="mt-0.5 text-sm text-ink-gray-5">
                    {{ __('Notifications and imported recipient lists fill each variable from these document fields.') }}
                  </p>
                </div>
                <LinkField v-model="doc.for_doctype" doctype="DocType" :label="__('Document type')" />
                <div v-if="count" class="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <div v-for="index in count" :key="index" class="flex items-center gap-2">
                    <code class="w-12 shrink-0 text-sm text-ink-gray-6">{{ token(index) }}</code>
                    <FieldPicker v-model="fields[index - 1]" class="min-w-0 flex-1" :doctype="doc.for_doctype" />
                  </div>
                </div>
              </section>

              <ErrorMessage :message="error" />

              <div class="lg:hidden">
                <p class="mb-2 text-sm font-medium text-ink-gray-5">{{ __('Preview') }}</p>
                <TemplatePreview :template="doc" :samples="samples" :business="business" full />
                <div v-if="name" class="mt-3 flex items-center justify-between text-sm text-ink-gray-6">
                  <span>{{ __('Meta status') }}</span>
                  <CampaignStatusBadge :status="doc.status" />
                </div>
              </div>
            </div>
          </ScrollArea>

          <div class="hidden min-h-0 flex-col gap-3 lg:flex">
            <div class="flex shrink-0 items-center justify-between gap-2">
              <p class="text-sm font-medium text-ink-gray-5">{{ __('Preview') }}</p>
              <CampaignStatusBadge v-if="name" :status="doc.status" />
            </div>
            <TemplatePreview class="min-h-0 flex-1" :template="doc" :samples="samples" :business="business" stretch />
          </div>
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <div>
          <Button v-if="name" variant="ghost" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="remove" />
        </div>
        <div class="flex items-center gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
          <Button
            v-if="tab === 'details'"
            variant="solid"
            :loading="saving"
            :label="name ? __('Save and resubmit') : __('Submit to Meta')"
            @click="save"
          />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { SAMPLE_GROUPS, SAMPLE_TEMPLATES, sampleDoc } from '@/data/sampleTemplates'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import FieldPicker from '@/components/Automation/FieldPicker.vue'
import { computed, nextTick, ref, watch } from 'vue'
import {
  Alert,
  Button,
  Dropdown,
  ErrorMessage,
  FileUploader,
  FormControl,
  FormLabel,
  ScrollArea,
  Skeleton,
  TabButtons,
  Textarea,
  call,
  toast,
} from 'frappe-ui'
import PhoneField from '@/components/Common/PhoneField.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import LinkField from '@/components/Common/LinkField.vue'
import CampaignStatusBadge from './CampaignStatusBadge.vue'
import TemplateAnalytics from './TemplateAnalytics.vue'
import TemplatePreview, { splitList, variableCount } from './TemplatePreview.vue'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
})

const emit = defineEmits(['saved', 'deleted'])

const open = defineModel('open', { type: Boolean, default: false })

const LIMITS = { 'Quick Reply': 3, 'Visit Website': 2, 'Call Phone': 1, Flow: 1 }

const BUTTON_ICONS = {
  'Quick Reply': 'lucide-reply',
  'Call Phone': 'lucide-phone',
  'Visit Website': 'lucide-external-link',
  Flow: 'lucide-list',
}

const categories = ['MARKETING', 'UTILITY', 'AUTHENTICATION', 'TRANSACTIONAL', 'OTP'].map((value) => ({
  label: __(value.charAt(0) + value.slice(1).toLowerCase()),
  value,
}))

const headerTypes = [
  { label: __('None'), value: '' },
  { label: __('Text'), value: 'TEXT' },
  { label: __('Image'), value: 'IMAGE' },
  { label: __('Document'), value: 'DOCUMENT' },
]

const ui = useUI()
const doc = ref({})
const samples = ref([])
const fields = ref([])
const bodyBox = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const tab = ref('details')
const business = ref('')

watch(
  () => doc.value.whatsapp_account,
  async (account) => {
    const filters = account ? { name: account } : { is_default_outgoing: 1 }
    try {
      const row = await call('frappe.client.get_value', {
        doctype: 'OneChat Account',
        filters,
        fieldname: ['verified_name', 'account_name'],
      })
      business.value = row?.verified_name || row?.account_name || ''
    } catch {
      business.value = ''
    }
  },
  { immediate: true },
)

const tabs = [
  { label: __('Details'), value: 'details', iconLeft: 'lucide-pencil' },
  { label: __('Analytics'), value: 'analytics', iconLeft: 'lucide-chart-column' },
]

const warning = computed(() => {
  const row = doc.value
  if (!props.name || !row) return null

  if (String(row.status || '').toUpperCase() === 'REJECTED') {
    return {
      theme: 'red',
      title: __('Meta rejected this template'),
      description: row.rejected_reason
        ? __('Reason: {0}. Edit it and resubmit.').format(humanize(row.rejected_reason))
        : __('Edit it and resubmit to try again.'),
    }
  }
  if (row.quality_score === 'RED') {
    return {
      theme: 'red',
      title: __('Low quality rating'),
      description: __(
        'Many recipients block or report this message. Meta may pause or disable it. Review the content and who receives it.',
      ),
    }
  }
  if (row.quality_score === 'YELLOW') {
    return {
      theme: 'amber',
      title: __('Medium quality rating'),
      description: __('Some recipients block or report this message. Review the content and audience before sending more.'),
    }
  }

  return null
})

const count = computed(() => variableCount(doc.value.template))

const buttonMenu = computed(() =>
  Object.keys(LIMITS).map((type) => ({
    label: __(type),
    icon: BUTTON_ICONS[type],
    disabled: used(type) >= LIMITS[type] || (doc.value.buttons || []).length >= 10,
    onClick: () => addButton(type),
  })),
)

function humanize(value) {
  const text = String(value).replace(/_/g, ' ').toLowerCase()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function token(index) {
  return `{{${index}}}`
}

function used(type) {
  return (doc.value.buttons || []).filter((button) => button.button_type === type).length
}

const sampleKey = ref('')

const sampleOptions = computed(() => [
  { label: __('Blank template'), value: '' },
  ...SAMPLE_GROUPS.flatMap((group) =>
    SAMPLE_TEMPLATES.filter((row) => row.group === group.key).map((row) => ({
      label: `${__(group.label)} · ${__(row.title)}`,
      value: row.key,
    })),
  ),
])

const sampleHint = computed(() => {
  const row = SAMPLE_TEMPLATES.find((item) => item.key === sampleKey.value)
  return row ? __(row.description) : __('Pick a ready-made sample to fill the form, then change anything you like')
})

function applySample(key) {
  const row = SAMPLE_TEMPLATES.find((item) => item.key === key)
  const keep = { language: doc.value.language || 'en', whatsapp_account: doc.value.whatsapp_account }
  doc.value = row ? { ...blank(), ...sampleDoc(row), ...keep } : { ...blank(), ...keep }
  samples.value = row ? [...row.samples] : []
  fields.value = row ? [...row.fields] : []
}

function blank() {
  return {
    template_name: '',
    category: 'MARKETING',
    language: 'en',
    header_type: '',
    template: '',
    footer: '',
    buttons: [],
  }
}

watch(
  open,
  async (value) => {
    if (!value) return

    error.value = ''
    tab.value = 'details'
    if (!props.name) {
      sampleKey.value = ''
      doc.value = blank()
      samples.value = []
      fields.value = []
      return
    }

    loading.value = true
    try {
      const loaded = await call('frappe.client.get', { doctype: 'WhatsApp Templates', name: props.name })
      doc.value = { ...loaded, buttons: loaded.buttons || [] }
      samples.value = loaded.sample_values ? splitList(loaded.sample_values) : []
      fields.value = loaded.field_names ? splitList(loaded.field_names) : []
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

function setHeaderType(value) {
  if (value !== doc.value.header_type) doc.value.sample = null
  doc.value.header_type = value
}

async function addVariable() {
  const next = token(count.value + 1)
  const textarea = bodyBox.value?.querySelector('textarea')
  const text = doc.value.template || ''
  const at = textarea ? textarea.selectionStart : text.length

  doc.value.template = text.slice(0, at) + next + text.slice(at)
  await nextTick()
  if (textarea) {
    textarea.focus()
    textarea.setSelectionRange(at + next.length, at + next.length)
  }
}

function addButton(type) {
  doc.value.buttons.push({
    button_type: type,
    button_label: '',
    is_active: 1,
    url_type: type === 'Visit Website' ? 'Static' : null,
  })
}

function move(index, step) {
  const rows = doc.value.buttons
  const [row] = rows.splice(index, 1)
  rows.splice(index + step, 0, row)
}

function problems() {
  const row = doc.value
  const list = []

  if (!row.template_name?.trim()) list.push(__('Template name is required'))
  if (!row.language) list.push(__('Pick a language'))
  if (!row.template?.trim()) list.push(__('The body cannot be empty'))
  if (row.header_type === 'TEXT' && !row.header?.trim()) list.push(__('Add the header text'))
  if (['IMAGE', 'DOCUMENT'].includes(row.header_type) && !row.sample) list.push(__('Upload a sample for the header'))

  for (let index = 0; index < count.value; index++) {
    if (!samples.value[index]?.trim()) {
      list.push(__('Add a sample value for {0}').format(token(index + 1)))
      break
    }
  }

  for (const button of row.buttons || []) {
    if (!button.button_label?.trim()) list.push(__('Every button needs a label'))
    if (button.button_type === 'Call Phone' && !button.phone_number)
      list.push(__('Add the phone number for {0}').format(button.button_label || __('the call button')))
    if (button.button_type === 'Visit Website' && !button.website_url)
      list.push(__('Add the URL for {0}').format(button.button_label || __('the website button')))
  }

  return [...new Set(list)]
}

function payload() {
  const values = samples.value.slice(0, count.value).map((value) => (value || '').replace(/,/g, ' ').trim())
  const mapped = fields.value.slice(0, count.value).map((value) => (value || '').trim())

  return {
    ...doc.value,
    sample_values: values.join(','),
    field_names: mapped.some(Boolean) ? mapped.join(',') : '',
    buttons: (doc.value.buttons || []).map((button, index) => ({ ...button, sequence: index + 1 })),
  }
}

async function save() {
  const issues = problems()
  if (issues.length) {
    error.value = issues.join('. ')
    return
  }

  saving.value = true
  error.value = ''

  try {
    const saved = props.name
      ? await call('frappe.client.save', { doc: payload() })
      : await call('frappe.client.insert', { doc: { ...payload(), doctype: 'WhatsApp Templates' } })

    toast.success(props.name ? __('Template resubmitted') : __('Template submitted to Meta'))
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
    title: __('Delete this template?'),
    message: __('It is also deleted from your WhatsApp Business account on Meta.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: 'WhatsApp Templates', name: props.name })
      toast.success(__('Deleted'))
      emit('deleted', props.name)
      open.value = false
    },
  })
}
</script>

<style scoped>
.template-body :deep(textarea) {
  min-height: 10rem;
}
</style>

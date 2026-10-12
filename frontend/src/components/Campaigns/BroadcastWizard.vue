<template>
  <ResponsiveDialog v-model:open="open" :title="__('New broadcast')" size="3xl">
    <template #default>
      <ol class="mb-6 flex items-center gap-2">
        <li v-for="(label, index) in steps" :key="label" class="flex min-w-0 flex-1 items-center gap-2">
          <span
            class="flex size-6 shrink-0 items-center justify-center rounded-full text-sm font-medium"
            :class="index <= step ? 'bg-surface-gray-9 text-ink-base' : 'bg-surface-gray-2 text-ink-gray-5'"
          >
            <span v-if="index < step" class="lucide-check size-3.5" aria-hidden="true" />
            <template v-else>{{ index + 1 }}</template>
          </span>
          <TruncatedText
            class="truncate text-sm"
            :class="index === step ? 'font-medium text-ink-gray-9' : 'text-ink-gray-5'"
            :text="label"
          />
          <span v-if="index < steps.length - 1" class="h-px flex-1 bg-surface-gray-3 max-sm:hidden" />
        </li>
      </ol>

      <div v-if="step === 0" class="flex flex-col gap-4">
        <FormControl
          v-model="form.title"
          type="text"
          :label="__('Broadcast name')"
          :required="true"
          :placeholder="__('October newsletter')"
        />

        <FormControl
          v-if="whatsappNumbers.length > 1"
          v-model="form.whatsapp_account"
          type="select"
          :label="__('Send from')"
          :options="numberOptions"
        />

        <div class="flex flex-col gap-2">
          <FormLabel :label="__('Send to')" />
          <TabButtons v-model="form.recipient_type" :options="audienceOptions" />
        </div>

        <template v-if="form.recipient_type === 'Segment'">
          <FormControl
            v-model="form.segment"
            type="select"
            :label="__('Segment')"
            :options="segmentOptions"
            :placeholder="segmentsLoading ? __('Loading segments…') : __('Pick a segment')"
          />
          <ErrorMessage v-if="segmentsError" :message="segmentsError" />
          <p v-else-if="!segmentsLoading && !segments.length" class="text-sm text-ink-gray-5">
            {{ __('No segments yet. Create one under Contacts → Segments.') }}
          </p>
          <p v-else-if="selectedSegment" class="text-sm text-ink-gray-6">
            {{
              __(
                '{0} contacts match right now. Opted-out contacts are skipped, and the segment is read again when the broadcast sends.',
              ).format(formatNumber(selectedSegment.member_count))
            }}
          </p>
        </template>

        <template v-else-if="form.recipient_type === 'Recipient List'">
          <LinkField v-model="form.recipient_list" doctype="WhatsApp Recipient List" :label="__('Recipient list')" />
          <p v-if="form.recipient_list" class="text-sm text-ink-gray-6">
            <template v-if="listInfo.loading">{{ __('Counting recipients…') }}</template>
            <template v-else>{{ __('{0} recipients in this list').format(formatNumber(listInfo.count)) }}</template>
          </p>
        </template>

        <div v-else class="flex flex-col gap-1.5">
          <Textarea
            v-model="form.numbers"
            :rows="8"
            :placeholder="
              __('One per line: number, name, then values for the template variables') +
              '\n+919876543210, Asha, ORD-1042\n+971501234567, Omar'
            "
          />
          <p class="text-sm text-ink-gray-5">
            {{ __('{0} valid numbers').format(people.length) }} · {{ __('Include the country code. Duplicates are skipped.') }}
          </p>
        </div>
      </div>

      <div v-else-if="step === 1" class="grid gap-6 md:grid-cols-[minmax(0,1fr)_280px]">
        <div class="flex min-w-0 flex-col gap-4">
          <LinkField
            v-model="form.template"
            doctype="WhatsApp Templates"
            :filters="{ status: 'APPROVED' }"
            :label="__('Approved template')"
            :description="__('Only templates approved by Meta can start a conversation.')"
          />

          <div v-if="template && keys.length" class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-3">
            <p class="text-sm font-medium text-ink-gray-7">{{ __('Variables') }}</p>
            <p v-if="form.recipient_type === 'Recipient List'" class="text-sm text-ink-gray-5">
              {{ __('Saved recipient data fills these. Missing keys are sent empty.') }}
            </p>
            <p v-else-if="form.recipient_type === 'Segment'" class="text-sm text-ink-gray-5">
              {{ __('Contact details fill these: {0}.').format(SEGMENT_FIELDS.join(', ')) }}
            </p>
            <p v-else class="text-sm text-ink-gray-5">
              {{ __('Values pasted after the name win; otherwise these defaults are used.') }}
            </p>
            <div v-for="(key, index) in keys" :key="index" class="flex items-center gap-2">
              <code class="w-12 shrink-0 text-sm text-ink-gray-6">{{ token(index + 1) }}</code>
              <template v-if="form.recipient_type === 'Recipient List'">
                <TruncatedText class="flex-1 truncate text-sm text-ink-gray-7" :text="key" />
                <Badge
                  :theme="listInfo.fields.includes(key) ? 'green' : 'amber'"
                  :label="listInfo.fields.includes(key) ? __('In list data') : __('Not in list data')"
                />
              </template>
              <template v-else-if="form.recipient_type === 'Segment'">
                <TruncatedText class="flex-1 truncate text-sm text-ink-gray-7" :text="key" />
                <Badge
                  :theme="SEGMENT_FIELDS.includes(key) ? 'green' : 'amber'"
                  :label="SEGMENT_FIELDS.includes(key) ? __('From contact') : __('Not a contact field')"
                />
              </template>
              <FormControl type="text" v-else v-model="form.values[index]" class="flex-1" :placeholder="key" />
            </div>
          </div>

          <div class="flex flex-col gap-3 rounded-4 border border-outline-gray-1 p-3">
            <Switch
              v-model="form.ab_test"
              :label="__('A/B test')"
              :description="__('Send two templates to a small test group, then send the better one to everyone else.')"
            />
            <template v-if="form.ab_test">
              <LinkField
                v-model="form.template_b"
                doctype="WhatsApp Templates"
                :filters="{ status: 'APPROVED' }"
                :label="__('Template B')"
              />
              <div class="grid gap-3 sm:grid-cols-3">
                <Select v-model="form.ab_test_percent" :label="__('Test group')" :options="TEST_SIZES" />
                <Select v-model="form.ab_metric" :label="__('Winner by')" :options="METRICS" />
                <Select v-model="form.ab_wait_hours" :label="__('Decide after')" :options="WAITS" />
              </div>
              <p class="text-sm text-ink-gray-5">
                {{ abSummary }}
              </p>
            </template>
          </div>
        </div>

        <div>
          <div class="mb-2 flex items-center justify-between gap-2">
            <p class="text-sm font-medium text-ink-gray-5">{{ __('Preview') }}</p>
            <TabButtons
              v-if="form.ab_test && templateB"
              v-model="previewing"
              :options="[
                { label: 'A', value: 'A' },
                { label: 'B', value: 'B' },
              ]"
            />
          </div>
          <TemplatePreview v-if="form.ab_test && previewing === 'B' && templateB" :template="templateB" :samples="previewValues" />
          <TemplatePreview v-else-if="template" :template="template" :samples="previewValues" />
          <div
            v-else
            class="flex h-48 items-center justify-center rounded-7 border border-dashed border-outline-gray-2 text-sm text-ink-gray-5"
          >
            {{ __('Pick a template') }}
          </div>
        </div>
      </div>

      <div v-else class="flex flex-col gap-5">
        <dl class="grid grid-cols-1 gap-3 rounded-5 bg-surface-gray-1 p-4 sm:grid-cols-3">
          <div>
            <dt class="text-sm text-ink-gray-5">{{ __('Name') }}</dt>
            <TruncatedText as="dd" class="truncate text-base font-medium text-ink-gray-9" :text="form.title" />
          </div>
          <div>
            <dt class="text-sm text-ink-gray-5">{{ __('Audience') }}</dt>
            <dd class="truncate text-base font-medium text-ink-gray-9">
              {{ __('{0} recipients').format(formatNumber(audienceCount)) }}
              <span v-if="form.recipient_type === 'Recipient List'" class="font-normal text-ink-gray-5">· {{ form.recipient_list }}</span>
              <span v-else-if="form.recipient_type === 'Segment'" class="font-normal text-ink-gray-5">· {{ form.segment }}</span>
            </dd>
          </div>
          <div>
            <dt class="text-sm text-ink-gray-5">{{ form.ab_test ? __('Templates') : __('Template') }}</dt>
            <dd class="truncate text-base font-medium text-ink-gray-9">
              {{ template?.template_name || form.template }}
              <template v-if="form.ab_test"> · {{ templateB?.template_name || form.template_b }}</template>
            </dd>
          </div>
        </dl>
        <p v-if="form.ab_test" class="-mt-2 text-sm text-ink-gray-6">{{ abSummary }}</p>

        <div class="flex flex-col gap-2">
          <FormLabel :label="__('When')" />
          <TabButtons v-model="form.when" :options="whenOptions" />
        </div>

        <FormControl
          v-if="form.when === 'later'"
          v-model="form.scheduled_time"
          type="datetime"
          :label="__('Send at')"
          :description="__('The broadcast stays a draft until then.')"
        />

        <div v-if="!form.ab_test" class="rounded-5 border border-outline-gray-2 px-3 py-2.5">
          <Switch
            v-model="form.smart_send"
            :label="__('Smart send time')"
            :description="
              __(
                'Each person gets it at the hour they usually message you, within 24 hours. People who have never written in get it right away.',
              )
            "
          />
        </div>

        <Alert
          v-if="form.when !== 'later'"
          theme="amber"
          :title="form.smart_send ? __('Sending starts as soon as you confirm') : __('Messages go out as soon as you confirm')"
          :description="__('WhatsApp charges per conversation. Sent messages cannot be recalled.')"
        />
      </div>

      <ErrorMessage :message="error" class="mt-4" />
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <Button v-if="step" variant="ghost" icon-left="lucide-arrow-left" :label="__('Back')" @click="step -= 1" />
        <span v-else />
        <div class="flex items-center gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
          <Button v-if="step < 2" variant="solid" icon-right="lucide-arrow-right" :label="__('Next')" @click="next" />
          <Button
            v-else
            variant="solid"
            :icon-left="form.when === 'later' ? 'lucide-calendar-clock' : 'lucide-send'"
            :loading="saving"
            :label="form.when === 'later' ? __('Schedule') : __('Send now')"
            @click="finish"
          />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, ref, watch } from 'vue'
import {
  Alert,
  Badge,
  Button,
  ErrorMessage,
  FormControl,
  FormLabel,
  Select,
  Switch,
  TabButtons,
  Textarea,
  call,
  dayjs,
  toast,
} from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { useNumbers } from '@/stores/numbers'
import LinkField from '@/components/Common/LinkField.vue'
import TemplatePreview, { splitList, variableCount } from './TemplatePreview.vue'
import { errorMessage, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({ segment: { type: String, default: null } })
const emit = defineEmits(['created'])

const open = defineModel('open', { type: Boolean, default: false })

const steps = [__('Audience'), __('Message'), __('Review')]

const SEGMENT_FIELDS = ['contact_name', 'mobile_no', 'email', 'favourite_category', 'value_group', 'lifetime_value', 'engagement_score']

const audienceOptions = [
  { label: __('Segment'), value: 'Segment', iconLeft: 'lucide-users-round' },
  { label: __('Recipient list'), value: 'Recipient List', iconLeft: 'lucide-list-checks' },
  { label: __('Individual numbers'), value: 'Individual', iconLeft: 'lucide-phone' },
]

const whenOptions = [
  { label: __('Send now'), value: 'now', iconLeft: 'lucide-send' },
  { label: __('Schedule'), value: 'later', iconLeft: 'lucide-calendar-clock' },
]

const step = ref(0)
const saving = ref(false)
const error = ref('')
const template = ref(null)
const templateB = ref(null)
const previewing = ref('A')

const TEST_SIZES = [10, 20, 30, 50].map((value) => ({ label: __('{0}% of recipients').format(value), value }))
const METRICS = [
  { label: __('Replies'), value: 'Replies' },
  { label: __('Reads'), value: 'Reads' },
]
const WAITS = [2, 4, 8, 24].map((value) => ({ label: __('{0} hours').format(value), value }))
const form = reactive(blank())
const numbers = useNumbers()
if (!numbers.loaded) numbers.load()
const whatsappNumbers = computed(() => numbers.rows.filter((row) => row.channel !== 'Instagram'))
const numberOptions = computed(() => [
  { label: __('Default number'), value: '' },
  ...whatsappNumbers.value.map((row) => ({ label: row.phone ? `${row.label} · ${row.phone}` : row.label, value: row.name })),
])
const listInfo = reactive({ loading: false, count: 0, fields: [] })
const segments = ref([])
const segmentsLoading = ref(false)

const segmentOptions = computed(() =>
  segments.value.map((row) => ({ label: `${row.segment_name} (${formatNumber(row.member_count)})`, value: row.name })),
)
const selectedSegment = computed(() => segments.value.find((row) => row.name === form.segment))

const segmentsError = ref('')

async function loadSegments() {
  segmentsLoading.value = true
  segmentsError.value = ''
  try {
    segments.value = await call('onechat.inbox.segments.segments')
  } catch (err) {
    segments.value = []
    segmentsError.value = errorMessage(err)
  } finally {
    segmentsLoading.value = false
  }
}

function blank() {
  return {
    title: '',
    whatsapp_account: '',
    recipient_type: 'Recipient List',
    recipient_list: null,
    segment: null,
    ab_test: false,
    template_b: null,
    ab_test_percent: 20,
    ab_metric: 'Replies',
    ab_wait_hours: 4,
    numbers: '',
    template: null,
    values: [],
    when: 'now',
    scheduled_time: null,
    smart_send: false,
  }
}

function token(index) {
  return `{{${index}}}`
}

const keys = computed(() => {
  if (!template.value) return []

  const count = variableCount(template.value.template)
  const source = splitList(template.value.field_names || template.value.sample_values)

  return Array.from({ length: count }, (item, index) => source[index] || `var_${index + 1}`)
})

const people = computed(() => {
  const seen = new Set()
  const out = []

  for (const line of form.numbers.split(/\r?\n/)) {
    const [number, name, ...values] = line.split(/[,\t;]/).map((part) => part.trim())
    const mobile = String(number || '').replace(/[^\d+]/g, '')
    if (mobile.replace('+', '').length < 6 || seen.has(mobile)) continue

    seen.add(mobile)
    out.push({ mobile, name: name || '', values })
  }

  return out
})

const abSummary = computed(() => {
  const test = Math.max(10, Math.round((audienceCount.value * Number(form.ab_test_percent || 20)) / 100))
  const half = Math.floor(Math.min(test, audienceCount.value) / 2)
  return __('{0} get A and {0} get B. After {1} hours the one with more {2} goes to the other {3}.').format(
    formatNumber(half),
    form.ab_wait_hours,
    form.ab_metric === 'Reads' ? __('reads') : __('replies'),
    formatNumber(Math.max(audienceCount.value - half * 2, 0)),
  )
})

const audienceCount = computed(() => {
  if (form.recipient_type === 'Segment') return selectedSegment.value?.member_count || 0
  return form.recipient_type === 'Recipient List' ? listInfo.count : people.value.length
})

const previewValues = computed(() => {
  const samples = splitList(template.value?.sample_values)
  const first = form.recipient_type === 'Individual' ? people.value[0]?.values || [] : []

  return keys.value.map((key, index) => first[index] || form.values[index] || samples[index] || '')
})

watch(
  open,
  (value) => {
    if (!value) return

    Object.assign(form, blank())
    if (props.segment) Object.assign(form, { recipient_type: 'Segment', segment: props.segment })
    step.value = 0
    error.value = ''
    template.value = null
    loadSegments()
  },
  { immediate: true },
)

watch(
  () => props.segment,
  (value) => {
    if (open.value && value) Object.assign(form, { recipient_type: 'Segment', segment: value })
  },
)

watch(
  () => form.recipient_type,
  (value) => {
    if (open.value && value === 'Segment' && !segments.value.length && !segmentsLoading.value) loadSegments()
  },
)

watch(
  () => form.recipient_list,
  async (name) => {
    listInfo.count = 0
    listInfo.fields = []
    if (!name) return

    listInfo.loading = true
    try {
      const [counts, list] = await Promise.all([
        call('onechat.campaigns.broadcasts.recipient_counts', { names: [name] }),
        call('frappe.client.get_value', { doctype: 'WhatsApp Recipient List', filters: { name }, fieldname: ['data_fields'] }),
      ])
      listInfo.count = counts[name] || 0
      listInfo.fields = parseKeys(list?.data_fields)
    } catch {
      listInfo.count = 0
    } finally {
      listInfo.loading = false
    }
  },
)

watch(
  () => form.template_b,
  async (name) => {
    templateB.value = null
    if (!name) return
    try {
      templateB.value = await call('frappe.client.get', { doctype: 'WhatsApp Templates', name })
    } catch (err) {
      error.value = errorMessage(err)
    }
  },
)

watch(
  () => form.template,
  async (name) => {
    template.value = null
    form.values = []
    if (!name) return

    try {
      template.value = await call('frappe.client.get', { doctype: 'WhatsApp Templates', name })
      form.values = splitList(template.value.sample_values).slice(0, keys.value.length)
    } catch (err) {
      error.value = errorMessage(err)
    }
  },
)

function parseKeys(value) {
  try {
    const list = JSON.parse(value || '[]')
    return Array.isArray(list) ? list.map((key) => String(key).toLowerCase().replace(/ /g, '_')) : []
  } catch {
    return []
  }
}

function check() {
  if (step.value === 0) {
    if (!form.title.trim()) return __('Give the broadcast a name')
    if (form.recipient_type === 'Recipient List' && !form.recipient_list) return __('Pick a recipient list')
    if (form.recipient_type === 'Recipient List' && !listInfo.loading && !listInfo.count) return __('That list has no recipients')
    if (form.recipient_type === 'Individual' && !people.value.length) return __('Add at least one number')
    if (form.recipient_type === 'Segment' && !form.segment) return __('Pick a segment')
    if (form.recipient_type === 'Segment' && selectedSegment.value && !selectedSegment.value.member_count)
      return __('No contacts match that segment')
  }

  if (step.value === 1 && !template.value) return __('Pick an approved template')
  if (step.value === 1 && form.ab_test && !form.template_b) return __('Pick template B')
  if (step.value === 1 && form.ab_test && form.template_b === form.template) return __('Pick a different template for B')
  if (step.value === 1 && form.ab_test && audienceCount.value < 20) return __('A/B tests need at least 20 recipients')

  if (step.value === 2 && form.when === 'later') {
    if (!form.scheduled_time) return __('Pick a time to send')
    if (dayjs(form.scheduled_time).isBefore(dayjs())) return __('Pick a time in the future')
  }

  return ''
}

function next() {
  error.value = check()
  if (!error.value) step.value += 1
}

function recipients() {
  return people.value.map((person) => ({
    mobile_number: person.mobile,
    recipient_name: person.name,
    recipient_data: JSON.stringify(
      Object.fromEntries(keys.value.map((key, index) => [key, person.values[index] || form.values[index] || ''])),
    ),
  }))
}

async function finish() {
  error.value = check()
  if (error.value) return

  saving.value = true
  try {
    const individual = form.recipient_type === 'Individual'
    const doc = await call('frappe.client.insert', {
      doc: {
        doctype: 'Bulk WhatsApp Message',
        title: form.title.trim(),
        whatsapp_account: form.whatsapp_account || null,
        recipient_type: form.recipient_type,
        recipient_list: form.recipient_type === 'Recipient List' ? form.recipient_list : null,
        segment: form.recipient_type === 'Segment' ? form.segment : null,
        recipients: individual ? recipients() : [],
        use_template: 1,
        ab_test: form.ab_test ? 1 : 0,
        template_b: form.ab_test ? form.template_b : null,
        ab_test_percent: Number(form.ab_test_percent) || 20,
        ab_metric: form.ab_metric || 'Replies',
        ab_wait_hours: Number(form.ab_wait_hours) || 4,
        template: form.template,
        template_variables: JSON.stringify(Object.fromEntries(keys.value.map((key) => [key, `recipient.${key}`]))),
        scheduled_time: form.when === 'later' ? form.scheduled_time : null,
        smart_send: form.smart_send && !form.ab_test ? 1 : 0,
      },
    })

    if (form.when === 'now') {
      await call('frappe.client.submit', { doc })
      toast.success(__('Broadcast queued'))
    } else {
      toast.success(__('Broadcast scheduled for {0}').format(dayjs(form.scheduled_time).format('D MMM, h:mm a')))
    }

    emit('created', doc.name)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}
</script>

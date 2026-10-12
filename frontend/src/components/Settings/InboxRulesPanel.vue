<template>
  <SettingsHeader>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Inbox rules') }}</h2>
        <p class="mt-1 text-base text-ink-gray-6">
          {{ __('Who picks up new conversations, and what customers hear when you are closed') }}
        </p>
      </div>
      <Button variant="solid" :label="__('Save')" :loading="saving" :disabled="loading || !dirty || !!problem" @click="save" />
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <div v-if="loading" class="flex flex-col gap-3 pt-6">
      <Skeleton v-for="row in 4" :key="row" class="h-12 w-full" />
    </div>

    <template v-else>
      <p class="mt-6 text-sm font-medium text-ink-gray-5">{{ __('Visibility') }}</p>
      <div class="divide-y divide-outline-gray-1">
        <SettingsRow :title="__('Agents can see')" :description="visibilityHint">
          <Select class="w-64" :options="VISIBILITY_OPTIONS" v-model="form.agent_visibility" />
        </SettingsRow>
      </div>

      <p class="mt-6 text-sm font-medium text-ink-gray-5">{{ __('Assignment') }}</p>
      <div class="divide-y divide-outline-gray-1" data-tour="assignment">
        <SettingsRow :title="__('Assign automatically')" :description="__('Give unassigned conversations an owner as they come in')">
          <Switch v-model="form.auto_assign" />
        </SettingsRow>
        <template v-if="form.auto_assign">
          <SettingsRow :title="__('Only available agents')" :description="__('Skip agents who have set themselves away')">
            <Switch v-model="form.assign_only_available" />
          </SettingsRow>
          <SettingsRow :title="__('Assign on')" :description="__('When a conversation gets an owner')">
            <Select class="w-64" :options="ASSIGN_OPTIONS" v-model="form.assign_on" />
          </SettingsRow>
          <SettingsRow :title="__('Assign to')" :description="__('Share conversations between everyone, or only one team')">
            <Select class="w-64" :options="teamOptions" v-model="form.assign_team" />
          </SettingsRow>
        </template>
        <SettingsRow :title="__('Method')" :description="methodHint">
          <Select class="w-64" :options="METHOD_OPTIONS" v-model="form.assign_method" />
        </SettingsRow>
        <SettingsRow
          :title="__('Max open chats per agent')"
          :description="__('Skip agents who already have this many open or pending chats. 0 means no limit.')"
        >
          <FormControl v-model="form.assign_capacity" type="number" min="0" class="w-24" />
        </SettingsRow>
        <SettingsRow
          :title="__('Keep customers with their last agent')"
          :description="__('A returning customer goes back to whoever handled them last, if that agent can take the chat')"
        >
          <Switch v-model="form.assign_sticky" />
        </SettingsRow>
        <SettingsRow
          :title="__('Release chats when resolved')"
          :description="__('Clear the owner on resolve, so the next conversation is assigned again')"
        >
          <Switch v-model="form.assign_release_on_resolve" />
        </SettingsRow>
      </div>
      <p class="mt-2 text-xs text-ink-gray-5">
        {{ __('Method, limit and last agent also apply to flow steps that assign the next available agent.') }}
      </p>

      <p class="mt-8 text-sm font-medium text-ink-gray-5">{{ __('Reply time') }}</p>
      <div class="divide-y divide-outline-gray-1">
        <SettingsRow
          :title="__('Track reply time')"
          :description="__('Chats waiting too long for a reply show as Overdue, and the owner (or admins) are alerted once')"
        >
          <Switch v-model="form.sla_enabled" />
        </SettingsRow>
        <template v-if="form.sla_enabled">
          <SettingsRow :title="__('Reply within')" :description="__('Minutes after the customer writes')">
            <div class="flex items-center gap-2">
              <FormControl v-model="form.sla_first_response_minutes" type="number" min="1" class="w-24" />
              <span class="text-sm text-ink-gray-6">{{ __('minutes') }}</span>
            </div>
          </SettingsRow>
          <SettingsRow
            :title="__('Count business hours only')"
            :description="__('A message at night is due the same number of minutes after you open')"
          >
            <Switch v-model="form.sla_business_hours_only" />
          </SettingsRow>
        </template>
      </div>

      <p class="mt-8 text-sm font-medium text-ink-gray-5">{{ __('Resolving chats') }}</p>
      <div class="divide-y divide-outline-gray-1">
        <SettingsRow
          :title="__('Ask for a reason')"
          :description="__('Agents pick why a chat is resolved. It is saved on the conversation and shows in reports.')"
        >
          <Switch v-model="form.resolve_require_reason" />
        </SettingsRow>
        <div v-if="form.resolve_require_reason" class="py-3.5">
          <FormControl
            v-model="form.resolve_reasons"
            type="textarea"
            :rows="4"
            :label="__('Reasons')"
            :description="__('One per line. Leave empty to let agents type their own.')"
          />
        </div>
        <SettingsRow
          :title="__('Require a note')"
          :description="
            __('Agents must write what was done for the customer before a chat can be resolved. The note is saved on the conversation.')
          "
        >
          <Switch v-model="form.resolve_require_note" />
        </SettingsRow>
        <SettingsRow :title="__('When the customer is waiting for a reply')" :description="waitingHint">
          <Select class="w-48" :options="WAITING_OPTIONS" v-model="form.resolve_when_waiting" />
        </SettingsRow>
        <SettingsRow
          :title="__('Only the assigned agent can resolve')"
          :description="__('Others, except admins, cannot resolve a chat someone else owns.')"
        >
          <Switch v-model="form.resolve_only_owner" />
        </SettingsRow>
        <SettingsRow
          :title="__('New chats from templates start as')"
          :description="
            __('When your broadcast, notification or flow messages a new number. The chat becomes Open as soon as the customer replies.')
          "
        >
          <Select class="w-48" :options="OUTGOING_OPTIONS" v-model="form.outgoing_new_status" />
        </SettingsRow>
      </div>

      <p class="mt-8 text-sm font-medium text-ink-gray-5">{{ __('Satisfaction survey') }}</p>
      <div class="divide-y divide-outline-gray-1">
        <SettingsRow
          :title="__('Ask for a rating when a chat is resolved')"
          :description="__('Sends Great, Okay and Poor buttons if the customer wrote in the last 24 hours. Scores show in Insights.')"
        >
          <Switch v-model="form.csat_enabled" />
        </SettingsRow>
        <div v-if="form.csat_enabled" class="py-3.5">
          <FormControl
            v-model="form.csat_message"
            type="textarea"
            :rows="2"
            :label="__('Question')"
            :placeholder="__('How did we do today? Tap a rating below.')"
          />
        </div>
      </div>

      <div class="mt-8 flex items-center justify-between gap-3">
        <p class="text-sm font-medium text-ink-gray-5">{{ __('Business hours') }}</p>
        <Badge v-if="status" variant="subtle" :theme="statusTheme" :label="statusLabel" />
      </div>
      <div class="divide-y divide-outline-gray-1" data-tour="business-hours">
        <SettingsRow :title="__('Use business hours')" :description="__('Outside these hours customers get the away message')">
          <Switch v-model="form.business_hours_enabled" />
        </SettingsRow>
      </div>

      <template v-if="form.business_hours_enabled">
        <div class="mt-2 flex flex-wrap items-center justify-between gap-2">
          <p class="text-sm text-ink-gray-5">
            {{ __('Times are in {0}').format(status?.timezone || __('the system timezone')) }}
            <span v-if="nextChangeLabel"> · {{ nextChangeLabel }}</span>
          </p>
          <Button variant="ghost" size="sm" icon-left="lucide-copy" :label="__('Copy Monday to weekdays')" @click="copyMonday" />
        </div>

        <div class="mt-2 divide-y divide-outline-gray-1 rounded-4 border border-outline-gray-2">
          <div v-for="day in week" :key="day.weekday" class="flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-start">
            <div class="flex h-7 w-36 shrink-0 items-center gap-2">
              <Switch
                v-model="day.open"
                :aria-label="__('Open on {0}').format(__(day.weekday))"
                @update:model-value="(value) => toggleDay(day, value)"
              />
              <span class="text-base text-ink-gray-8">{{ __(day.weekday) }}</span>
            </div>

            <p v-if="!day.open" class="flex h-7 items-center text-base text-ink-gray-5">{{ __('Closed') }}</p>

            <div v-else class="flex min-w-0 flex-1 flex-col gap-2">
              <div v-for="(range, index) in day.ranges" :key="index" class="flex flex-wrap items-center gap-2">
                <TimePicker v-model="range.open_time" class="w-28" :placeholder="__('Opens')" />
                <span class="text-sm text-ink-gray-5">{{ __('to') }}</span>
                <TimePicker v-model="range.close_time" class="w-28" :placeholder="__('Closes')" />
                <Button variant="ghost" icon="lucide-x" :aria-label="__('Remove these hours')" @click="removeRange(day, index)" />
                <span v-if="!validRange(range)" class="text-sm text-ink-red-3">
                  {{ __('Closing time must be after opening time') }}
                </span>
              </div>
              <div>
                <Button variant="ghost" size="sm" icon-left="lucide-plus" :label="__('Add hours')" @click="addRange(day)" />
              </div>
            </div>
          </div>
        </div>
        <p class="mt-2 text-sm text-ink-gray-5">{{ __('Use 00:00 as the closing time to stay open until midnight.') }}</p>
      </template>

      <p class="mt-8 text-sm font-medium text-ink-gray-5">{{ __('Away message') }}</p>
      <div class="mt-2 flex flex-col gap-4">
        <FormControl
          type="textarea"
          :rows="3"
          :label="__('Message')"
          :description="__('Sent to customers who write outside business hours')"
          v-model="form.away_message"
        />
        <FormControl
          type="number"
          class="w-48"
          :label="__('Cooldown (hours)')"
          :description="__('Send it to the same person at most once in this many hours')"
          v-model="form.away_cooldown_hours"
        />
      </div>
    </template>
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Badge,
  Button,
  ErrorMessage,
  FormControl,
  Select,
  SettingsBody,
  SettingsHeader,
  SettingsRow,
  Skeleton,
  Switch,
  TimePicker,
  call,
  dayjs,
  toast,
} from 'frappe-ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const SETTINGS = 'OneChat Settings'
const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const METHOD_OPTIONS = [
  { label: __('Round robin'), value: 'Round robin', description: __('Take turns, whoever waited longest goes next') },
  { label: __('Least busy'), value: 'Least busy', description: __('Fewest open and pending chats goes next') },
]

const ASSIGN_OPTIONS = [
  { label: __('New conversations'), value: 'New conversations' },
  { label: __('Every unassigned incoming message'), value: 'Every unassigned incoming message' },
]

const VISIBILITY_OPTIONS = [
  { label: __('All conversations'), value: 'All conversations', description: __('Every agent sees every chat') },
  {
    label: __("Their team's conversations"),
    value: 'Team conversations',
    description: __("Their own, their teams', and unassigned chats"),
  },
  { label: __('Only their own'), value: 'Own conversations', description: __('Chats assigned to them, plus unassigned ones') },
]

const VISIBILITY_HINTS = {
  'All conversations': 'Every agent can open and reply to every chat. Admins and managers always see everything.',
  'Team conversations':
    'Agents see chats assigned to them or to their teams, plus unassigned chats so they can pick up new ones. Admins and managers see everything.',
  'Own conversations':
    'Agents see only chats assigned to them, plus unassigned chats so they can pick up new ones. Admins and managers see everything.',
}

const form = reactive({
  agent_visibility: 'All conversations',
  assign_method: 'Round robin',
  assign_capacity: 0,
  assign_sticky: false,
  assign_release_on_resolve: false,
  auto_assign: false,
  assign_only_available: true,
  assign_on: 'New conversations',
  assign_team: '',
  business_hours_enabled: false,
  away_message: '',
  away_cooldown_hours: 12,
  sla_enabled: false,
  sla_first_response_minutes: 30,
  sla_business_hours_only: true,
  csat_enabled: false,
  csat_message: '',
  resolve_require_reason: false,
  resolve_require_note: false,
  resolve_reasons: '',
  resolve_when_waiting: 'Allow',
  resolve_only_owner: false,
  outgoing_new_status: 'Pending',
})

const OUTGOING_OPTIONS = [
  { label: __('Pending (recommended)'), value: 'Pending' },
  { label: __('Open'), value: 'Open' },
  { label: __('Resolved'), value: 'Resolved' },
]

const WAITING_OPTIONS = [
  { label: __('Allow'), value: 'Allow' },
  { label: __('Ask to confirm'), value: 'Ask to confirm' },
  { label: __('Block'), value: 'Block' },
]

const waitingHint = computed(
  () =>
    ({
      Allow: __('Agents can resolve even if the customer wrote last.'),
      'Ask to confirm': __('Agents see a warning and must confirm.'),
      Block: __('Agents must reply first. Admins can still resolve.'),
    }[form.resolve_when_waiting] || ''),
)
const week = ref(emptyWeek())
const teams = ref([])

const teamOptions = computed(() => [
  { label: __('All agents'), value: '' },
  ...teams.value.map((team) => ({ label: __('{0} team ({1})').format(team.team_name, team.members.length), value: team.name })),
])

const methodHint = computed(() =>
  form.assign_method === 'Least busy'
    ? __('The agent with the fewest open and pending chats gets the next one. Ties take turns.')
    : __('Agents take turns. Whoever was assigned longest ago goes next.'),
)

const status = ref(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const snapshot = ref('')

const dirty = computed(() => snapshot.value !== serialize())

const problem = computed(
  () => form.business_hours_enabled && week.value.some((day) => day.open && day.ranges.some((range) => !validRange(range))),
)

const statusTheme = computed(() => {
  if (!status.value.business_hours_enabled) return 'gray'
  return status.value.open_now ? 'green' : 'amber'
})

const statusLabel = computed(() => {
  if (!status.value.business_hours_enabled) return __('Always open')
  return status.value.open_now ? __('Open now') : __('Closed now')
})

const nextChangeLabel = computed(() => {
  const next = status.value?.business_hours_enabled && status.value.next_change
  if (!next) return ''

  const when = dayjs(next).format('ddd h:mm a')
  return status.value.open_now ? __('Closes {0}').format(when) : __('Opens {0}').format(when)
})

function emptyWeek() {
  return WEEKDAYS.map((weekday) => ({ weekday, open: false, ranges: [] }))
}

function hhmm(value) {
  if (!value) return ''

  const [hours = '0', minutes = '0'] = String(value).split(':')
  return `${hours.padStart(2, '0')}:${minutes.padStart(2, '0')}`
}

function toMinutes(value) {
  const [hours, minutes] = hhmm(value).split(':').map(Number)
  return hours * 60 + minutes
}

function validRange(range) {
  if (!range.open_time || !range.close_time) return false

  const close = toMinutes(range.close_time) || 1440
  return close > toMinutes(range.open_time)
}

function buildWeek(rows) {
  const days = emptyWeek()
  for (const row of rows || []) {
    const day = days.find((item) => item.weekday === row.weekday)
    if (!day) continue
    day.open = true
    day.ranges.push({ open_time: hhmm(row.open_time), close_time: hhmm(row.close_time) })
  }
  for (const day of days) day.ranges.sort((a, b) => toMinutes(a.open_time) - toMinutes(b.open_time))

  return days
}

function hourRows() {
  return week.value.flatMap((day) =>
    day.open
      ? day.ranges.map((range) => ({
          weekday: day.weekday,
          open_time: `${hhmm(range.open_time)}:00`,
          close_time: `${hhmm(range.close_time)}:00`,
        }))
      : [],
  )
}

const visibilityHint = computed(() => __(VISIBILITY_HINTS[form.agent_visibility] || VISIBILITY_HINTS['All conversations']))

function values() {
  return {
    agent_visibility: form.agent_visibility || 'All conversations',
    assign_method: form.assign_method || 'Round robin',
    assign_capacity: Math.max(0, parseInt(form.assign_capacity, 10) || 0),
    assign_sticky: form.assign_sticky ? 1 : 0,
    assign_release_on_resolve: form.assign_release_on_resolve ? 1 : 0,
    auto_assign: form.auto_assign ? 1 : 0,
    assign_only_available: form.assign_only_available ? 1 : 0,
    assign_on: form.assign_on || 'New conversations',
    assign_team: form.assign_team || null,
    business_hours_enabled: form.business_hours_enabled ? 1 : 0,
    away_message: form.away_message || '',
    away_cooldown_hours: Math.max(0, parseInt(form.away_cooldown_hours, 10) || 0),
    sla_enabled: form.sla_enabled ? 1 : 0,
    sla_first_response_minutes: Math.max(1, parseInt(form.sla_first_response_minutes, 10) || 30),
    sla_business_hours_only: form.sla_business_hours_only ? 1 : 0,
    csat_enabled: form.csat_enabled ? 1 : 0,
    csat_message: form.csat_message || '',
    resolve_require_reason: form.resolve_require_reason ? 1 : 0,
    resolve_require_note: form.resolve_require_note ? 1 : 0,
    resolve_reasons: form.resolve_reasons || '',
    resolve_when_waiting: form.resolve_when_waiting || 'Allow',
    resolve_only_owner: form.resolve_only_owner ? 1 : 0,
    outgoing_new_status: form.outgoing_new_status || 'Pending',
    business_hours: hourRows(),
  }
}

function serialize() {
  return JSON.stringify(values())
}

function toggleDay(day, open) {
  if (open && !day.ranges.length) day.ranges.push({ open_time: '09:00', close_time: '17:00' })
}

function addRange(day) {
  const last = day.ranges[day.ranges.length - 1]
  day.ranges.push(last ? { open_time: last.close_time || '13:00', close_time: '' } : { open_time: '09:00', close_time: '17:00' })
}

function removeRange(day, index) {
  day.ranges.splice(index, 1)
  if (!day.ranges.length) day.open = false
}

function copyMonday() {
  const monday = week.value[0]
  for (const day of week.value.slice(1, 5)) {
    day.open = monday.open
    day.ranges = monday.ranges.map((range) => ({ ...range }))
  }
}

function apply(doc) {
  form.agent_visibility = doc.agent_visibility || 'All conversations'
  form.assign_method = doc.assign_method || 'Round robin'
  form.assign_capacity = doc.assign_capacity || 0
  form.assign_sticky = !!doc.assign_sticky
  form.assign_release_on_resolve = !!doc.assign_release_on_resolve
  form.auto_assign = !!doc.auto_assign
  form.assign_only_available = !!doc.assign_only_available
  form.assign_on = doc.assign_on || 'New conversations'
  form.assign_team = doc.assign_team || ''
  form.business_hours_enabled = !!doc.business_hours_enabled
  form.away_message = doc.away_message || ''
  form.away_cooldown_hours = doc.away_cooldown_hours ?? 12
  form.sla_enabled = !!doc.sla_enabled
  form.sla_first_response_minutes = doc.sla_first_response_minutes || 30
  form.sla_business_hours_only = doc.sla_business_hours_only === undefined ? true : !!doc.sla_business_hours_only
  form.csat_enabled = !!doc.csat_enabled
  form.csat_message = doc.csat_message || ''
  form.resolve_require_reason = !!doc.resolve_require_reason
  form.resolve_require_note = !!doc.resolve_require_note
  form.resolve_reasons = doc.resolve_reasons || ''
  form.resolve_when_waiting = doc.resolve_when_waiting || 'Allow'
  form.resolve_only_owner = !!doc.resolve_only_owner
  form.outgoing_new_status = doc.outgoing_new_status || 'Pending'
  week.value = buildWeek(doc.business_hours)
  snapshot.value = serialize()
}

async function loadStatus() {
  try {
    status.value = await call('onechat.inbox.routing.status')
  } catch {
    status.value = null
  }
}

async function load() {
  error.value = ''

  try {
    const [doc, teamRows] = await Promise.all([
      call('frappe.client.get', { doctype: SETTINGS, name: SETTINGS }),
      call('onechat.workspace.teams.teams'),
      loadStatus(),
    ])
    teams.value = teamRows || []
    apply(doc)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''

  try {
    const doc = await call('frappe.client.set_value', { doctype: SETTINGS, name: SETTINGS, fieldname: values() })
    apply(doc)
    await loadStatus()
    toast.success(__('Saved'))
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

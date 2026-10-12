<template>
  <SettingsHeader>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Teams') }}</h2>
        <p class="mt-1 text-base text-ink-gray-6">{{ __('Groups of agents that flows and inbox rules can hand conversations to') }}</p>
      </div>
      <Button variant="solid" icon-left="lucide-plus" :label="__('New team')" data-tour="new-team" @click="edit(null)" />
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <div v-if="loading" class="grid grid-cols-1 gap-3 pt-6 sm:grid-cols-2">
      <Skeleton v-for="row in 2" :key="row" class="h-36 w-full rounded-6" />
    </div>

    <div v-else-if="rows.length" class="grid grid-cols-1 gap-3 pt-6 sm:grid-cols-2">
      <div
        v-for="team in rows"
        :key="team.name"
        role="button"
        tabindex="0"
        class="flex cursor-pointer flex-col gap-3 rounded-6 border border-outline-gray-2 bg-surface-base p-4 text-left transition-colors hover:border-outline-gray-3 hover:bg-surface-gray-1"
        @click="edit(team)"
        @keydown.enter.self="edit(team)"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <TruncatedText as="p" class="truncate text-lg font-semibold text-ink-gray-9" :text="team.team_name" />
            <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="team.description || __('No description')" />
          </div>
          <span class="shrink-0 rounded-full bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-7">
            {{ __('{0} members').format(team.members.length) }}
          </span>
        </div>

        <div class="flex items-center gap-2">
          <div class="flex -space-x-2">
            <Avatar
              v-for="member in team.members.slice(0, 6)"
              :key="member.user"
              size="md"
              class="ring-2 ring-surface-base"
              :image="member.image"
              :label="member.full_name"
            />
          </div>
          <span v-if="team.members.length > 6" class="text-sm text-ink-gray-5">+{{ team.members.length - 6 }}</span>
        </div>

        <div class="flex flex-col items-start gap-0.5 text-xs text-ink-gray-5">
          <button type="button" :class="LINK" :title="__('Open members')" @click.stop="ui.settingsTab = 'team'">
            <span class="size-1.5 rounded-full bg-surface-green-6" aria-hidden="true" />{{ __('{0} available').format(available(team)) }}
          </button>
          <button
            v-for="account in team.accounts"
            :key="account"
            type="button"
            :class="LINK"
            :title="__('Open accounts')"
            @click.stop="ui.settingsTab = 'accounts'"
          >
            <span class="lucide-smartphone size-3" aria-hidden="true" />{{ numberLabel(account) }}
          </button>
          <button
            v-if="team.auto_assign_target"
            type="button"
            :class="LINK"
            :title="__('Open inbox rules')"
            @click.stop="ui.settingsTab = 'inbox-rules'"
          >
            <span class="lucide-inbox size-3" aria-hidden="true" />{{ __('Inbox auto-assign') }}
          </button>
          <button
            v-for="flow in team.flows"
            :key="flow.name"
            type="button"
            :class="LINK"
            :title="__('Open flow')"
            @click.stop="openFlow(flow.name)"
          >
            <span class="lucide-git-fork size-3" aria-hidden="true" />{{ flow.label }}
            <span class="lucide-arrow-up-right size-3 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>

    <EmptyState
      v-else
      class="mt-6"
      icon="lucide-users-round"
      :title="__('No teams yet')"
      :description="__('Create a team such as Sales or Support, then hand conversations to it from a flow or inbox rules.')"
    >
      <Button variant="solid" icon-left="lucide-plus" :label="__('New team')" @click="edit(null)" />
    </EmptyState>
  </SettingsBody>

  <ResponsiveDialog v-model:open="open" :title="form.name ? __('Edit team') : __('New team')" size="4xl">
    <template #default>
      <div class="flex flex-col gap-5">
        <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <FormControl v-model="form.team_name" :label="__('Name')" :placeholder="__('Sales')" required />
          <FormControl
            v-model="form.description"
            :label="__('Description')"
            :placeholder="__('Who is in this team and what they handle')"
          />
        </div>

        <div class="flex flex-col gap-1.5">
          <FormLabel :label="__('Accounts')" />
          <MultiSelect v-model="form.accounts" :options="numberOptions" :placeholder="__('Any account')" />
          <p class="text-sm text-ink-gray-5">
            {{
              form.accounts.length
                ? __('Only members of this team and admins can see and reply to chats on these numbers.')
                : __('Leave empty to let this team work on every number that no team owns.')
            }}
          </p>
          <p v-if="shared.length" class="flex items-start gap-1.5 text-sm text-ink-blue-7">
            <span class="lucide-info mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {{ __('Also shared with: {0}').format(shared.join(', ')) }}
          </p>
        </div>

        <div class="flex flex-col gap-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="text-base font-medium text-ink-gray-8">{{ __('Members') }} · {{ form.members.length }}</p>
              <p class="text-sm text-ink-gray-5">
                {{ __('{0} available now').format(availableNow) }}
                <template v-if="blockedCount">
                  · <span class="text-ink-amber-7">{{ __('{0} need attention').format(blockedCount) }}</span></template
                >
              </p>
            </div>
            <div class="flex w-full items-center gap-2 sm:w-auto">
              <FormControl
                type="text"
                v-if="form.members.length > 6"
                v-model="search"
                class="min-w-0 flex-1 sm:w-48"
                :placeholder="__('Filter members')"
              >
                <template #prefix>
                  <span class="lucide-search size-4 text-ink-gray-4" aria-hidden="true" />
                </template>
              </FormControl>
              <Combobox
                class="min-w-0 flex-1 sm:w-60"
                :model-value="null"
                :options="addOptions"
                :placeholder="addable.length ? __('Add people…') : __('Everyone eligible is in')"
                :disabled="!addable.length"
                @update:model-value="add"
              />
            </div>
          </div>

          <ScrollArea v-if="form.members.length" class="max-h-[24rem]" viewport-class="max-h-[24rem]">
            <ul class="grid grid-cols-1 gap-2 pb-0.5 sm:grid-cols-2 lg:grid-cols-3">
              <li
                v-for="member in shown"
                :key="member.user"
                class="group flex min-w-0 items-center gap-2.5 rounded-4 border px-2.5 py-2"
                :class="member.eligible ? 'border-outline-gray-1 bg-surface-base' : 'border-outline-amber-2 bg-surface-amber-1'"
              >
                <span class="relative shrink-0">
                  <Avatar size="md" :image="member.image" :label="member.full_name" />
                  <span
                    class="absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full ring-2 ring-surface-base"
                    :class="member.availability === 'Away' || !member.eligible ? 'bg-surface-gray-4' : 'bg-surface-green-6'"
                    :title="__(member.availability || 'Available')"
                  />
                </span>
                <span class="min-w-0 flex-1">
                  <TruncatedText class="block truncate text-sm font-medium text-ink-gray-8" :text="member.full_name" />
                  <span class="flex min-w-0 items-center gap-1 text-xs">
                    <TruncatedText v-if="!member.eligible" class="truncate text-ink-amber-7" :text="member.reason" />
                    <template v-else>
                      <span class="shrink-0 text-ink-gray-6">{{ __(member.role) }}</span>
                      <span class="truncate text-ink-gray-4">· {{ member.user }}</span>
                    </template>
                  </span>
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  icon="lucide-x"
                  class="shrink-0 opacity-60 group-hover:opacity-100"
                  :label="__('Remove {0}').format(member.full_name)"
                  @click="removeMember(member.user)"
                />
              </li>
            </ul>
            <p v-if="!shown.length" class="px-1 py-4 text-sm text-ink-gray-5">{{ __('No members match.') }}</p>
          </ScrollArea>

          <div v-else class="flex flex-col items-center gap-1 rounded-5 border border-dashed border-outline-gray-2 px-4 py-8 text-center">
            <span class="lucide-users-round size-5 text-ink-gray-4" aria-hidden="true" />
            <p class="text-sm font-medium text-ink-gray-8">{{ __('No members yet') }}</p>
            <p class="text-sm text-ink-gray-5">{{ __("Add the people who should handle this team's chats.") }}</p>
          </div>

          <p class="text-xs text-ink-gray-5">
            {{ __('Only active OneChat members with an Agent, Manager or Admin role can be added. Manage roles under Settings → Team.') }}
          </p>
        </div>

        <ErrorMessage :message="formError" />
      </div>
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <Button v-if="form.name" variant="ghost" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="remove" />
        <span v-else />
        <div class="flex gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
          <Button variant="solid" :loading="saving" :label="__('Save')" @click="save" />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Avatar,
  Button,
  Combobox,
  ErrorMessage,
  FormControl,
  FormLabel,
  MultiSelect,
  ScrollArea,
  SettingsBody,
  SettingsHeader,
  Skeleton,
  call,
  toast,
} from 'frappe-ui'
import EmptyState from '@/components/Common/EmptyState.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const ui = useUI()
const router = useRouter()

const LINK = 'group inline-flex items-center gap-1 rounded-3 px-1 -mx-1 py-0.5 hover:bg-surface-gray-3 hover:text-ink-gray-8'

function openFlow(name) {
  ui.settingsDialog = false
  router.push({ name: 'FlowBuilder', params: { name } })
}

const rows = ref([])
const candidates = ref([])
const loading = ref(true)
const error = ref('')
const open = ref(false)
const saving = ref(false)
const formError = ref('')
const search = ref('')
const form = reactive({ name: null, team_name: '', description: '', members: [], accounts: [] })
const numbers = ref([])

const numberOptions = computed(() =>
  numbers.value.map((row) => ({
    label: row.label,
    value: row.value,
    description: [
      row.number,
      row.teams.filter((team) => team !== form.name).length
        ? __('Also in {0}').format(row.teams.filter((team) => team !== form.name).join(', '))
        : '',
    ]
      .filter(Boolean)
      .join(' · '),
  })),
)

const shared = computed(() => [
  ...new Set(
    numbers.value.filter((row) => form.accounts.includes(row.value)).flatMap((row) => row.teams.filter((team) => team !== form.name)),
  ),
])

function numberLabel(account) {
  const row = numbers.value.find((item) => item.value === account)
  return row ? [row.label, row.number].filter(Boolean).join(' · ') : account
}

const known = ref({})

const picked = computed(() => new Set(form.members))

const memberRows = computed(() =>
  form.members
    .map((user) => known.value[user] || { user, full_name: user, eligible: 0, reason: __('Not a OneChat member') })
    .sort((a, b) => Number(a.eligible) - Number(b.eligible) || a.full_name.localeCompare(b.full_name)),
)

const shown = computed(() => {
  const query = search.value.trim().toLowerCase()
  return query
    ? memberRows.value.filter((row) => `${row.full_name} ${row.user} ${row.role || ''}`.toLowerCase().includes(query))
    : memberRows.value
})

const availableNow = computed(() => memberRows.value.filter((row) => row.eligible && row.availability !== 'Away').length)
const blockedCount = computed(() => memberRows.value.filter((row) => !row.eligible).length)
const addable = computed(() => candidates.value.filter((row) => !picked.value.has(row.user)))

const addOptions = computed(() => {
  const people = addable.value.map((row) => ({ label: row.full_name, value: row.user, description: `${__(row.role)} · ${row.user}` }))
  if (addable.value.length < 2) return people
  return [
    {
      type: 'custom',
      key: 'add-all',
      label: __('Add all {0} eligible people').format(addable.value.length),
      icon: 'lucide-users-round',
      onClick: () => (form.members = [...new Set([...form.members, ...addable.value.map((row) => row.user)])]),
    },
    ...people,
  ]
})

function available(team) {
  return team.members.filter((member) => member.enabled && member.availability !== 'Away').length
}

async function load() {
  error.value = ''
  try {
    const [teams, people, accounts] = await Promise.all([
      call('onechat.workspace.teams.teams'),
      call('onechat.workspace.teams.candidates'),
      call('onechat.inbox.accounts.options'),
    ])
    rows.value = teams
    candidates.value = people
    numbers.value = accounts
    remember([...people, ...teams.flatMap((team) => team.members)])
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function edit(team) {
  Object.assign(form, {
    name: team?.name || null,
    team_name: team?.team_name || '',
    description: team?.description || '',
    members: (team?.members || []).map((member) => member.user),
    accounts: [...(team?.accounts || [])],
  })
  search.value = ''
  formError.value = ''
  open.value = true
}

function remember(people) {
  known.value = { ...known.value, ...Object.fromEntries(people.map((row) => [row.user, row])) }
}

function add(user) {
  if (user && !picked.value.has(user)) form.members = [...form.members, user]
}

function removeMember(user) {
  form.members = form.members.filter((row) => row !== user)
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    const saved = await call('onechat.workspace.teams.save_team', {
      name: form.name,
      team_name: form.team_name,
      description: form.description,
      members: JSON.stringify(form.members),
      accounts: JSON.stringify(form.accounts),
    })
    numbers.value = await call('onechat.inbox.accounts.options')
    rows.value = saved
    remember(saved.flatMap((team) => team.members))
    open.value = false
    toast.success(__('Team saved'))
  } catch (err) {
    formError.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function remove() {
  const team = rows.value.find((row) => row.name === form.name)
  const uses = (team?.flows || []).map((flow) => flow.label)
  if (team?.auto_assign_target) uses.unshift(__('inbox auto-assign'))
  ui.confirm({
    title: __('Delete {0}?').format(form.team_name),
    message: uses.length
      ? __('It is used by {0}. Those will stop assigning to anyone until you pick another team.').format(uses.join(', '))
      : __('Conversations keep their assigned agent. Only the team is removed.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      rows.value = await call('onechat.workspace.teams.delete_team', { name: form.name })
      open.value = false
      toast.success(__('Team deleted'))
    },
  })
}

onMounted(load)
</script>

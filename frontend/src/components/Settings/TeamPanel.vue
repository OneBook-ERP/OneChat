<template>
  <SettingsHeader>
    <div class="flex flex-col gap-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="text-lg font-semibold text-ink-gray-8">{{ __('Team') }}</h2>
          <p class="mt-1 text-base text-ink-gray-6">{{ __('People who can sign in to OneChat, and what they can do') }}</p>
        </div>
        <Button
          variant="solid"
          icon-left="lucide-user-plus"
          :label="__('Invite member')"
          data-tour="invite-member"
          @click="inviting = true"
        />
      </div>
      <FormControl type="text" v-model="search" :placeholder="__('Search by name or email')">
        <template #prefix>
          <span class="lucide-search size-4 text-ink-gray-4" aria-hidden="true" />
        </template>
      </FormControl>
    </div>
  </SettingsHeader>

  <SettingsBody>
    <ErrorMessage :message="error" class="pt-4" />

    <ListSkeleton v-if="loading" class="pt-4" :rows="4" />

    <List
      v-else-if="filtered.length"
      class="-mx-3 pt-4"
      :columns="{ base: ['minmax(0,1fr)', '7rem', '3rem'], md: ['minmax(0,1fr)', '9rem', '8rem', '5rem'] }"
      :row-height="56"
    >
      <ListHeader>
        <ListHeaderCell>{{ __('Member') }}</ListHeaderCell>
        <ListHeaderCell>{{ __('Role') }}</ListHeaderCell>
        <ListHeaderCell class="max-md:hidden">{{ __('Schedule') }}</ListHeaderCell>
        <ListHeaderCell>{{ __('Active') }}</ListHeaderCell>
      </ListHeader>
      <ListRows :items="filtered" v-slot="{ item }">
        <ListRow>
          <ListCell>
            <Avatar size="lg" :image="item.image" :label="item.full_name" />
            <div class="ml-3 min-w-0">
              <div class="flex items-center gap-1.5">
                <TruncatedText
                  class="truncate text-base text-ink-gray-8"
                  :class="{ 'text-ink-gray-5': !item.enabled }"
                  :text="item.full_name"
                />
                <Badge v-if="item.user === session.user.name" theme="gray" variant="subtle" size="sm" :label="__('You')" />
              </div>
              <TruncatedText as="div" class="mt-0.5 truncate text-sm text-ink-gray-5" :text="item.user" />
            </div>
          </ListCell>
          <ListCell>
            <Tooltip v-if="item.is_system_manager" :text="__('System Managers always have admin access')">
              <Badge theme="blue" variant="subtle" :label="__('System Manager')" />
            </Tooltip>
            <Select
              v-else
              class="w-full"
              :options="ROLE_OPTIONS"
              :model-value="item.is_admin ? 'admin' : 'agent'"
              :disabled="busy[item.name] || item.user === session.user.name"
              @update:model-value="(value) => setRole(item, value === 'admin')"
            />
          </ListCell>
          <ListCell class="max-md:hidden">
            <Button
              size="sm"
              variant="ghost"
              :icon-left="scheduleOf(item).icon"
              :label="scheduleOf(item).label"
              :class="scheduleOf(item).class"
              :disabled="!item.enabled"
              @click="openSchedule(item)"
            />
          </ListCell>
          <ListCell>
            <Switch
              :model-value="!!item.enabled"
              :disabled="busy[item.name] || item.user === session.user.name"
              :aria-label="__('Active')"
              @update:model-value="(value) => setEnabled(item, value)"
            />
          </ListCell>
        </ListRow>
      </ListRows>
    </List>

    <EmptyState
      v-else
      class="mt-6"
      icon="lucide-users"
      :title="search ? __('No one matches that search') : __('No members yet')"
      :description="search ? '' : __('Invite your teammates so they can answer conversations.')"
    />

    <InviteDialog v-model:open="inviting" @invited="load" />
    <ScheduleDialog
      v-model:open="scheduleOpen"
      :user="scheduleFor?.user || ''"
      :name="scheduleFor?.full_name || ''"
      @saved="(data) => (schedules[data.user] = data)"
    />
  </SettingsBody>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Avatar,
  Badge,
  Button,
  ErrorMessage,
  FormControl,
  Select,
  SettingsBody,
  SettingsHeader,
  Switch,
  Tooltip,
  call,
  toast,
} from 'frappe-ui'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from 'frappe-ui/list'
import InviteDialog from './InviteDialog.vue'
import ScheduleDialog from './ScheduleDialog.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import ListSkeleton from '@/components/Common/ListSkeleton.vue'
import { session } from '@/data/session'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const ROLE_OPTIONS = [
  { label: __('Agent'), value: 'agent' },
  { label: __('Admin'), value: 'admin' },
]

const members = ref([])
const loading = ref(true)
const error = ref('')
const search = ref('')
const inviting = ref(false)
const busy = reactive({})
const schedules = reactive({})
const scheduleOpen = ref(false)
const scheduleFor = ref(null)

function scheduleOf(item) {
  const data = schedules[item.user]
  if (!data) return { label: __('Set hours'), icon: 'lucide-calendar-clock', class: 'text-ink-gray-5' }
  if (data.on_leave) return { label: __('On leave'), icon: 'lucide-plane', class: 'text-ink-amber-7' }
  if (!data.use_shift)
    return { label: data.leaves.length ? __('Leave planned') : __('Any time'), icon: 'lucide-calendar-clock', class: 'text-ink-gray-6' }
  return data.working_now
    ? { label: __('Working'), icon: 'lucide-clock', class: 'text-ink-green-7' }
    : { label: __('Off shift'), icon: 'lucide-moon', class: 'text-ink-gray-5' }
}

function openSchedule(item) {
  scheduleFor.value = item
  scheduleOpen.value = true
}

const filtered = computed(() => {
  const text = search.value.trim().toLowerCase()
  if (!text) return members.value

  return members.value.filter((row) => `${row.full_name} ${row.user}`.toLowerCase().includes(text))
})

async function load() {
  error.value = ''

  try {
    const [rows, plans] = await Promise.all([
      call('onechat.workspace.team.members'),
      call('onechat.workspace.shifts.team_schedule').catch(() => ({})),
    ])
    members.value = rows
    Object.assign(schedules, plans)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function change(item, changes, request) {
  const previous = Object.fromEntries(Object.keys(changes).map((key) => [key, item[key]]))
  Object.assign(item, changes)
  busy[item.name] = true
  error.value = ''

  try {
    await request()
    toast.success(__('Saved'))
  } catch (err) {
    Object.assign(item, previous)
    error.value = errorMessage(err)
  } finally {
    busy[item.name] = false
  }
}

function setRole(item, admin) {
  if (admin === item.is_admin) return

  change(item, { is_admin: admin }, () => call('onechat.workspace.team.set_admin', { user: item.user, admin: admin ? 1 : 0 }))
}

function setEnabled(item, enabled) {
  change(item, { enabled: enabled ? 1 : 0 }, () => call('onechat.workspace.team.set_active', { user: item.user, active: enabled ? 1 : 0 }))
}

onMounted(load)
</script>

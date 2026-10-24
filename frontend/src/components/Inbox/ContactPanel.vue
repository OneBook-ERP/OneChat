<template>
  <aside class="flex min-h-0 flex-col bg-surface-base" :aria-label="__('Contact details')">
    <header v-if="!compact" class="flex h-14 shrink-0 items-center justify-between gap-2 border-b px-4">
      <h2 class="text-base font-medium text-ink-gray-9">{{ __('Contact details') }}</h2>
      <Button variant="ghost" icon="lucide-x" :label="__('Close')" :tooltip="__('Close')" @click="emit('close')" />
    </header>

    <ScrollArea class="min-h-0 flex-1" :viewport-class="compact ? 'px-4 pb-4' : 'px-4 pb-8'">
      <div class="flex flex-col gap-2" :class="compact ? 'pt-1' : 'pt-4'">
        <div class="flex items-center gap-3">
          <Avatar :image="contact.profile_image" :label="title" size="2xl" />
          <div class="min-w-0 flex-1">
            <TruncatedText as="p" class="truncate text-base font-semibold text-ink-gray-9" :text="title" />
            <a
              v-if="contact.mobile_no"
              :href="`tel:${contact.mobile_no}`"
              class="block text-sm tabular-nums text-ink-gray-6 hover:text-ink-gray-8"
            >
              {{ contact.mobile_no }}
            </a>
            <a
              v-if="contact.instagram_username"
              :href="`https://instagram.com/${contact.instagram_username}`"
              target="_blank"
              rel="noopener noreferrer"
              class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8"
            >
              <ChannelIcon channel="Instagram" class="size-3.5" />@{{ contact.instagram_username }}
            </a>
            <RouterLink
              v-for="twin in contact.also_on || []"
              :key="twin.name"
              :to="{ name: 'Inbox', params: { contact: twin.name } }"
              class="flex items-center gap-1 text-sm text-ink-blue-6 hover:underline"
            >
              <ChannelIcon channel="Instagram" class="size-3.5" />
              {{ __('Also on {0}').format(twin.account_label) }}
              <span v-if="twin.unread_count" class="text-ink-gray-5">· {{ __('{0} unread').format(twin.unread_count) }}</span>
            </RouterLink>
            <p v-if="contact.email" class="truncate text-sm text-ink-gray-5">
              <a :href="`mailto:${contact.email}`" class="hover:text-ink-gray-8">{{ contact.email }}</a>
            </p>
          </div>
        </div>
        <LabelBadges v-if="contact.labels?.length" :names="contact.labels" class="max-w-full flex-wrap" />
      </div>

      <section class="mt-4 flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-ink-gray-7">{{ __('Assigned to') }}</h3>
          <Button
            v-if="contact.assigned_to !== session.user.name"
            variant="ghost"
            :size="compact ? 'md' : 'sm'"
            :label="__('Assign to me')"
            :loading="assigning"
            @click="changeAssignee(session.user.name)"
          />
        </div>
        <Combobox
          :size="compact ? 'lg' : 'sm'"
          :model-value="contact.assigned_to || ''"
          :options="agentOptions"
          :loading="agents.loading"
          :disabled="assigning"
          :placeholder="__('Unassigned')"
          @update:model-value="changeAssignee"
        />
      </section>

      <ReminderList :contact="contactName" />

      <CustomerScores
        v-if="profile?.scores?.scores_updated_at !== undefined"
        class="mt-5"
        :contact="contactName"
        :scores="profile.scores"
        @updated="(scores) => (profile = { ...profile, scores })"
      />
      <CustomerStats v-if="stats.length || !profile" class="mt-4" :stats="stats.slice(0, 4)" :loading="!profile" columns="grid-cols-2" />

      <section class="mt-6 flex flex-col gap-2">
        <h3 class="text-sm font-medium text-ink-gray-7">
          {{ __('Notes') }}
          <span v-if="notes.length" class="ml-1 tabular-nums text-ink-gray-5">{{ notes.length }}</span>
        </h3>

        <div v-if="!details" class="flex flex-col gap-2">
          <Skeleton v-for="index in 2" :key="index" class="h-14 w-full rounded-4" />
        </div>

        <p v-else-if="!notes.length" class="text-sm text-ink-gray-5">
          {{ __('No notes yet') }}
        </p>

        <template v-else>
          <button
            v-for="note in allNotes ? notes : notes.slice(0, NOTE_LIMIT)"
            :key="note.name"
            type="button"
            class="flex flex-col gap-1 rounded-4 border border-outline-amber-2 bg-surface-amber-1 px-3 text-left transition-colors hover:border-outline-amber-3 focus-visible:focus-ring"
            :class="compact ? 'min-h-11 py-2.5' : 'py-2'"
            :title="__('Show in the conversation')"
            @click="reveal(note)"
          >
            <TruncatedText
              class="line-clamp-3 whitespace-pre-wrap break-words text-sm text-ink-gray-8"
              :text="plainMessage(note.content)"
            />
            <span class="flex items-center gap-1 text-xs text-ink-amber-7">
              <span class="lucide-lock size-3.5 shrink-0" aria-hidden="true" />
              <span class="truncate">
                {{ note.owner === session.user.name ? __('You') : note.owner_name || note.owner }} ·
                {{ timeAgo(note.creation) }}
              </span>
            </span>
          </button>
          <Button
            v-if="notes.length > NOTE_LIMIT"
            variant="ghost"
            size="sm"
            class="self-start"
            :label="allNotes ? __('Show less') : __('Show all {0}').format(notes.length)"
            @click="allNotes = !allNotes"
          />
        </template>
      </section>

      <section class="mt-6 flex flex-col gap-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-ink-gray-7">{{ __('Recent activity') }}</h3>
          <Button
            variant="ghost"
            :size="compact ? 'md' : 'sm'"
            icon-right="lucide-arrow-right"
            :label="__('Full profile')"
            :route="{ name: 'CustomerProfile', params: { contact: contactName } }"
          />
        </div>
        <CustomerTimeline :key="contactName" :contact="contactName" compact :limit="5" />
      </section>

      <IntegrationCards
        class="mt-6"
        :contact="contactName"
        :reference-doctype="contact.reference_doctype"
        :reference-docname="contact.reference_docname"
        :linked="contact.linked || []"
        @changed="applyLink"
      />

      <div v-if="session.user.is_admin" class="mt-6">
        <Button
          class="w-full"
          variant="subtle"
          :size="compact ? 'lg' : 'sm'"
          icon-left="lucide-external-link"
          :label="__('Open in desk')"
          :link="deskUrl('OneChat Contact', contactName)"
        />
      </div>
    </ScrollArea>
  </aside>
</template>

<script setup>
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import { Avatar, Button, Combobox, ScrollArea, Skeleton, toast } from 'frappe-ui'
import CustomerScores from '@/components/Customer/CustomerScores.vue'
import ReminderList from './ReminderList.vue'
import CustomerStats from '@/components/Customer/CustomerStats.vue'
import CustomerTimeline from '@/components/Customer/CustomerTimeline.vue'
import IntegrationCards from '@/components/Integrations/IntegrationCards.vue'
import LabelBadges from '@/components/Labels/LabelBadges.vue'
import { customerProfile } from '@/data/customer'
import { agents, assign, deskUrl, findRow, inbox, loadDetails, plainMessage, revealNote } from '@/data/inbox'
import { session } from '@/data/session'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contactName: { type: String, required: true },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const assigning = ref(false)
const profile = ref(null)
const stats = computed(() => [...(profile.value?.record_stats || []), ...(profile.value?.stats || [])])

async function loadProfile(name) {
  profile.value = null
  try {
    const result = await customerProfile(name)
    if (name === props.contactName) profile.value = result
  } catch {
    if (name === props.contactName) profile.value = { stats: [], record_stats: [] }
  }
}

const details = computed(() => inbox.details[props.contactName] || null)
const contact = computed(() => ({ ...findRow(props.contactName), ...details.value }))
const title = computed(
  () =>
    contact.value.contact_name ||
    contact.value.mobile_no ||
    (contact.value.instagram_username && `@${contact.value.instagram_username}`) ||
    props.contactName,
)
const notes = computed(() => details.value?.notes || [])
const NOTE_LIMIT = 3
const allNotes = ref(false)

const agentOptions = computed(() => {
  const options = (agents.data || []).map((agent) => ({ label: agent.full_name || agent.name, value: agent.name }))
  const current = contact.value.assigned_to
  if (current && !options.some((option) => option.value === current)) options.unshift({ label: current, value: current })

  return [{ label: __('Unassigned'), value: '' }, ...options]
})

function applyLink(result) {
  loadProfile(props.contactName)
  const changes = {
    reference_doctype: result.reference_doctype,
    reference_docname: result.reference_docname,
    linked: (result.links || []).map((row) => row.doctype),
  }
  if (inbox.details[props.contactName]) Object.assign(inbox.details[props.contactName], changes)
  const row = findRow(props.contactName)
  if (row) Object.assign(row, changes)
}

async function changeAssignee(user) {
  const value = user || null
  if (value === (contact.value.assigned_to || null)) return

  assigning.value = true
  try {
    await assign(props.contactName, value)
    toast.success(value ? __('Conversation assigned') : __('Conversation unassigned'))
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    assigning.value = false
  }
}

async function reveal(note) {
  try {
    const found = await revealNote(props.contactName, note.name)
    if (!found) toast.error(__('Could not find this note in the conversation'))
  } catch (error) {
    toast.error(errorMessage(error))
  }
}

watch(
  () => props.contactName,
  (name) => {
    if (!agents.data) agents.fetch()
    if (!inbox.details[name]) loadDetails(name).catch((error) => toast.error(errorMessage(error)))
    loadProfile(name)
  },
  { immediate: true },
)
</script>

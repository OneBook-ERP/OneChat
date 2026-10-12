<template>
  <section class="flex min-h-0 min-w-0 flex-1 flex-col bg-surface-base" :aria-label="title">
    <header v-if="compact" class="flex h-14 shrink-0 items-center gap-1 border-b pl-1 pr-2">
      <PageHeaderBackButton :to="back" :label="__('Back')" class="!size-10" />
      <Avatar :image="contact.profile_image" :label="title" size="xl" class="shrink-0" />
      <div class="ml-1.5 min-w-0 flex-1">
        <TruncatedText as="p" class="truncate text-base font-medium leading-5 text-ink-gray-9" :text="title" />
        <p class="truncate text-xs leading-4" :class="typingLine ? 'text-ink-green-7' : 'text-ink-gray-5'" aria-live="polite">
          <template v-if="typingLine">{{ typingLine }}</template>
          <template v-else>
            <span v-if="contact.mobile_no" class="tabular-nums">{{ contact.mobile_no }}</span>
            <span v-if="contact.instagram_username" class="inline-flex items-center gap-1"
              ><ChannelIcon channel="Instagram" class="size-3" />@{{ contact.instagram_username }}</span
            >
            <span v-if="contact.opted_out" class="text-ink-red-7">
              <template v-if="contact.mobile_no"> · </template>{{ __('Opted out') }}
            </span>
          </template>
        </p>
      </div>
      <FollowUpMenu :contact="{ ...contact, name: contactName }" size="lg" icon-class="size-[1.05rem]" />
      <Dropdown :options="statusMenu" align="end">
        <Button
          variant="ghost"
          size="lg"
          :icon="STATUS_LOOK[status].icon"
          :label="__('Status: {0}').format(__(status))"
          :loading="statusBusy"
        />
      </Dropdown>
      <Dropdown :options="phoneMenu" align="end">
        <Button variant="ghost" size="lg" icon="lucide-ellipsis-vertical" :label="__('More actions')" />
      </Dropdown>
    </header>

    <header v-else class="flex h-14 shrink-0 items-center gap-1 border-b px-3 sm:px-4">
      <Button
        variant="ghost"
        class="-ml-1"
        :icon="listOpen ? 'lucide-panel-left-close' : 'lucide-panel-left-open'"
        :tooltip="listOpen ? __('Hide conversation list') : __('Show conversation list')"
        :label="listOpen ? __('Hide conversation list') : __('Show conversation list')"
        @click="emit('list')"
      />
      <Avatar :image="contact.profile_image" :label="title" size="lg" class="ml-2 shrink-0" />
      <div class="ml-2 mr-2 min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-2">
          <TruncatedText as="p" class="truncate text-base font-medium text-ink-gray-9" :text="title" />
          <LabelBadges :names="contact.labels || []" :max="3" />
          <Tooltip
            v-if="contact.opted_out"
            :text="__('Opted out of marketing. Replies are fine; marketing templates and broadcasts are blocked.')"
          >
            <Badge theme="red" variant="subtle" size="sm" :label="__('Opted out')" />
          </Tooltip>
        </div>
        <p class="flex items-center gap-1.5 truncate text-xs text-ink-gray-5">
          <span v-if="contact.mobile_no" class="tabular-nums">{{ contact.mobile_no }}</span>
          <span v-if="contact.instagram_username" class="inline-flex items-center gap-1"
            ><ChannelIcon channel="Instagram" class="size-3" />@{{ contact.instagram_username }}</span
          >
          <template v-if="contact.reference_doctype">
            <span aria-hidden="true">·</span>
            <span>{{ __(contact.reference_doctype) }}</span>
          </template>
          <template v-if="assignee">
            <span aria-hidden="true">·</span>
            <TruncatedText class="truncate" :text="__('Assigned to {0}').format(assignee)" />
          </template>
        </p>
      </div>
      <Tooltip v-if="present.length" :text="presentTooltip">
        <div class="mr-1 flex shrink-0 items-center -space-x-1.5" :aria-label="presentTooltip">
          <span v-for="person in present.slice(0, 3)" :key="person.user" class="relative rounded-full ring-2 ring-surface-base">
            <Avatar :image="person.image" :label="person.name" size="sm" />
            <span
              v-if="person.typing"
              class="absolute -bottom-0.5 -right-0.5 flex size-3 items-center justify-center rounded-full bg-surface-amber-2 ring-1 ring-surface-base"
            >
              <span class="lucide-pencil size-2 text-ink-amber-7" aria-hidden="true" />
            </span>
          </span>
          <span
            v-if="present.length > 3"
            class="flex size-6 items-center justify-center rounded-full bg-surface-gray-3 text-2xs font-medium text-ink-gray-7 ring-2 ring-surface-base"
          >
            +{{ present.length - 3 }}
          </span>
        </div>
      </Tooltip>
      <Button
        variant="ghost"
        icon="lucide-search"
        :label="__('Search in conversation')"
        :tooltip="__('Search in conversation (Ctrl+F)')"
        :class="{ 'bg-surface-gray-3': searching }"
        @click="toggleSearch"
      />
      <Button
        v-if="isAdmin"
        variant="ghost"
        icon="lucide-history"
        :label="showActivity ? __('Hide activity') : __('Show activity')"
        :tooltip="showActivity ? __('Hide assignments, status and label changes') : __('Show assignments, status and label changes')"
        :class="{ 'bg-surface-gray-3': showActivity }"
        @click="showActivity = !showActivity"
      />
      <FollowUpMenu :contact="{ ...contact, name: contactName }" />
      <LabelPicker :contact="contactName" :model-value="contact.labels || []" />
      <Button
        v-if="assistantOn"
        variant="ghost"
        :label="__('Assistant')"
        :tooltip="__('Ask the Assistant about this customer')"
        :class="{ 'bg-surface-gray-3': assistantOpen }"
        @click="assistantOpen = true"
      >
        <template #icon>
          <AssistantIcon class="size-4.5" still />
        </template>
      </Button>
      <Dropdown v-if="!embedded" :options="flowMenu" align="end">
        <Button variant="ghost" icon="lucide-workflow" :label="__('Start flow')" :tooltip="__('Start flow')" />
      </Dropdown>
      <Dropdown :options="statusMenu" align="end">
        <Button
          variant="subtle"
          :theme="STATUS_LOOK[status].theme"
          :icon-left="STATUS_LOOK[status].icon"
          icon-right="lucide-chevron-down"
          :label="__(status)"
          :tooltip="__('Change status (Alt+R to resolve or reopen)')"
          :loading="statusBusy"
        />
      </Dropdown>
      <Button
        variant="ghost"
        :icon="panelOpen ? 'lucide-panel-right-close' : 'lucide-panel-right-open'"
        :tooltip="__('Contact details')"
        :label="__('Contact details')"
        :class="{ 'bg-surface-gray-3': panelOpen }"
        @click="emit('details')"
      />
    </header>

    <ResolveDialog
      v-model:open="resolving"
      :rules="rules"
      :waiting="customerWaiting"
      :busy="statusBusy"
      @confirm="(extra) => changeStatus('Resolved', extra)"
    />

    <div
      v-if="isSnoozed(contact)"
      class="flex shrink-0 items-center gap-2 border-b bg-surface-amber-1 text-sm text-ink-amber-7"
      :class="compact ? 'px-3 py-1.5' : 'px-3 py-1.5 sm:px-4'"
    >
      <span class="lucide-alarm-clock size-4 shrink-0" aria-hidden="true" />
      <TruncatedText
        class="min-w-0 flex-1 truncate"
        :text="__('Snoozed until {0}. It comes back earlier if the customer replies.').format(formatDateTime(contact.snoozed_until))"
      />
      <Button size="sm" variant="ghost" :label="__('Unsnooze')" @click="wakeUp" />
    </div>

    <div
      v-if="contact.bot_flow"
      class="flex shrink-0 items-center gap-2 border-b bg-surface-green-1 text-sm text-ink-green-7"
      :class="compact ? 'px-3 py-1.5' : 'px-3 py-1.5 sm:px-4'"
    >
      <span class="lucide-bot size-4 shrink-0" aria-hidden="true" />
      <TruncatedText class="min-w-0 flex-1 truncate" :text="__('{0} is handling this chat. Replying stops it.').format(contact.bot_flow)" />
      <Button size="sm" variant="ghost" :loading="botBusy" :label="__('Stop bot')" @click="stopBot" />
    </div>

    <div v-if="searching" class="flex shrink-0 items-center border-b" :class="compact ? 'gap-1 px-2 py-2' : 'gap-1.5 px-3 py-2 sm:px-4'">
      <FormControl
        ref="searchInput"
        v-model="searchQuery"
        class="min-w-0 flex-1"
        type="search"
        :size="compact ? 'lg' : 'sm'"
        :placeholder="__('Search in this conversation')"
        @keydown.enter.prevent="(event) => stepResult(event.shiftKey ? -1 : 1)"
        @keydown.esc.prevent="closeSearch"
      >
        <template #prefix>
          <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
        </template>
        <template v-if="compact && searchStatus" #suffix>
          <span class="text-sm tabular-nums text-ink-gray-5" aria-live="polite">{{ searchStatus }}</span>
        </template>
      </FormControl>
      <span v-if="!compact" class="shrink-0 px-1 text-sm tabular-nums text-ink-gray-5" aria-live="polite">{{ searchStatus }}</span>
      <Button
        variant="ghost"
        :size="compact ? 'lg' : 'sm'"
        icon="lucide-chevron-up"
        :label="__('Older match')"
        :disabled="results.length < 2"
        @click="stepResult(1)"
      />
      <Button
        variant="ghost"
        :size="compact ? 'lg' : 'sm'"
        icon="lucide-chevron-down"
        :label="__('Newer match')"
        :disabled="results.length < 2"
        @click="stepResult(-1)"
      />
      <Button variant="ghost" :size="compact ? 'lg' : 'sm'" icon="lucide-x" :label="__('Close search')" @click="closeSearch" />
    </div>

    <div class="relative min-h-0 flex-1">
      <ScrollArea
        ref="scrollArea"
        class="!absolute inset-0"
        viewport-class="overscroll-contain px-2 pb-4 sm:px-6 [&>div]:flex [&>div]:min-h-full [&>div]:flex-col"
        role="log"
      >
        <div ref="content" class="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-end">
          <div v-if="state.older" class="flex justify-center py-3">
            <Spinner class="size-4 text-ink-gray-5" />
          </div>
          <p v-else-if="state.loaded && !state.hasMore && state.messages.length" class="py-4 text-center text-xs text-ink-gray-4">
            {{ __('This is the beginning of the conversation') }}
          </p>

          <div v-if="!state.loaded && state.loading" class="flex flex-col gap-3 py-4">
            <div v-for="index in 6" :key="index" class="flex" :class="index % 2 ? 'justify-start' : 'justify-end'">
              <Skeleton class="h-10 rounded-5" :class="index % 3 ? 'w-2/5' : 'w-3/5'" />
            </div>
          </div>

          <div v-else-if="loadError && !state.messages.length" class="py-10">
            <EmptyState icon="lucide-cloud-off" :title="__('Could not load messages')" :description="loadError">
              <Button variant="subtle" :label="__('Try again')" @click="refresh" />
            </EmptyState>
          </div>

          <div v-else-if="state.loaded && !state.messages.length" class="py-10">
            <EmptyState
              icon="lucide-messages-square"
              :title="__('No messages yet')"
              :description="__('Start the conversation with an approved template.')"
            >
              <Button variant="solid" icon-left="lucide-layout-template" :label="__('Send a template')" @click="templatesOpen = true" />
            </EmptyState>
          </div>

          <section v-for="day in days" :key="day.key" class="relative">
            <DaySeparator :label="day.label" />
            <template v-for="item in day.items" :key="item.key">
              <p
                v-if="item.kind === 'activity'"
                class="mx-auto my-1.5 flex w-fit max-w-[90%] items-center gap-1.5 rounded-full bg-surface-gray-2 px-2.5 py-1 text-xs text-ink-gray-6"
              >
                <span
                  :class="[ACTIVITY_ICONS[item.event.action] || 'lucide-history', 'size-3.5 shrink-0 text-ink-gray-5']"
                  aria-hidden="true"
                />
                <span class="min-w-0 truncate">{{ activityText(item.event) }}</span>
                <span class="shrink-0 tabular-nums text-ink-gray-4">{{ dayjs(item.event.creation).format('h:mm a') }}</span>
              </p>
              <NoteBubble
                v-else-if="item.kind === 'note'"
                :note="item.message"
                :contact="contactName"
                :highlighted="highlight === item.message.name"
              />
              <MessageBubble
                v-else
                :message="item.message"
                :first="item.first"
                :highlighted="highlight === item.message.name"
                :contact-name="title"
                :selected="selected === item.message.name"
                :touch="touch"
                @actions="actionFor = item.message"
                @select="selected = selected === item.message.name ? null : item.message.name"
                @reply="startReply(item.message)"
                @react="(emoji) => addReaction(item.message, emoji)"
                @retry="retryMessage(contactName, item.message)"
                @discard="discardMessage(contactName, item.message)"
                @open="(url) => (lightbox = url)"
              />
            </template>
          </section>
        </div>
      </ScrollArea>

      <Transition
        enter-active-class="transition duration-150"
        enter-from-class="translate-y-2 opacity-0"
        leave-active-class="transition duration-100"
        leave-to-class="translate-y-2 opacity-0"
      >
        <button
          v-if="!stick && state.messages.length"
          type="button"
          class="absolute bottom-3 right-3 flex items-center gap-1.5 rounded-full border border-outline-gray-2 bg-surface-elevation-2 px-3 py-1.5 text-sm font-medium text-ink-gray-8 shadow-md hover:bg-surface-gray-2 sm:right-6"
          @click="scrollToBottom(true)"
        >
          <span class="lucide-arrow-down size-4" aria-hidden="true" />
          <span v-if="unseen">{{ unseen === 1 ? __('1 new message') : __('{0} new messages').format(countLabel(unseen)) }}</span>
          <span v-else class="sr-only">{{ __('Jump to the latest message') }}</span>
        </button>
      </Transition>
    </div>

    <p
      v-if="typingLine"
      class="mx-3 mb-1.5 flex shrink-0 items-center gap-1.5 rounded bg-surface-amber-1 px-2.5 py-1.5 text-xs text-ink-amber-7 sm:mx-4"
      aria-live="polite"
    >
      <span class="lucide-pencil-line size-3.5 shrink-0" aria-hidden="true" />
      <span class="truncate">{{ typingLine }} {{ __('Check before you send so you don’t both reply.') }}</span>
    </p>
    <p v-else-if="viewingLine" class="flex shrink-0 items-center gap-1.5 px-4 pb-1 text-xs text-ink-gray-5 sm:px-6" aria-live="polite">
      <span class="lucide-eye size-3.5 shrink-0" aria-hidden="true" />
      <span class="truncate">{{ viewingLine }}</span>
    </p>

    <Composer
      ref="composer"
      v-model:reply="replyTo"
      :contact="contactName"
      :contact-name="title"
      :window-open="windowOpen"
      :human-window-open="humanWindowOpen"
      :channel="contact?.channel || 'WhatsApp'"
      :compact="compact"
      @templates="templatesOpen = true"
      @sent="scrollToBottom(true)"
    />

    <LabelPicker v-if="compact" v-model:open="labelsOpen" :contact="contactName" :model-value="contact.labels || []" sheet />

    <ResponsiveDialog :open="!!actionFor" :title="__('Message')" size="sm" @update:open="(value) => !value && (actionFor = null)">
      <template #default>
        <div class="flex justify-between gap-1" role="group" :aria-label="__('React')">
          <button
            v-for="emoji in REACTIONS"
            :key="emoji"
            type="button"
            class="grid size-11 place-content-center rounded-full text-2xl transition-colors active:bg-surface-gray-3"
            :class="actionFor?.reactions?.includes(emoji) ? 'bg-surface-gray-3' : 'bg-surface-gray-1'"
            :aria-label="__('React with {0}').format(emoji)"
            @click="addReaction(actionFor, emoji)"
          >
            {{ emoji }}
          </button>
        </div>
        <div class="-mx-2 flex flex-col">
          <button
            v-for="item in messageActions"
            :key="item.label"
            type="button"
            class="flex h-11 items-center gap-3 rounded-4 px-2 text-left text-base text-ink-gray-8 active:bg-surface-gray-2"
            @click="item.onClick"
          >
            <span :class="item.icon" class="size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
            {{ item.label }}
          </button>
        </div>
      </template>
    </ResponsiveDialog>

    <TemplatePicker v-model:open="templatesOpen" :contact="contactName" @sent="scrollToBottom(true)" />

    <ResponsiveDialog v-model:open="assistantOpen" :title="__('Assistant')" size="lg">
      <template #title>
        <div class="flex items-center gap-2.5">
          <AssistantIcon class="size-7 shrink-0 text-ink-green-6" />
          <div class="min-w-0 flex-1">
            <h3 class="text-lg font-semibold leading-6 text-ink-gray-9">{{ __('Assistant') }}</h3>
            <p v-if="assistantStatus.data?.provider" class="text-xs text-ink-gray-5">{{ assistantStatus.data.provider }}</p>
          </div>
          <Button
            v-if="assistantPanel?.hasTurns"
            variant="ghost"
            icon="lucide-message-square-plus"
            :label="__('New chat')"
            :tooltip="__('New chat')"
            @click="assistantPanel.reset()"
          />
        </div>
      </template>
      <template #default>
        <AssistantPanel ref="assistantPanel" :contact="contactName" bare @inserted="assistantOpen = false" />
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog :open="!!lightbox" size="5xl" :title="__('Photo')" @update:open="(value) => !value && (lightbox = null)">
      <template #default>
        <img v-if="lightbox" :src="lightbox" alt="" class="mx-auto max-h-[70vh] rounded-4 object-contain" />
      </template>
      <template #actions>
        <div class="flex w-full justify-end gap-2">
          <Button variant="subtle" icon-left="lucide-external-link" :label="__('Open original')" @click="openOriginal" />
        </div>
      </template>
    </ResponsiveDialog>
  </section>
</template>

<script setup>
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Avatar,
  Badge,
  Button,
  Dropdown,
  FormControl,
  PageHeaderBackButton,
  ScrollArea,
  Skeleton,
  Spinner,
  Tooltip,
  call,
  createResource,
  dayjs,
  debounce,
  toast,
} from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import Composer from './Composer.vue'
import DaySeparator from './DaySeparator.vue'
import MessageBubble from './MessageBubble.vue'
import NoteBubble from './NoteBubble.vue'
import TemplatePicker from './TemplatePicker.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import LabelBadges from '@/components/Labels/LabelBadges.vue'
import LabelPicker from '@/components/Labels/LabelPicker.vue'
import { embedded } from '@/data/embed'
import {
  REACTIONS,
  agentName,
  agentOf,
  agents,
  copyMessage,
  discardMessage,
  ensureThread,
  findRow,
  inbox,
  itemKey,
  loadDetails,
  loadOlder,
  loadResolveRules,
  loadThread,
  markRead,
  messageBody,
  plainMessage,
  react,
  replyWindowOpen,
  resolveNeedsDialog,
  retryMessage,
  revealMessage,
  revealNote,
  searchThread,
  setActive,
  setStatus,
  statusOf,
  isSnoozed,
  unsnooze,
} from '@/data/inbox'
import FollowUpMenu from './FollowUpMenu.vue'
import ResolveDialog from './ResolveDialog.vue'
import AssistantPanel from './AssistantPanel.vue'
import AssistantIcon from './AssistantIcon.vue'
import { assistantStatus } from '@/data/assistant'
import { can, session } from '@/data/session'
import { useTypers, useViewers, watchTypers } from '@/data/typing'
import { countLabel, dayLabel, errorMessage, formatDateTime } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contactName: { type: String, required: true },
  compact: { type: Boolean, default: false },
  panelOpen: { type: Boolean, default: false },
  listOpen: { type: Boolean, default: true },
  back: { type: [String, Object], default: null },
})

const emit = defineEmits(['details', 'list'])

const state = ensureThread(props.contactName)

const scrollArea = ref(null)
const scroller = ref(null)
const content = ref(null)
const composer = ref(null)
const stick = ref(true)
const unseen = ref(0)
const selected = ref(null)
const replyTo = ref(null)
const templatesOpen = ref(false)
const lightbox = ref(null)
const loadError = ref('')
const statusBusy = ref(false)
const highlight = ref(null)
const now = ref(Date.now())
const labelsOpen = ref(false)
const actionFor = ref(null)

const touch = computed(() => props.compact && !embedded)

const contact = computed(() => ({ ...findRow(props.contactName), ...inbox.details[props.contactName] }))

const title = computed(
  () =>
    contact.value.contact_name ||
    contact.value.mobile_no ||
    (contact.value.instagram_username && `@${contact.value.instagram_username}`) ||
    props.contactName,
)

const assignee = computed(() => {
  const user = contact.value.assigned_to
  return user ? agentName(user) : ''
})

const status = computed(() => statusOf(contact.value))

const STATUS_LOOK = {
  Open: { icon: 'lucide-circle-dot', theme: 'gray' },
  Pending: { icon: 'lucide-clock', theme: 'gray' },
  Resolved: { icon: 'lucide-circle-check', theme: 'green' },
}

const rules = ref({ require_reason: false, reasons: [], when_waiting: 'Allow', only_owner: false, is_admin: false })
const resolving = ref(false)

const customerWaiting = computed(() => {
  const last = [...state.messages].reverse().find((row) => row.kind !== 'note' && row.content_type !== 'reaction')
  return last?.type === 'Incoming'
})

const mayEdit = can('OneChat Contact', 'write')

const statusMenu = computed(() => [
  {
    group: __('Status'),
    options: [
      {
        label: status.value === 'Resolved' ? __('Reopen') : __('Mark as open'),
        icon: status.value === 'Resolved' ? 'lucide-rotate-ccw' : 'lucide-circle-dot',
        condition: () => mayEdit && status.value !== 'Open',
        onClick: () => changeStatus('Open'),
      },
      {
        label: __('Mark as pending'),
        icon: 'lucide-clock',
        condition: () => mayEdit && status.value !== 'Pending',
        onClick: () => changeStatus('Pending'),
      },
      {
        label: __('Resolve'),
        icon: 'lucide-circle-check',
        condition: () => mayEdit && status.value !== 'Resolved',
        onClick: resolve,
      },
    ],
  },
])

async function resolve() {
  try {
    rules.value = await loadResolveRules()
  } catch {
    rules.value = { ...rules.value }
  }
  const owner = contact.value.assigned_to
  if (rules.value.only_owner && !rules.value.is_admin && owner && owner !== session.user.name) {
    toast.error(__('Only the assigned agent or an admin can resolve this chat.'))
    return
  }
  if (customerWaiting.value && rules.value.when_waiting === 'Block' && !rules.value.is_admin) {
    toast.error(__('The customer is waiting for a reply. Reply first, or ask an admin to resolve it.'))
    return
  }
  if (resolveNeedsDialog(rules.value, customerWaiting.value)) {
    resolving.value = true
    return
  }
  changeStatus('Resolved')
}

async function wakeUp() {
  try {
    await unsnooze(props.contactName)
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

const phoneMenu = computed(() => [
  { label: __('Search in conversation'), icon: 'lucide-search', onClick: openSearch },
  {
    label: showActivity.value ? __('Hide activity') : __('Show activity'),
    icon: 'lucide-history',
    onClick: () => (showActivity.value = !showActivity.value),
    condition: () => isAdmin.value,
  },
  { label: __('Labels…'), icon: 'lucide-tag', onClick: () => (labelsOpen.value = true) },
  ...statusMenu.value,
  ...flowMenu.value.filter((item) => !item.disabled).map((item) => ({ ...item, label: __('Start {0}').format(item.label) })),
  { label: __('Assistant'), icon: 'lucide-sparkles', onClick: () => (assistantOpen.value = true), condition: () => assistantOn.value },
  { label: __('Contact details'), icon: 'lucide-info', onClick: () => emit('details') },
])

const assistantOpen = ref(false)
const assistantPanel = ref(null)
const assistantOn = computed(() => Boolean(assistantStatus.data?.ready))

const messageActions = computed(() => {
  const message = actionFor.value
  if (!message) return []

  return [
    { label: __('Reply'), icon: 'lucide-reply', onClick: () => startReply(message) },
    plainMessage(messageBody(message)) && {
      label: __('Copy text'),
      icon: 'lucide-copy',
      onClick: () => {
        actionFor.value = null
        copyMessage(message)
      },
    },
  ].filter(Boolean)
})

const botBusy = ref(false)
const manualFlows = createResource({ url: 'onechat.automation.flows.manual_flows', cache: 'onechat-manual-flows', auto: true })

const flowMenu = computed(() => {
  const rows = manualFlows.data || []
  if (!rows.length) return [{ label: __('No flows to start'), icon: 'lucide-info', disabled: true, onClick: () => {} }]

  return rows.map((row) => ({ label: row.flow_name || row.name, icon: 'lucide-play', onClick: () => startFlow(row) }))
})

async function startFlow(row) {
  try {
    await call('onechat.automation.flows.start_for_contact', { flow: row.name, contact: props.contactName })
    toast.success(__('{0} started').format(row.flow_name || row.name))
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

async function stopBot() {
  botBusy.value = true
  try {
    await call('onechat.automation.flows.stop_bot', { contact: props.contactName })
    toast.success(__('Bot stopped'))
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    botBusy.value = false
  }
}

const STATUS_TOASTS = {
  Open: 'Conversation reopened',
  Pending: 'Marked as pending',
  Resolved: 'Conversation resolved',
}

async function changeStatus(value, extra = {}) {
  if (statusBusy.value || value === status.value) return

  statusBusy.value = true
  try {
    await setStatus(props.contactName, value, extra)
    resolving.value = false
    toast.success(__(STATUS_TOASTS[value]))
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    statusBusy.value = false
  }
}

function toggleResolved() {
  if (status.value === 'Resolved') changeStatus('Open')
  else resolve()
}

function onKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.code === 'KeyF') {
    event.preventDefault()
    openSearch()
    return
  }

  if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.code !== 'KeyR') return

  event.preventDefault()
  toggleResolved()
}

const windowOpen = computed(() => replyWindowOpen(state.messages, contact.value, state.hasMore, now.value))
const humanWindowOpen = computed(() => replyWindowOpen(state.messages, contact.value, state.hasMore, now.value, 24 * 7))

const ACTIVITY_KEY = 'onechat.chat.activity'
const ACTIVITY_ICONS = {
  Assigned: 'lucide-user-round-check',
  Resolved: 'lucide-circle-check',
  Reopened: 'lucide-rotate-ccw',
  'Marked pending': 'lucide-clock',
  'Opted out': 'lucide-bell-off',
  'Opted in': 'lucide-bell',
  'Labels changed': 'lucide-tag',
}

const isAdmin = computed(() => !!session.user.is_admin)
const showActivity = ref(readActivityPreference())
const activities = ref([])

function readActivityPreference() {
  try {
    return localStorage.getItem(ACTIVITY_KEY) === '1'
  } catch {
    return false
  }
}

watch(showActivity, (value) => {
  try {
    localStorage.setItem(ACTIVITY_KEY, value ? '1' : '0')
  } catch {
    return
  }
})

function activityText(event) {
  if (event.action === 'Assigned') {
    return event.details === __('Unassigned')
      ? __('{0} unassigned this chat').format(event.actor)
      : __('{0} assigned this chat to {1}').format(event.actor, event.details)
  }
  if (event.action === 'Resolved') return __('{0} resolved this chat').format(event.actor)
  if (event.action === 'Reopened') return __('{0} reopened this chat').format(event.actor)
  if (event.action === 'Marked pending') return __('{0} marked this chat pending').format(event.actor)
  if (event.action === 'Opted out') return __('{0} opted the customer out of marketing').format(event.actor)
  if (event.action === 'Opted in') return __('{0} opted the customer back in').format(event.actor)
  return __('{0} changed labels: {1}').format(event.actor, event.details)
}

const loadActivity = debounce(async () => {
  const contact = props.contactName
  if (!isAdmin.value || !showActivity.value || !contact) {
    activities.value = []
    return
  }
  try {
    const rows = await call('onechat.workspace.audit.chat_activity', {
      contact,
      start: state.hasMore ? state.messages[0]?.creation : undefined,
    })
    if (contact === props.contactName) activities.value = rows
  } catch {
    activities.value = []
  }
}, 300)

watch(
  () => [
    props.contactName,
    showActivity.value,
    state.messages.length,
    contact.value.assigned_to,
    contact.value.conversation_status,
    (contact.value.labels || []).join(','),
  ],
  loadActivity,
  { immediate: true },
)

const timeline = computed(() => {
  if (!activities.value.length) return state.messages
  const events = activities.value.map((event) => ({ kind: 'activity', creation: event.creation, event }))
  return [...state.messages, ...events].sort((a, b) => dayjs(a.creation).valueOf() - dayjs(b.creation).valueOf())
})

const days = computed(() => {
  const groups = []
  let group = null
  let previous = null

  for (const message of timeline.value) {
    const key = dayjs(message.creation).format('YYYY-MM-DD')
    if (key !== group?.key) {
      group = { key, label: dayLabel(message.creation), items: [] }
      groups.push(group)
      previous = null
    }

    if (message.kind === 'activity') {
      group.items.push({ kind: 'activity', key: `activity-${message.event.key}`, event: message.event })
      continue
    }

    if (message.kind === 'note') {
      group.items.push({ kind: 'note', key: itemKey(message), message })
      previous = null
      continue
    }

    const first = !previous || previous.type !== message.type || dayjs(message.creation).diff(dayjs(previous.creation), 'minute') > 5
    group.items.push({ kind: 'message', key: itemKey(message), message, first })
    previous = message
  }

  return groups
})

function scrollToBottom(smooth = false) {
  const element = scroller.value
  if (!element) return

  element.scrollTo({ top: element.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  stick.value = true
  unseen.value = 0
}

async function older() {
  const element = scroller.value
  if (!element || !state.loaded || !state.hasMore || state.older) return

  const height = element.scrollHeight
  const top = element.scrollTop

  await loadOlder(props.contactName)
  await nextTick()
  element.scrollTop = element.scrollHeight - height + top
}

function onScroll() {
  const element = scroller.value
  const distance = element.scrollHeight - element.scrollTop - element.clientHeight

  stick.value = distance < 120
  if (stick.value) unseen.value = 0
  if (element.scrollTop < 150) older()
}

async function refresh() {
  loadError.value = ''

  try {
    await loadThread(props.contactName)
    await nextTick()
    scrollToBottom()
    if (scroller.value && scroller.value.scrollHeight <= scroller.value.clientHeight) older()
  } catch (error) {
    loadError.value = errorMessage(error)
  }
}

function startReply(message) {
  replyTo.value = message
  selected.value = null
  actionFor.value = null
}

function addReaction(message, emoji) {
  selected.value = null
  actionFor.value = null
  react(message, emoji).catch((error) => toast.error(errorMessage(error)))
}

function openOriginal() {
  window.open(lightbox.value, '_blank', 'noopener')
}

watch(
  () => {
    const last = state.messages[state.messages.length - 1]
    return last ? itemKey(last) : null
  },
  (key, previous) => {
    if (!key || !previous || key === previous) return

    const last = state.messages[state.messages.length - 1]
    const own = last.kind === 'note' ? last.owner === session.user.name : last.type === 'Outgoing'
    if (own || stick.value) nextTick(() => scrollToBottom(true))
    else unseen.value += 1
  },
)

let flash = null

watch(
  () => inbox.focus,
  async (focus) => {
    if (!focus || focus.contact !== props.contactName) return

    inbox.focus = null
    await nextTick()
    document
      .getElementById(`${focus.kind === 'message' ? 'message' : 'note'}-${focus.name}`)
      ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    highlight.value = focus.name
    clearTimeout(flash)
    flash = setTimeout(() => (highlight.value = null), 2000)
  },
)

const typers = useTypers(() => props.contactName)
const viewers = useViewers(() => props.contactName)
let stopWatchingTypers = null

const typingLine = computed(() => {
  const names = typers.value.map(agentName)
  if (!names.length) return ''
  if (names.length === 1) return __('{0} is typing…').format(names[0])
  if (names.length === 2) return __('{0} and {1} are typing…').format(names[0], names[1])

  return __('Several teammates are typing…')
})

const present = computed(() =>
  [...new Set([...typers.value, ...viewers.value])].map((user) => {
    const agent = agentOf(user)
    return { user, name: agent?.full_name || user, image: agent?.image, typing: typers.value.includes(user) }
  }),
)

const presentTooltip = computed(() =>
  __('Also here: {0}').format(
    present.value.map((person) => (person.typing ? __('{0} (typing)').format(person.name) : person.name)).join(', '),
  ),
)

const viewingLine = computed(() => {
  const names = viewers.value.filter((user) => !typers.value.includes(user)).map(agentName)
  if (!names.length) return ''
  if (names.length === 1) return __('{0} is also viewing this chat').format(names[0])
  if (names.length === 2) return __('{0} and {1} are also viewing this chat').format(names[0], names[1])
  return __('{0} teammates are also viewing this chat').format(names.length)
})

const searching = ref(false)
const searchQuery = ref('')
const searchInput = ref(null)
const results = ref([])
const resultIndex = ref(-1)
const searchBusy = ref(false)
let searchToken = 0

const searchStatus = computed(() => {
  if (searchBusy.value) return __('Searching…')
  if (searchQuery.value.trim().length < 2) return ''
  if (!results.value.length) return __('No matches')

  return __('{0} of {1}').format(resultIndex.value + 1, results.value.length)
})

async function goToResult(index) {
  const row = results.value[index]
  if (!row) return

  resultIndex.value = index
  const found = row.kind === 'note' ? await revealNote(props.contactName, row.name) : await revealMessage(props.contactName, row.name)
  if (!found) toast.error(__('That message could not be loaded.'))
}

function stepResult(delta) {
  const count = results.value.length
  if (!count) return

  goToResult((resultIndex.value + delta + count) % count)
}

const runSearch = debounce(async (query) => {
  const token = ++searchToken
  const text = query.trim()
  if (text.length < 2) {
    results.value = []
    resultIndex.value = -1
    searchBusy.value = false
    return
  }

  searchBusy.value = true
  try {
    const rows = await searchThread(props.contactName, text)
    if (token !== searchToken) return
    results.value = rows || []
    resultIndex.value = -1
    if (results.value.length) goToResult(0)
  } catch (err) {
    if (token === searchToken) toast.error(errorMessage(err))
  } finally {
    if (token === searchToken) searchBusy.value = false
  }
}, 300)

watch(searchQuery, (query) => runSearch(query))

async function openSearch() {
  searching.value = true
  await nextTick()
  searchInput.value?.$el?.querySelector?.('input')?.focus()
}

function closeSearch() {
  searchToken += 1
  searching.value = false
  searchQuery.value = ''
  results.value = []
  resultIndex.value = -1
  searchBusy.value = false
}

function toggleSearch() {
  searching.value ? closeSearch() : openSearch()
}

let resizer = null
let clock = null

onMounted(() => {
  scroller.value = scrollArea.value?.viewportElement || null
  scroller.value?.addEventListener('scroll', onScroll, { passive: true })
  setActive(props.contactName)
  stopWatchingTypers = watchTypers(props.contactName)
  if (!agents.data) agents.fetch()

  if (state.loaded) nextTick(scrollToBottom)
  refresh()

  markRead(props.contactName)
  loadDetails(props.contactName)
    .then(() => markRead(props.contactName))
    .catch(() => {})

  resizer = new ResizeObserver(() => {
    if (stick.value && scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
  if (content.value) resizer.observe(content.value)

  clock = setInterval(() => (now.value = Date.now()), 60000)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  stopWatchingTypers?.()
  scroller.value?.removeEventListener('scroll', onScroll)
  resizer?.disconnect()
  clearInterval(clock)
  clearTimeout(flash)
  document.removeEventListener('keydown', onKeydown)
  if (inbox.active === props.contactName) setActive(null)
})

defineExpose({ focus: () => composer.value?.focus() })
</script>

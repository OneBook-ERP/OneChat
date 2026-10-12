<template>
  <component
    :is="selectable ? 'button' : 'router-link'"
    v-bind="selectable ? { type: 'button', 'aria-pressed': selected } : { to, 'aria-current': active ? 'page' : undefined }"
    class="flex w-full items-center gap-3 rounded-4 px-2.5 text-left transition-colors focus-visible:focus-ring"
    :class="[
      compact ? 'min-h-16 py-3' : 'py-2.5',
      selected
        ? 'bg-surface-gray-3'
        : active && !selectable
        ? 'bg-surface-gray-3'
        : compact
        ? 'active:bg-surface-gray-2'
        : 'hover:bg-surface-gray-2',
    ]"
    @click="selectable && emit('toggle')"
  >
    <span v-if="selectable" class="flex shrink-0 items-center" @click.stop="emit('toggle')">
      <Checkbox :model-value="selected" :aria-label="__('Select {0}').format(title)" />
    </span>
    <Avatar :image="row.profile_image" :label="title" :size="compact ? '2xl' : 'xl'" class="shrink-0" />

    <div class="min-w-0 flex-1">
      <div class="flex gap-2" :class="compact ? 'items-center' : 'items-baseline'">
        <TruncatedText
          as="p"
          class="min-w-0 truncate text-base"
          :class="['shrink', unread ? 'font-semibold' : 'font-medium', resolved && !active ? 'text-ink-gray-6' : 'text-ink-gray-9']"
          :text="title"
        />
        <Tooltip v-if="isInstagram(row)" :text="row.instagram_username ? `Instagram · @${row.instagram_username}` : __('Instagram')">
          <span class="flex shrink-0 text-ink-gray-6">
            <ChannelIcon channel="Instagram" class="size-3.5" />
          </span>
        </Tooltip>
        <LabelBadges v-if="row.labels?.length" :names="row.labels" :max="3" dots />
        <span class="flex-1" />
        <Tooltip
          v-if="row.sla_due_at && !isSnoozed(row)"
          :text="
            isOverdue(row)
              ? __('Waiting since {0}').format(formatDateTime(row.sla_due_at))
              : __('Reply by {0}').format(formatDateTime(row.sla_due_at))
          "
        >
          <span class="flex shrink-0 items-center" :class="isOverdue(row) ? 'text-ink-red-7' : 'text-ink-gray-5'">
            <span class="lucide-timer size-3.5" :aria-label="isOverdue(row) ? __('Overdue') : __('Waiting for a reply')" />
          </span>
        </Tooltip>
        <Tooltip v-if="isSnoozed(row)" :text="__('Snoozed until {0}').format(formatDateTime(row.snoozed_until))">
          <span class="flex shrink-0 items-center gap-1 text-xs tabular-nums text-ink-amber-7">
            <span class="lucide-alarm-clock size-3" aria-hidden="true" />
            {{ shortTime(row.snoozed_until) }}
          </span>
        </Tooltip>
        <span v-else class="shrink-0 text-xs tabular-nums" :class="unread ? 'font-medium text-ink-green-7' : 'text-ink-gray-5'">
          {{ shortTime(row.last_message_at) }}
        </span>
      </div>

      <div class="mt-1 flex items-center gap-2">
        <p class="min-w-0 flex-1 truncate text-sm" :class="unread ? 'text-ink-gray-8' : 'text-ink-gray-5'">
          <span v-if="row.last_message_type === 'Outgoing' && row.last_message" class="text-ink-gray-5">
            {{ __('You:') }}
          </span>
          {{ row.last_message || __('No messages yet') }}
        </p>

        <Tooltip v-if="indicator" :text="indicator.label">
          <span class="flex shrink-0 text-ink-gray-5">
            <span :class="indicator.icon" class="size-3.5" aria-hidden="true" />
            <span class="sr-only">{{ indicator.label }}</span>
          </span>
        </Tooltip>

        <Tooltip v-if="agent && !compact" :text="__('Assigned to {0}').format(agent.full_name || agent.name)">
          <span class="flex shrink-0">
            <Avatar :image="agent.image" :label="agent.full_name || agent.name" size="xs" />
          </span>
        </Tooltip>

        <Badge v-if="unread" variant="solid" theme="green" size="sm" class="shrink-0 tabular-nums">
          {{ countLabel(row.unread_count) }}
        </Badge>
      </div>
    </div>
  </component>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Avatar, Badge, Checkbox, Tooltip } from 'frappe-ui'
import LabelBadges from '@/components/Labels/LabelBadges.vue'
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import { agents, isInstagram, isOverdue, isSnoozed, statusOf } from '@/data/inbox'
import { countLabel, formatDateTime, shortTime } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  row: { type: Object, required: true },
  active: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle'])

const route = useRoute()

const title = computed(
  () =>
    props.row.contact_name || props.row.mobile_no || (props.row.instagram_username && `@${props.row.instagram_username}`) || props.row.name,
)
const unread = computed(() => props.row.unread_count > 0)
const resolved = computed(() => statusOf(props.row) === 'Resolved')

const indicator = computed(() => {
  if (props.row.bot_flow) return { icon: 'lucide-bot', label: __('Bot: {0}').format(props.row.bot_flow) }
  const status = statusOf(props.row)
  if (status === 'Pending') return { icon: 'lucide-clock', label: __('Pending') }
  if (status === 'Resolved') return { icon: 'lucide-circle-check', label: __('Resolved') }
  return null
})

const to = computed(() => ({ name: 'Inbox', params: { contact: props.row.name }, query: route.query }))

const agent = computed(() => {
  if (!props.row.assigned_to) return null

  return (agents.data || []).find((user) => user.name === props.row.assigned_to) || { name: props.row.assigned_to }
})
</script>

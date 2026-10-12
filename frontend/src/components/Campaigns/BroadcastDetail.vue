<template>
  <ResponsiveDialog v-model:open="open" :title="doc?.title || __('Broadcast')" size="3xl">
    <template #default>
      <div v-if="!data && detail.loading" class="flex flex-col gap-3">
        <Skeleton class="h-20 w-full" />
        <Skeleton v-for="row in 4" :key="row" class="h-8 w-full" />
      </div>

      <ErrorMessage v-else-if="detail.error && !data" :message="errorMessage(detail.error)" />

      <div v-else-if="data" class="flex flex-col gap-5">
        <div class="flex flex-wrap items-center gap-2 text-sm text-ink-gray-6">
          <CampaignStatusBadge :status="status" />
          <span>{{ doc.name }}</span>
          <span>·</span>
          <span>{{ doc.template }}</span>
          <template v-if="doc.recipient_list || doc.segment">
            <span>·</span>
            <span>{{ doc.segment ? __('Segment: {0}').format(doc.segment) : doc.recipient_list }}</span>
          </template>
          <span v-if="live" class="ml-auto inline-flex items-center gap-1.5 text-ink-gray-5">
            <span class="size-2 animate-pulse rounded-full bg-surface-green-6" />
            {{ __('Live') }}
          </span>
        </div>

        <Alert
          v-if="status === 'Scheduled'"
          theme="blue"
          :title="__('Scheduled for {0}').format(formatDateTime(doc.scheduled_time))"
          :description="__('It sends automatically at that time. Send now to skip the wait.')"
        />

        <Alert
          v-if="smartWaiting"
          theme="blue"
          :title="__('{0} waiting for their best hour').format(formatNumber(smartWaiting))"
          :description="__('Smart send time is on. The next batch goes out at {0}.').format(formatDateTime(data.smart_pending[0].at))"
        />

        <Alert
          v-if="doc.follow_up_of"
          theme="gray"
          :title="__('Follow-up to {0}').format(doc.follow_up_of)"
          :description="doc.follow_up_audience ? __('Audience: {0}').format(__(doc.follow_up_audience)) : ''"
        />

        <div v-if="doc.docstatus === 1" class="flex flex-col gap-3">
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <NumberCard :title="__('Recipients')" :value="progress.total" />
            <NumberCard :title="__('Sent')" :value="progress.sent" />
            <NumberCard :title="__('Delivered')" :value="(progress.delivered || 0) + (progress.read || 0)" />
            <NumberCard :title="__('Read')" :value="progress.read || 0" />
            <NumberCard :title="__('Failed')" :value="progress.failed" />
            <NumberCard v-if="progress.skipped" :title="__('Skipped (opted out)')" :value="progress.skipped" />
          </div>
          <Progress :value="progress.percent" size="md" :label="__('Processed')" hint />
        </div>

        <ABResults v-if="doc.ab_test && doc.docstatus === 1" :name="doc.name" @changed="emit('changed')" />

        <div v-if="doc.docstatus === 1" class="flex flex-col gap-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-base font-medium text-ink-gray-8">{{ __('Messages') }}</p>
            <TabButtons v-model="filter" :options="filterOptions" />
          </div>

          <p
            v-if="!messages.length"
            class="rounded-4 border border-dashed border-outline-gray-2 px-4 py-8 text-center text-sm text-ink-gray-5"
          >
            {{ data.messages.length ? __('No messages with this status') : __('Messages appear here as they are queued.') }}
          </p>

          <ScrollArea v-else viewport-class="max-h-80">
            <List :columns="{ base: ['minmax(0,1fr)', '110px'], md: ['minmax(0,1fr)', '120px', '140px'] }" :row-height="44">
              <ListHeader>
                <ListHeaderCell>{{ __('Number') }}</ListHeaderCell>
                <ListHeaderCell>{{ __('Status') }}</ListHeaderCell>
                <ListHeaderCell class="max-md:hidden">{{ __('Updated') }}</ListHeaderCell>
              </ListHeader>
              <ListRows v-slot="{ item, value }" :items="messages" row-key="name">
                <ListRow :value="value">
                  <ListCell><TruncatedText class="truncate text-base text-ink-gray-8" :text="item.to" /></ListCell>
                  <ListCell><CampaignStatusBadge :status="item.status || 'Queued'" size="sm" /></ListCell>
                  <ListCell class="max-md:hidden"
                    ><span class="text-sm text-ink-gray-5">{{ timeAgo(item.modified) }}</span></ListCell
                  >
                </ListRow>
              </ListRows>
            </List>
          </ScrollArea>
        </div>

        <div v-else class="flex flex-col gap-2">
          <p class="text-base font-medium text-ink-gray-8">
            {{ __('Recipients') }}
            <span class="font-normal text-ink-gray-5">{{ formatNumber(doc.recipient_count || doc.recipients?.length || 0) }}</span>
          </p>
          <ScrollArea v-if="doc.recipients?.length" class="rounded-4 border border-outline-gray-1" viewport-class="max-h-60">
            <ul>
              <li
                v-for="recipient in doc.recipients.slice(0, 200)"
                :key="recipient.name"
                class="flex items-center justify-between gap-2 border-b border-outline-gray-1 px-3 py-1.5 text-base last:border-0"
              >
                <span class="text-ink-gray-8">{{ recipient.mobile_number }}</span>
                <TruncatedText class="truncate text-ink-gray-5" :text="recipient.recipient_name" />
              </li>
            </ul>
          </ScrollArea>
          <p v-else-if="doc.segment" class="text-sm text-ink-gray-5">
            {{ __('Recipients come from the segment {0}.').format(doc.segment) }}
          </p>
          <p v-else class="text-sm text-ink-gray-5">{{ __('Recipients come from the list {0}.').format(doc.recipient_list) }}</p>
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex w-full flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-1">
          <Button
            v-if="doc && doc.docstatus === 0"
            variant="ghost"
            theme="red"
            icon-left="lucide-trash-2"
            :label="__('Delete')"
            @click="remove"
          />
          <Button
            v-if="doc"
            variant="ghost"
            icon-left="lucide-external-link"
            :label="__('Open in desk')"
            :link="`/app/bulk-whatsapp-message/${doc.name}`"
          />
        </div>
        <div class="flex items-center gap-2">
          <Button
            v-if="status === 'Scheduled'"
            variant="subtle"
            icon-left="lucide-calendar-x"
            :label="__('Unschedule')"
            :loading="busy === 'unschedule'"
            @click="unschedule"
          />
          <Button
            v-if="doc && doc.docstatus === 0"
            variant="solid"
            icon-left="lucide-send"
            :label="__('Send now')"
            :loading="busy === 'send'"
            @click="sendNow"
          />
          <Button
            v-if="doc?.docstatus === 1 && progress.sent"
            variant="subtle"
            icon-left="lucide-reply-all"
            :label="__('Follow up')"
            @click="followUp = true"
          />
          <Button
            v-if="doc?.docstatus === 1 && progress.failed"
            variant="solid"
            icon-left="lucide-rotate-ccw"
            :label="__('Retry {0} failed').format(progress.failed)"
            :loading="busy === 'retry'"
            @click="retry"
          />
        </div>
      </div>
    </template>
  </ResponsiveDialog>

  <FollowUpDialog
    v-model:open="followUp"
    :name="name"
    :template="doc?.template || ''"
    :account="doc?.whatsapp_account || ''"
    @created="(created) => emit('open', created)"
  />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Alert, Button, ErrorMessage, Progress, ScrollArea, Skeleton, TabButtons, call, createResource, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { NumberCard } from 'frappe-ui/charts'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from 'frappe-ui/list'
import ABResults from './ABResults.vue'
import CampaignStatusBadge from './CampaignStatusBadge.vue'
import FollowUpDialog from './FollowUpDialog.vue'
import { useUI } from '@/stores/ui'
import { errorMessage, formatDateTime, formatNumber, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
})

const emit = defineEmits(['changed', 'open'])

const open = defineModel('open', { type: Boolean, default: false })

const POLL = 4000
const ACTIVE = ['Queued', 'In Progress']

const ui = useUI()
const filter = ref('all')
const busy = ref('')
const followUp = ref(false)
let timer = null

const detail = createResource({
  url: 'onechat.campaigns.broadcasts.broadcast',
  makeParams: () => ({ name: props.name }),
})

const data = computed(() => (detail.data?.doc?.name === props.name ? detail.data : null))
const doc = computed(() => data.value?.doc || null)
const progress = computed(() => data.value?.progress || { total: 0, sent: 0, failed: 0, percent: 0 })
const smartWaiting = computed(() => (data.value?.smart_pending || []).reduce((sum, row) => sum + row.count, 0))

const status = computed(() => {
  if (!doc.value) return ''
  if (doc.value.docstatus === 0 && doc.value.scheduled_time) return 'Scheduled'

  return doc.value.status || 'Draft'
})

const live = computed(() => doc.value?.docstatus === 1 && (ACTIVE.includes(doc.value.status) || progress.value.queued > 0))

const filterOptions = computed(() => {
  const counts = data.value?.counts || {}

  return [
    { label: __('All'), value: 'all' },
    { label: `${__('Failed')} ${counts.failed || 0}`, value: 'failed' },
    { label: `${__('Queued')} ${counts.queued || 0}`, value: 'queued' },
    { label: `${__('Read')} ${counts.read || 0}`, value: 'read' },
  ]
})

const messages = computed(() => {
  const rows = data.value?.messages || []
  if (filter.value === 'all') return rows

  return rows.filter((row) => String(row.status || 'queued').toLowerCase() === filter.value)
})

function stop() {
  clearTimeout(timer)
  timer = null
}

async function poll() {
  stop()
  if (!open.value || !props.name) return

  await detail.reload().catch(() => null)
  if (open.value && live.value) timer = setTimeout(poll, POLL)
}

watch(
  () => [open.value, props.name],
  ([value]) => {
    filter.value = 'all'
    if (value) poll()
    else stop()
  },
  { immediate: true },
)

onBeforeUnmount(stop)

async function run(key, action, message) {
  busy.value = key
  try {
    await action()
    if (message) toast.success(message)
    emit('changed')
    await poll()
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    busy.value = ''
  }
}

function retry() {
  run('retry', () => call('onechat.campaigns.bulk_messaging.retry_failed', { name: props.name }), __('Failed messages queued again'))
}

function unschedule() {
  run('unschedule', () => call('onechat.campaigns.broadcasts.cancel_schedule', { name: props.name }), __('Schedule removed'))
}

function sendNow() {
  ui.confirm({
    title: __('Send this broadcast now?'),
    message: __('Messages go out to {0} recipients right away.').format(formatNumber(doc.value.recipient_count || 0)),
    action: __('Send now'),
    onConfirm: () =>
      run(
        'send',
        async () => {
          const fresh = await call('frappe.client.get', { doctype: 'Bulk WhatsApp Message', name: props.name })
          await call('frappe.client.submit', { doc: { ...fresh, scheduled_time: null } })
        },
        __('Broadcast queued'),
      ),
  })
}

function remove() {
  ui.confirm({
    title: __('Delete this draft?'),
    message: __('This cannot be undone.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: 'Bulk WhatsApp Message', name: props.name })
      toast.success(__('Deleted'))
      emit('changed')
      open.value = false
    },
  })
}
</script>

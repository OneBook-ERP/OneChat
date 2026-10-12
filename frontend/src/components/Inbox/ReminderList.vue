<template>
  <section v-if="rows.length" class="mt-4 flex flex-col gap-1.5">
    <h3 class="text-sm font-medium text-ink-gray-7">
      {{ __('Follow-ups') }}
      <span class="ml-1 tabular-nums text-ink-gray-5">{{ rows.length }}</span>
    </h3>
    <Tooltip
      v-for="row in all ? rows : rows.slice(0, LIMIT)"
      :key="row.name"
      :text="
        [
          row.note,
          row.user === session.user.name ? __('For you') : __('For {0}').format(row.user_name),
          row.only_if_no_reply ? __('Only if no reply') : '',
        ]
          .filter(Boolean)
          .join(' · ')
      "
    >
      <div class="flex items-center gap-2 rounded-4 bg-surface-blue-1 py-1 pl-2.5 pr-0.5">
        <span class="lucide-bell-ring size-3.5 shrink-0 text-ink-blue-6" aria-hidden="true" />
        <p class="min-w-0 flex-1 truncate text-sm text-ink-gray-8">
          <span class="font-medium">{{ formatDateTime(row.remind_at) }}</span>
          <span v-if="row.note" class="text-ink-gray-6"> · {{ row.note }}</span>
        </p>
        <Button variant="ghost" size="sm" icon="lucide-x" :label="__('Cancel reminder')" @click="cancel(row)" />
      </div>
    </Tooltip>
    <Button
      v-if="rows.length > LIMIT"
      variant="ghost"
      size="sm"
      class="self-start"
      :label="all ? __('Show less') : __('Show all {0}').format(rows.length)"
      @click="all = !all"
    />
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, Tooltip, toast } from 'frappe-ui'
import { cancelReminder, contactReminders, followups } from '@/data/inbox'
import { session } from '@/data/session'
import { errorMessage, formatDateTime } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({ contact: { type: String, required: true } })

const rows = ref([])
const LIMIT = 2
const all = ref(false)
let ticket = 0

async function load() {
  const current = ++ticket
  try {
    const result = await contactReminders(props.contact)
    if (current === ticket) rows.value = result
  } catch {
    if (current === ticket) rows.value = []
  }
}

async function cancel(row) {
  try {
    await cancelReminder(row.name)
    rows.value = rows.value.filter((item) => item.name !== row.name)
    toast.success(__('Reminder cancelled'))
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

watch(() => [props.contact, followups.version], load, { immediate: true })
</script>

<template>
  <Dropdown :options="menu" align="end">
    <Button
      variant="ghost"
      :size="size"
      :class="{ 'bg-surface-gray-3': snoozed }"
      :label="__('Snooze or follow up')"
      :tooltip="snoozed ? __('Snoozed until {0}').format(when(contact.snoozed_until)) : __('Snooze or follow up')"
    >
      <template #icon>
        <span :class="[snoozed ? 'lucide-alarm-clock-check' : 'lucide-alarm-clock', iconClass]" aria-hidden="true" />
      </template>
    </Button>
  </Dropdown>

  <ResponsiveDialog v-model:open="dialog.open" :title="dialog.mode === 'snooze' ? __('Snooze until') : __('Remind me')" size="md">
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl v-model="dialog.at" type="datetime" :label="__('When')" required />
        <template v-if="dialog.mode === 'remind'">
          <Switch
            v-model="dialog.onlyIfNoReply"
            :label="__('Only if the customer has not replied')"
            :description="__('Skipped automatically when they write back before then')"
          />
          <FormControl v-model="dialog.note" type="textarea" :rows="2" :label="__('Note')" :placeholder="__('Send the revised quote')" />
        </template>
        <p v-else class="text-sm text-ink-gray-5">
          {{ __('The chat leaves your inbox and comes back at this time, or earlier if the customer replies.') }}
        </p>
        <ErrorMessage :message="dialog.error" />
      </div>
    </template>
    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="dialog.open = false" />
        <Button
          variant="solid"
          :loading="dialog.saving"
          :label="dialog.mode === 'snooze' ? __('Snooze') : __('Set reminder')"
          @click="confirm"
        />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { Button, Dropdown, ErrorMessage, FormControl, Switch, dayjs, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { addReminder, isSnoozed, snooze, unsnooze } from '@/data/inbox'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contact: { type: Object, required: true },
  size: { type: String, default: 'md' },
  iconClass: { type: String, default: 'size-4.5' },
})
const emit = defineEmits(['reminded'])

const FORMAT = 'YYYY-MM-DD HH:mm:ss'
const dialog = reactive({ open: false, mode: 'snooze', at: '', onlyIfNoReply: true, note: '', saving: false, error: '' })

const snoozed = computed(() => isSnoozed(props.contact))

function at(hour, day) {
  return day.hour(hour).minute(0).second(0)
}

function presets() {
  const now = dayjs()
  const out = []
  if (now.hour() < 18) out.push({ label: __('Later today'), hint: now.add(3, 'hour'), value: now.add(3, 'hour') })
  out.push({ label: __('Tomorrow morning'), value: at(10, now.add(1, 'day')) })
  const monday = now.add((8 - now.day()) % 7 || 7, 'day')
  out.push({ label: __('Next Monday'), value: at(10, monday) })
  out.push({ label: __('In a week'), value: at(10, now.add(7, 'day')) })
  return out
}

function when(value) {
  const moment = dayjs(value)
  if (moment.isSame(dayjs(), 'day')) return moment.format('h:mm a')
  if (moment.isSame(dayjs().add(1, 'day'), 'day')) return __('tomorrow {0}').format(moment.format('h:mm a'))
  return moment.format('ddd D MMM, h:mm a')
}

async function doSnooze(value) {
  try {
    await snooze(props.contact.name, value.format(FORMAT))
    toast.success(__('Snoozed until {0}').format(when(value)))
    return true
  } catch (err) {
    toast.error(errorMessage(err))
    return false
  }
}

async function doRemind(value, onlyIfNoReply = true, note = '') {
  try {
    const row = await addReminder(props.contact.name, { remindAt: value.format(FORMAT), onlyIfNoReply, note })
    toast.success(
      onlyIfNoReply
        ? __('We will remind you {0} if they have not replied').format(when(value))
        : __('We will remind you {0}').format(when(value)),
    )
    emit('reminded', row)
    return true
  } catch (err) {
    toast.error(errorMessage(err))
    return false
  }
}

function openDialog(mode) {
  Object.assign(dialog, {
    open: true,
    mode,
    at: at(10, dayjs().add(1, 'day')).format(FORMAT),
    onlyIfNoReply: true,
    note: '',
    saving: false,
    error: '',
  })
}

async function confirm() {
  const value = dayjs(dialog.at)
  if (!dialog.at || !value.isValid() || !value.isAfter(dayjs())) {
    dialog.error = __('Pick a time in the future')
    return
  }
  dialog.saving = true
  const done = dialog.mode === 'snooze' ? await doSnooze(value) : await doRemind(value, dialog.onlyIfNoReply, dialog.note)
  dialog.saving = false
  if (done) dialog.open = false
}

async function wake() {
  try {
    await unsnooze(props.contact.name)
    toast.success(__('Back in your inbox'))
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

const menu = computed(() => [
  ...(snoozed.value ? [{ label: __('Unsnooze now'), icon: 'lucide-alarm-clock-off', onClick: wake }] : []),
  {
    group: __('Snooze until'),
    options: [
      ...presets().map((preset) => ({
        label: `${preset.label} · ${when(preset.value)}`,
        icon: 'lucide-alarm-clock',
        onClick: () => doSnooze(preset.value),
      })),
      { label: __('Pick a date and time…'), icon: 'lucide-calendar-clock', onClick: () => openDialog('snooze') },
    ],
  },
  {
    group: __('Remind me if no reply'),
    options: [
      { label: __('In 1 day'), icon: 'lucide-bell-ring', onClick: () => doRemind(dayjs().add(1, 'day')) },
      { label: __('In 2 days'), icon: 'lucide-bell-ring', onClick: () => doRemind(dayjs().add(2, 'day')) },
      { label: __('In a week'), icon: 'lucide-bell-ring', onClick: () => doRemind(dayjs().add(7, 'day')) },
      { label: __('Custom reminder…'), icon: 'lucide-bell-plus', onClick: () => openDialog('remind') },
    ],
  },
])
</script>

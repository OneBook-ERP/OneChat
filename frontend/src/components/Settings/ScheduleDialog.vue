<template>
  <ResponsiveDialog v-model:open="open" :title="leaveOnly ? __('My time off') : __('Schedule for {0}').format(name)" size="2xl">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-2">
        <Skeleton v-for="index in 5" :key="index" class="h-9 w-full rounded-3" />
      </div>

      <div v-else class="flex flex-col gap-6">
        <section v-if="!leaveOnly" class="flex flex-col gap-3">
          <Switch
            v-model="form.use_shift"
            :label="__('Use working hours')"
            :description="__('Outside these hours they are set to Away and auto-assign skips them. They can still reply to their chats.')"
          />

          <div v-if="form.use_shift" class="divide-y divide-outline-gray-1 rounded-4 border border-outline-gray-2">
            <div v-for="day in week" :key="day.weekday" class="flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-start">
              <div class="flex h-7 w-36 shrink-0 items-center gap-2">
                <Switch
                  v-model="day.open"
                  :aria-label="__('Works on {0}').format(__(day.weekday))"
                  @update:model-value="(value) => toggleDay(day, value)"
                />
                <span class="text-base text-ink-gray-8">{{ __(day.weekday) }}</span>
              </div>
              <p v-if="!day.open" class="flex h-7 items-center text-base text-ink-gray-5">{{ __('Day off') }}</p>
              <div v-else class="flex flex-1 flex-col gap-2">
                <div v-for="(range, index) in day.ranges" :key="index" class="flex items-center gap-2">
                  <TimePicker v-model="range.open_time" class="w-28" :placeholder="__('Start')" />
                  <span class="text-sm text-ink-gray-5">{{ __('to') }}</span>
                  <TimePicker v-model="range.close_time" class="w-28" :placeholder="__('End')" />
                  <Button variant="ghost" icon="lucide-x" :label="__('Remove')" @click="removeRange(day, index)" />
                </div>
                <Button
                  class="self-start"
                  variant="ghost"
                  size="sm"
                  icon-left="lucide-plus"
                  :label="__('Add hours')"
                  @click="addRange(day)"
                />
              </div>
            </div>
          </div>
          <Button
            v-if="form.use_shift"
            class="self-start"
            variant="ghost"
            size="sm"
            icon-left="lucide-copy"
            :label="__('Copy Monday to weekdays')"
            @click="copyMonday"
          />
        </section>

        <section class="flex flex-col gap-3">
          <div class="flex items-center justify-between gap-2">
            <div>
              <p class="text-base font-medium text-ink-gray-8">{{ __('Leave') }}</p>
              <p class="text-sm text-ink-gray-5">{{ __('Away all day and skipped by auto-assign.') }}</p>
            </div>
            <Button variant="subtle" size="sm" icon-left="lucide-plus" :label="__('Add leave')" @click="addLeave" />
          </div>
          <p v-if="!form.leaves.length" class="rounded-4 bg-surface-gray-1 px-3 py-3 text-center text-sm text-ink-gray-5">
            {{ __('No upcoming leave.') }}
          </p>
          <div
            v-for="(row, index) in form.leaves"
            :key="index"
            class="grid grid-cols-[1fr_1fr_auto] items-end gap-2 sm:grid-cols-[9rem_9rem_minmax(0,1fr)_auto]"
          >
            <FormControl v-model="row.from_date" type="date" :label="index ? '' : __('From')" />
            <FormControl v-model="row.to_date" type="date" :label="index ? '' : __('To')" />
            <FormControl
              v-model="row.reason"
              type="text"
              class="col-span-2 sm:col-span-1"
              :label="index ? '' : __('Reason')"
              :placeholder="__('Optional')"
            />
            <Button variant="ghost" icon="lucide-x" :label="__('Remove')" @click="form.leaves.splice(index, 1)" />
          </div>
        </section>

        <ErrorMessage :message="error" />
      </div>
    </template>

    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button variant="solid" :loading="saving" :label="__('Save')" @click="save" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, Skeleton, Switch, TimePicker, call, dayjs, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

const props = defineProps({
  user: { type: String, default: '' },
  name: { type: String, default: '' },
  leaveOnly: { type: Boolean, default: false },
})
const emit = defineEmits(['saved'])

const open = defineModel('open', { type: Boolean, default: false })

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const week = ref([])
const form = reactive({ use_shift: false, leaves: [] })

function buildWeek(shifts) {
  return WEEKDAYS.map((weekday) => {
    const ranges = shifts.filter((row) => row.weekday === weekday).map((row) => ({ open_time: row.open_time, close_time: row.close_time }))
    return { weekday, open: ranges.length > 0, ranges }
  })
}

function toggleDay(day, value) {
  if (value && !day.ranges.length) day.ranges.push({ open_time: '09:00', close_time: '18:00' })
}

function addRange(day) {
  const last = day.ranges[day.ranges.length - 1]
  day.ranges.push(last ? { open_time: last.close_time || '14:00', close_time: '' } : { open_time: '09:00', close_time: '18:00' })
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

function addLeave() {
  const today = dayjs().format('YYYY-MM-DD')
  form.leaves.push({ from_date: today, to_date: today, reason: '' })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await call('onechat.workspace.shifts.schedule', { user: props.user || undefined })
    form.use_shift = Boolean(data.use_shift)
    form.leaves = data.leaves.map((row) => ({ ...row }))
    week.value = buildWeek(data.shifts)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function shiftRows() {
  return week.value.flatMap((day) =>
    day.open ? day.ranges.filter((range) => range.open_time && range.close_time).map((range) => ({ weekday: day.weekday, ...range })) : [],
  )
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const leaves = JSON.stringify(form.leaves)
    const data = props.leaveOnly
      ? await call('onechat.workspace.shifts.save_leaves', { leaves })
      : await call('onechat.workspace.shifts.save_schedule', {
          user: props.user,
          use_shift: form.use_shift ? 1 : 0,
          shifts: JSON.stringify(shiftRows()),
          leaves,
        })
    toast.success(__('Schedule saved'))
    emit('saved', data)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

watch(open, (value) => value && load())
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <TabButtons v-model="period" :options="options" />
    <DateRangePicker v-if="period === 'custom'" v-model="dates" class="w-60" :placeholder="__('Pick a date range')" :max="today" />
  </div>
</template>

<script setup>
import { DateRangePicker, TabButtons, dayjs } from 'frappe-ui'
import { translate as __ } from '@/translation'

const period = defineModel('period', { type: String, default: '168' })
const dates = defineModel('dates', { type: Array, default: () => [] })

const today = dayjs().format('YYYY-MM-DD')

const options = [
  { label: __('24h'), value: '24' },
  { label: __('7d'), value: '168' },
  { label: __('30d'), value: '720' },
  { label: __('90d'), value: '2160' },
  { label: __('Custom'), value: 'custom' },
]
</script>

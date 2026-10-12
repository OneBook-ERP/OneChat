<template>
  <div class="flex flex-col gap-1.5">
    <FormLabel v-if="label" :label="label" :required="required" />
    <div
      class="flex min-w-0 items-center rounded-4 border text-base transition-colors"
      :class="[
        size === 'md' ? 'h-8' : 'h-7',
        disabled
          ? 'border-transparent bg-surface-gray-1'
          : 'border-[--surface-gray-2] bg-surface-gray-2 hover:border-outline-elevation-2 hover:bg-surface-gray-3 focus-within:border-outline-gray-4 focus-within:bg-surface-base focus-within:shadow-sm',
        problem ? '!border-outline-red-3' : '',
      ]"
    >
      <Combobox
        :model-value="country?.iso || null"
        :options="options"
        :disabled="disabled"
        :placeholder="__('Search country or code')"
        align="start"
        @update:model-value="pickCountry"
      >
        <template #trigger>
          <button
            type="button"
            class="flex h-full shrink-0 items-center gap-1.5 rounded-l-4 pl-2 pr-1 text-ink-gray-8 outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 disabled:cursor-not-allowed"
            :disabled="disabled"
            :aria-label="country ? __('Country: {0} +{1}').format(country.name, country.dial) : __('Choose country')"
          >
            <img
              v-if="country && !broken[country.iso]"
              :src="flagSrc(country.iso)"
              alt=""
              class="h-3 w-[1.125rem] shrink-0 rounded-1 object-cover shadow-[0_0_0_1px_rgba(0,0,0,0.08)]"
              @error="broken[country.iso] = true"
            />
            <span v-else class="text-xs font-medium text-ink-gray-5">{{ country?.iso || '🌐' }}</span>
            <span class="tabular-nums">+{{ country?.dial || '' }}</span>
          </button>
        </template>
        <template #item-prefix="{ item }">
          <img
            v-if="!broken[item.value]"
            :src="flagSrc(item.value)"
            alt=""
            class="h-3 w-[1.125rem] shrink-0 rounded-1 object-cover shadow-[0_0_0_1px_rgba(0,0,0,0.08)]"
            loading="lazy"
            @error="broken[item.value] = true"
          />
          <span v-else class="w-[1.125rem] text-center text-[10px] font-medium text-ink-gray-5">{{ item.value }}</span>
        </template>
      </Combobox>
      <FormControl
        class="min-w-0 flex-1"
        variant="ghost"
        type="tel"
        inputmode="tel"
        autocomplete="tel-national"
        :size="size"
        :model-value="national"
        :placeholder="placeholder || __('Enter mobile number')"
        :disabled="disabled"
        @update:model-value="typeNumber"
        @paste="paste"
      />
    </div>
    <p v-if="problem" class="text-xs text-ink-red-7">{{ problem }}</p>
    <p v-else-if="description" class="text-xs text-ink-gray-5">{{ description }}</p>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Combobox, FormControl, FormLabel } from 'frappe-ui'
import { COUNTRIES, defaultCountry, joinNumber, splitNumber, validNumber } from '@/data/countries'
import { useFlags } from '@/stores/flags'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  description: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: 'sm' },
})
const emit = defineEmits(['update:modelValue'])

const flagStore = useFlags()

const country = ref(defaultCountry())
const national = ref('')
const touched = ref(false)
const broken = reactive({})
let echo = null

const options = COUNTRIES.map((row) => ({ label: `${row.name} +${row.dial}`, value: row.iso }))

const problem = computed(() => {
  if (!touched.value || !national.value) return ''
  return validNumber(country.value, national.value)
    ? ''
    : __('This number looks too short or too long for {0}.').format(country.value?.name || __('this country'))
})

function flagSrc(iso) {
  return flagStore.url(iso)
}

function publish() {
  const value = joinNumber(country.value, national.value)
  echo = value
  emit('update:modelValue', value)
}

function load(value) {
  if (value === echo) return
  const parts = splitNumber(value, country.value)
  if (parts.country) country.value = parts.country
  national.value = parts.national
}

function pickCountry(iso) {
  const found = COUNTRIES.find((row) => row.iso === iso)
  if (!found) return
  country.value = found
  publish()
}

function typeNumber(value) {
  touched.value = true
  const text = String(value || '')
  if (/^\s*(\+|00)/.test(text)) {
    const parts = splitNumber(text, country.value)
    if (parts.country) country.value = parts.country
    national.value = parts.national
  } else {
    national.value = text.replace(/[^\d\s()-]/g, '')
  }
  publish()
}

function paste(event) {
  const text = event.clipboardData?.getData('text') || ''
  if (!/^\s*(\+|00)/.test(text)) return
  event.preventDefault()
  typeNumber(text)
}

watch(() => props.modelValue, load, { immediate: true })
watch(
  () => country.value?.iso,
  (iso) => iso && flagStore.load(iso),
  { immediate: true },
)
flagStore.warm()
</script>

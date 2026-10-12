<template>
  <div class="flex flex-col items-center gap-3">
    <div class="flex w-full items-center justify-between">
      <Button
        size="sm"
        variant="ghost"
        icon="lucide-chevron-left"
        :disabled="index <= 0"
        :label="__('Previous screen')"
        @click="emit('select', screens[index - 1].key)"
      />
      <p class="text-sm text-ink-gray-6">{{ __('Screen {0} of {1}').format(index + 1, screens.length) }}</p>
      <Button
        size="sm"
        variant="ghost"
        icon="lucide-chevron-right"
        :disabled="index >= screens.length - 1"
        :label="__('Next screen')"
        @click="emit('select', screens[index + 1].key)"
      />
    </div>

    <div class="w-full max-w-[300px] rounded-8 border border-outline-gray-3 bg-surface-gray-3 p-2 shadow-sm">
      <div class="flex h-[540px] flex-col overflow-hidden rounded-8 bg-surface-base">
        <div class="flex items-center gap-3 border-b border-outline-gray-1 px-3 py-3">
          <span class="lucide-x size-4 text-ink-gray-6" aria-hidden="true" />
          <TruncatedText
            as="p"
            class="min-w-0 flex-1 truncate text-center text-base font-medium text-ink-gray-9"
            :text="screen.screen_title || __('Untitled screen')"
          />
          <span class="lucide-ellipsis-vertical size-4 text-ink-gray-6" aria-hidden="true" />
        </div>

        <ScrollArea class="min-h-0 flex-1" viewport-class="px-4 py-4">
          <div class="flex flex-col gap-4">
            <template v-for="field in visible" :key="field.key">
              <p v-if="field.field_type === 'TextHeading'" class="whitespace-pre-wrap break-words text-xl font-semibold text-ink-gray-9">
                {{ field.label || __('Heading') }}
              </p>
              <p
                v-else-if="field.field_type === 'TextSubheading'"
                class="whitespace-pre-wrap break-words text-lg font-medium text-ink-gray-9"
              >
                {{ field.label || __('Subheading') }}
              </p>
              <p v-else-if="field.field_type === 'TextBody'" class="whitespace-pre-wrap break-words text-base text-ink-gray-8">
                {{ field.label || __('Body text') }}
              </p>
              <p v-else-if="field.field_type === 'TextCaption'" class="whitespace-pre-wrap break-words text-sm text-ink-gray-5">
                {{ field.label || __('Caption') }}
              </p>

              <template v-else-if="field.field_type === 'Image'">
                <img v-if="field.init_value" :src="imageSrc(field.init_value)" :alt="field.label" class="w-full rounded-4 object-cover" />
                <div v-else class="flex h-28 items-center justify-center rounded-4 bg-surface-gray-2">
                  <span class="lucide-image size-6 text-ink-gray-4" aria-hidden="true" />
                </div>
              </template>

              <button
                v-else-if="field.field_type === 'EmbeddedLink'"
                type="button"
                class="text-left text-base font-medium text-ink-green-6"
                @click="follow(field)"
              >
                {{ field.label || __('Link') }}
              </button>

              <div v-else-if="field.field_type === 'TextInput' || field.field_type === 'TextArea'" class="flex flex-col gap-1">
                <div
                  class="relative rounded-4 border border-outline-gray-3 px-3 pb-2 pt-4"
                  :class="field.field_type === 'TextArea' ? 'min-h-[88px]' : ''"
                >
                  <span class="absolute left-2.5 top-1 text-xs text-ink-gray-5">{{ labelOf(field) }}</span>
                  <FormControl
                    type="text"
                    v-if="field.field_type === 'TextInput'"
                    v-model="values[field.key]"
                    variant="ghost"
                    class="w-full [&_input]:!px-0 [&_input]:!text-base"
                    :maxlength="field.max_chars || undefined"
                  />
                  <Textarea
                    v-else
                    v-model="values[field.key]"
                    :rows="3"
                    variant="ghost"
                    class="w-full resize-none !px-0 !text-base"
                    :maxlength="field.max_chars || undefined"
                  />
                </div>
                <div class="flex justify-between gap-2 px-1 text-xs text-ink-gray-5">
                  <span>{{ field.helper_text }}</span>
                  <span v-if="field.max_chars">{{ String(values[field.key] || '').length }}/{{ field.max_chars }}</span>
                </div>
              </div>

              <div v-else-if="field.field_type === 'DatePicker'" class="flex flex-col gap-1">
                <div class="flex items-center justify-between rounded-4 border border-outline-gray-3 px-3 py-2.5">
                  <span class="text-base" :class="field.init_value ? 'text-ink-gray-9' : 'text-ink-gray-5'">
                    {{ field.init_value || labelOf(field) }}
                  </span>
                  <span class="lucide-calendar size-4 text-ink-gray-5" aria-hidden="true" />
                </div>
                <span v-if="field.helper_text" class="px-1 text-xs text-ink-gray-5">{{ field.helper_text }}</span>
              </div>

              <div v-else-if="field.field_type === 'Dropdown'" class="flex flex-col gap-1">
                <div class="relative rounded-4 border border-outline-gray-3 px-3 pb-2 pt-4">
                  <span class="absolute left-2.5 top-1 text-xs text-ink-gray-5">{{ labelOf(field) }}</span>
                  <div class="flex items-center justify-between">
                    <TruncatedText class="truncate text-base text-ink-gray-9" :text="optionTitle(field, field.init_value) || ' '" />
                    <span class="lucide-chevron-down size-4 text-ink-gray-5" aria-hidden="true" />
                  </div>
                </div>
                <span v-if="field.helper_text" class="px-1 text-xs text-ink-gray-5">{{ field.helper_text }}</span>
              </div>

              <fieldset
                v-else-if="field.field_type === 'RadioButtonsGroup' || field.field_type === 'CheckboxGroup'"
                class="flex flex-col gap-1"
              >
                <legend class="mb-1 text-base font-medium text-ink-gray-9">{{ labelOf(field) }}</legend>
                <span v-if="field.helper_text" class="-mt-1 mb-1 text-xs text-ink-gray-5">{{ field.helper_text }}</span>
                <RadioGroup v-if="field.field_type === 'RadioButtonsGroup' && field.options.length" v-model="values[field.key]" padded>
                  <Radio v-for="option in field.options" :key="option.id" :value="option.id" :label="option.title || option.id" />
                </RadioGroup>
                <template v-else>
                  <Checkbox
                    v-for="option in field.options"
                    :key="option.id"
                    padded
                    :label="option.title || option.id"
                    :model-value="(values[field.key] || []).includes(option.id)"
                    @update:model-value="toggle(field, option.id)"
                  />
                </template>
                <p v-if="!field.options.length" class="text-sm text-ink-gray-4">{{ __('No options yet') }}</p>
              </fieldset>

              <Checkbox
                v-else-if="field.field_type === 'OptIn'"
                v-model="values[field.key]"
                :label="field.required ? field.label || __('I agree') : __('{0} (optional)').format(field.label || __('I agree'))"
              />
            </template>

            <p v-if="!visible.length" class="py-10 text-center text-sm text-ink-gray-4">{{ __('Fields you add appear here.') }}</p>
          </div>
        </ScrollArea>

        <div class="flex flex-col gap-2 border-t border-outline-gray-1 px-4 pb-3 pt-3">
          <button
            type="button"
            class="w-full rounded-full py-2.5 text-base font-medium"
            :class="ready ? 'bg-surface-green-3 text-ink-gray-9' : 'bg-surface-gray-2 text-ink-gray-4'"
            @click="next"
          >
            {{ footerLabel }}
          </button>
          <p class="text-center text-xs text-ink-gray-5">
            {{ __('Managed by the business.') }} <span class="text-ink-green-6">{{ __('Learn more') }}</span>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, watch } from 'vue'
import { Button, Checkbox, FormControl, Radio, RadioGroup, ScrollArea, Textarea } from 'frappe-ui'
import { isInput } from './formSchema'
import { translate as __ } from '@/translation'

const props = defineProps({
  screen: { type: Object, required: true },
  screens: { type: Array, required: true },
})

const emit = defineEmits(['select'])

const values = reactive({})

const index = computed(() => props.screens.findIndex((screen) => screen.key === props.screen.key))
const visible = computed(() => props.screen.fields.filter((field) => field.enabled && field.field_type !== 'Footer'))
const footer = computed(() => props.screen.fields.find((field) => field.enabled && field.field_type === 'Footer'))
const footerLabel = computed(
  () => footer.value?.label || (footer.value ? __('Submit') : props.screen.terminal ? __('Complete') : __('Continue')),
)

const ready = computed(() =>
  visible.value
    .filter((field) => isInput(field.field_type) && field.required)
    .every((field) => {
      const value = values[field.key]
      return Array.isArray(value) ? value.length : !!value || !!field.init_value
    }),
)

watch(
  () => props.screen.fields.map((field) => `${field.key}:${field.init_value}`).join('|'),
  () => {
    for (const field of props.screen.fields) {
      if (values[field.key] !== undefined) continue
      if (field.field_type === 'CheckboxGroup') values[field.key] = []
      else if (['TextInput', 'TextArea', 'RadioButtonsGroup'].includes(field.field_type)) values[field.key] = field.init_value || ''
    }
  },
  { immediate: true },
)

function labelOf(field) {
  return (field.label || field.field_name || '') + (field.required ? '' : ` ${__('(optional)')}`)
}

function optionTitle(field, id) {
  const option = field.options.find((item) => item.id === id)

  return option ? option.title || option.id : ''
}

function imageSrc(value) {
  return value.startsWith('data:') ? value : `data:image/png;base64,${value}`
}

function toggle(field, id) {
  const current = values[field.key] || []
  values[field.key] = current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
}

function follow(field) {
  const target = props.screens.find((screen) => screen.screen_id === field.init_value)
  if (target) emit('select', target.key)
}

function next() {
  if (props.screen.terminal) return
  const target = props.screens[index.value + 1]
  if (target) emit('select', target.key)
}
</script>

<template>
  <div
    class="rounded-5 border bg-surface-base transition-shadow"
    :class="[
      errors.length ? 'border-outline-red-3' : expanded ? 'border-outline-gray-3' : 'border-outline-gray-2',
      expanded ? 'shadow-sm' : '',
      field.enabled ? '' : 'opacity-60',
    ]"
  >
    <div class="flex cursor-pointer items-center gap-2 py-2 pl-1.5 pr-2" @click="emit('select')">
      <span
        class="lucide-grip-vertical size-4 shrink-0 cursor-grab text-ink-gray-4"
        draggable="true"
        :aria-label="__('Drag to reorder')"
        @dragstart="(event) => emit('dragstart', event)"
        @click.stop
      />
      <span class="flex size-7 shrink-0 items-center justify-center rounded-4 bg-surface-gray-2">
        <span :class="def.icon" class="size-3.5 text-ink-gray-6" aria-hidden="true" />
      </span>
      <div class="min-w-0 flex-1">
        <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="title" />
        <p class="truncate text-xs text-ink-gray-5">
          {{ __(def.label) }}<template v-if="def.input && field.field_name"> · {{ field.field_name }}</template>
        </p>
      </div>
      <Badge v-if="def.input && field.required" size="sm" theme="blue" :label="__('Required')" />
      <Badge v-if="!field.enabled" size="sm" theme="gray" :label="__('Hidden')" />
      <span v-if="errors.length" class="lucide-circle-alert size-4 shrink-0 text-ink-red-3" :aria-label="__('Has problems')" />
      <Dropdown :options="menu" align="end">
        <Button size="sm" variant="ghost" icon="lucide-ellipsis" :label="__('Field actions')" @click.stop />
      </Dropdown>
      <span :class="expanded ? 'lucide-chevron-up' : 'lucide-chevron-down'" class="size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
    </div>

    <div v-if="expanded" class="flex flex-col gap-4 border-t border-outline-gray-1 p-3">
      <ul v-if="issues.length" class="flex flex-col gap-1">
        <li
          v-for="(issue, index) in issues"
          :key="index"
          class="flex items-start gap-2 text-sm"
          :class="issue.level === 'error' ? 'text-ink-red-3' : 'text-ink-amber-6'"
        >
          <span
            :class="issue.level === 'error' ? 'lucide-circle-x' : 'lucide-triangle-alert'"
            class="mt-0.5 size-3.5 shrink-0"
            aria-hidden="true"
          />
          {{ issue.message }}
        </li>
      </ul>

      <template v-if="def.input">
        <div class="grid grid-cols-2 gap-3">
          <FormControl
            type="text"
            :label="field.field_type === 'OptIn' ? __('Agreement text') : __('Label')"
            :required="true"
            :model-value="field.label"
            @update:model-value="setLabel"
          />
          <FormControl
            type="text"
            :label="__('Field name')"
            :description="__('Key used in the saved answer')"
            :model-value="field.field_name"
            @update:model-value="(value) => change({ field_name: value, autoName: false })"
          />
        </div>

        <Checkbox :label="__('Required')" :model-value="field.required" @update:model-value="(value) => change({ required: !!value })" />

        <FormControl
          v-if="field.field_type !== 'OptIn'"
          type="text"
          :label="__('Helper text')"
          :placeholder="__('Shown under the field')"
          :model-value="field.helper_text"
          @update:model-value="(value) => change({ helper_text: value })"
        />

        <OptionsEditor v-if="def.choice" :options="field.options" @change="(options) => change({ options })" />

        <div v-if="def.text" class="grid grid-cols-2 gap-3">
          <FormControl
            type="number"
            :label="__('Minimum characters')"
            :model-value="field.min_chars ?? ''"
            @update:model-value="(value) => change({ min_chars: toInt(value) })"
          />
          <FormControl
            type="number"
            :label="__('Maximum characters')"
            :model-value="field.max_chars ?? ''"
            @update:model-value="(value) => change({ max_chars: toInt(value) })"
          />
        </div>

        <FormControl
          v-if="def.text"
          type="text"
          :label="__('Error message')"
          :placeholder="__('Shown when the answer is not valid')"
          :model-value="field.error_message"
          @update:model-value="(value) => change({ error_message: value })"
        />

        <FormControl
          v-if="field.field_type === 'DatePicker'"
          type="date"
          :label="__('Initial value')"
          :model-value="field.init_value"
          @update:model-value="(value) => change({ init_value: value || '' })"
        />
        <FormControl
          v-else-if="['RadioButtonsGroup', 'Dropdown'].includes(field.field_type)"
          type="select"
          :label="__('Selected by default')"
          :options="[
            { label: __('None'), value: '' },
            ...field.options.map((option) => ({ label: option.title || option.id, value: option.id })),
          ]"
          :model-value="field.init_value"
          @update:model-value="(value) => change({ init_value: value || '' })"
        />
        <FormControl
          v-else-if="def.text"
          type="text"
          :label="__('Initial value')"
          :model-value="field.init_value"
          @update:model-value="(value) => change({ init_value: value })"
        />
      </template>

      <FormControl
        v-else-if="['TextHeading', 'TextSubheading', 'TextBody', 'TextCaption'].includes(field.field_type)"
        type="textarea"
        :rows="field.field_type === 'TextBody' ? 4 : 2"
        :label="__('Text')"
        :required="true"
        :model-value="field.label"
        @update:model-value="(value) => change({ label: value })"
      />

      <template v-else-if="field.field_type === 'Image'">
        <div class="flex items-center gap-3">
          <img
            v-if="field.init_value"
            :src="imageSrc"
            class="size-16 shrink-0 rounded-4 border border-outline-gray-1 object-cover"
            alt=""
          />
          <div class="flex flex-col gap-1">
            <Button size="sm" variant="subtle" icon-left="lucide-upload" :label="__('Choose image')" @click="picker?.click()" />
            <p class="text-xs text-ink-gray-5">{{ __('PNG or JPG, ideally under 300 KB. Stored inside the form.') }}</p>
          </div>
          <input ref="picker" type="file" accept="image/png,image/jpeg" class="hidden" @change="pickImage" />
        </div>
        <FormControl
          type="text"
          :label="__('Alt text')"
          :model-value="field.label"
          @update:model-value="(value) => change({ label: value })"
        />
      </template>

      <template v-else-if="field.field_type === 'EmbeddedLink'">
        <FormControl
          type="text"
          :label="__('Link text')"
          :model-value="field.label"
          @update:model-value="(value) => change({ label: value })"
        />
        <FormControl
          type="select"
          :label="__('Opens screen')"
          :required="true"
          :options="[
            { label: __('Pick a screen'), value: '' },
            ...screens.map((screen) => ({ label: screen.screen_title || screen.screen_id, value: screen.screen_id })),
          ]"
          :model-value="field.init_value"
          @update:model-value="(value) => change({ init_value: value || '' })"
        />
      </template>

      <FormControl
        v-else-if="field.field_type === 'Footer'"
        type="text"
        :label="__('Button label')"
        :description="__('Replaces the default Continue or Complete button on this screen.')"
        :model-value="field.label"
        @update:model-value="(value) => change({ label: value })"
      />
    </div>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref } from 'vue'
import { Badge, Button, Checkbox, Dropdown, FormControl, toast } from 'frappe-ui'
import OptionsEditor from './OptionsEditor.vue'
import { fieldDef, slug } from './formSchema'
import { translate as __ } from '@/translation'

const props = defineProps({
  field: { type: Object, required: true },
  screens: { type: Array, default: () => [] },
  screenKey: { type: String, default: null },
  expanded: { type: Boolean, default: false },
  issues: { type: Array, default: () => [] },
})

const emit = defineEmits(['change', 'select', 'duplicate', 'remove', 'move', 'dragstart'])

const picker = ref(null)

const def = computed(() => fieldDef(props.field.field_type))
const errors = computed(() => props.issues.filter((issue) => issue.level === 'error'))
const title = computed(() => props.field.label || (def.value.input ? props.field.field_name : '') || __(def.value.label))
const imageSrc = computed(() =>
  props.field.init_value.startsWith('data:') ? props.field.init_value : `data:image/png;base64,${props.field.init_value}`,
)

const menu = computed(() => [
  { label: __('Duplicate'), icon: 'lucide-copy', onClick: () => emit('duplicate') },
  {
    label: props.field.enabled ? __('Hide from form') : __('Show in form'),
    icon: props.field.enabled ? 'lucide-eye-off' : 'lucide-eye',
    onClick: () => change({ enabled: !props.field.enabled }),
  },
  {
    label: __('Move to screen'),
    icon: 'lucide-arrow-right-left',
    condition: () => props.screens.length > 1,
    submenu: props.screens
      .filter((screen) => screen.key !== props.screenKey)
      .map((screen) => ({ label: screen.screen_title || screen.screen_id, onClick: () => emit('move', screen.key) })),
  },
  { label: __('Delete'), icon: 'lucide-trash-2', theme: 'red', onClick: () => emit('remove') },
])

function change(patch) {
  emit('change', patch)
}

function setLabel(label) {
  const patch = { label }
  if (props.field.autoName || !props.field.field_name) {
    const name = slug(label)
    if (name) {
      patch.field_name = name
      patch.autoName = true
    }
  }
  change(patch)
}

function toInt(value) {
  const number = parseInt(value, 10)

  return Number.isNaN(number) || number <= 0 ? null : number
}

function pickImage(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (file.size > 1024 * 1024) {
    toast.error(__('Pick an image under 1 MB'))
    return
  }

  const reader = new FileReader()
  reader.onload = () => change({ init_value: String(reader.result).replace(/^data:[^,]+,/, '') })
  reader.readAsDataURL(file)
}
</script>

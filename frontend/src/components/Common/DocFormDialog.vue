<template>
  <ResponsiveDialog v-model:open="open" :title="heading" :size="size">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-3 py-2">
        <Skeleton v-for="row in 4" :key="row" class="h-9 w-full" />
      </div>

      <div v-else class="grid grid-cols-2 gap-x-4 gap-y-4">
        <template v-for="field in visibleFields" :key="field.fieldname || field.section">
          <p
            v-if="field.section"
            class="col-span-2 mt-2 border-t border-outline-gray-1 pt-4 text-sm font-medium text-ink-gray-5 first:mt-0 first:border-0 first:pt-0"
          >
            {{ __(field.section) }}
          </p>
          <div v-else :class="field.half ? 'col-span-2 sm:col-span-1' : 'col-span-2'">
            <slot :name="`field-${field.fieldname}`" :doc="doc" :field="field">
              <FieldControl v-model="doc[field.fieldname]" :field="field" />
            </slot>
          </div>
        </template>
      </div>

      <ErrorMessage :message="error" class="mt-4" />
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <div>
          <Button v-if="name && deletable" variant="ghost" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="remove" />
        </div>
        <div class="flex items-center gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
          <Button variant="solid" :loading="saving" :label="name ? __('Save') : __('Create')" @click="save" />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, ErrorMessage, Skeleton, call, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import FieldControl from './FieldControl.vue'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, default: null },
  title: { type: String, default: '' },
  fields: { type: Array, required: true },
  defaults: { type: Object, default: () => ({}) },
  size: { type: String, default: 'xl' },
  deletable: { type: Boolean, default: true },
})

const emit = defineEmits(['saved', 'deleted'])

const open = defineModel('open', { type: Boolean, default: false })

const ui = useUI()
const doc = ref({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const heading = computed(
  () => props.title || (props.name ? __('Edit {0}').format(__(props.doctype)) : __('New {0}').format(__(props.doctype))),
)

const visibleFields = computed(() => props.fields.filter((field) => !field.depends || field.depends(doc.value)))

watch(
  open,
  async (value) => {
    if (!value) return

    error.value = ''
    if (!props.name) {
      doc.value = { ...props.defaults }
      return
    }

    loading.value = true
    try {
      doc.value = await call('frappe.client.get', { doctype: props.doctype, name: props.name })
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

function values() {
  const out = {}

  for (const field of props.fields) {
    if (!field.fieldname || field.readOnly) continue
    if (field.depends && !field.depends(doc.value)) continue

    out[field.fieldname] = doc.value[field.fieldname] ?? null
  }

  return out
}

function missing() {
  return visibleFields.value.filter((field) => field.required && [undefined, null, ''].includes(doc.value[field.fieldname]))
}

async function save() {
  const empty = missing()
  if (empty.length) {
    error.value = __('Fill in {0}').format(empty.map((field) => __(field.label)).join(', '))
    return
  }

  saving.value = true
  error.value = ''

  try {
    const saved = props.name
      ? await call('frappe.client.set_value', { doctype: props.doctype, name: props.name, fieldname: values() })
      : await call('frappe.client.insert', { doc: { doctype: props.doctype, ...values() } })

    toast.success(props.name ? __('Saved') : __('Created'))
    emit('saved', saved)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function remove() {
  ui.confirm({
    title: __('Delete this {0}?').format(__(props.doctype).toLowerCase()),
    message: __('This cannot be undone.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: props.doctype, name: props.name })
      toast.success(__('Deleted'))
      emit('deleted', props.name)
      open.value = false
    },
  })
}
</script>

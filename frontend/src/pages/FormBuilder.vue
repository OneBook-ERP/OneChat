<template>
  <template v-if="compact">
    <AppHeader :title="form.flow_name || __('Form builder')" :back="{ name: 'Forms' }" />
    <div class="flex flex-col gap-4 px-3 pb-10 pt-5">
      <div v-if="loading" class="flex flex-col gap-2">
        <Skeleton v-for="row in 4" :key="row" class="h-10 w-full" />
      </div>
      <ErrorMessage v-else-if="loadError" :message="loadError" />
      <FormSummary v-else-if="form.name" :form="form" :screens="screens" />
      <EmptyState
        icon="lucide-monitor-smartphone"
        :title="__('Open on a larger screen to edit')"
        :description="
          __('The form builder needs room for screens, fields and the preview. Open OneChat on a laptop or desktop to edit this form.')
        "
      />
    </div>
  </template>

  <div v-else class="flex min-h-0 flex-1 flex-col bg-surface-base">
    <header class="flex h-12 shrink-0 items-center gap-2 border-b border-outline-gray-2 px-3">
      <Tooltip :text="__('Back to forms')">
        <Button variant="ghost" icon="lucide-arrow-left" :label="__('Back to forms')" @click="router.push({ name: 'Forms' })" />
      </Tooltip>
      <FormControl type="text" v-model="form.flow_name" variant="ghost" class="w-60 text-base font-medium" :placeholder="__('Form name')" />
      <FormStatusBadge v-if="form.name" :status="form.status" />
      <Badge v-if="dirty" :label="__('Unsaved')" theme="amber" />

      <div class="flex-1" />

      <TabButtons v-model="view" :options="views" />
      <div class="mx-1 h-5 w-px bg-surface-gray-4" />

      <Tooltip :text="form.flow_id ? __('Send this form to a phone') : __('Create the form on WhatsApp first')">
        <Button variant="subtle" icon-left="lucide-send" :disabled="!form.flow_id" :label="__('Send test')" @click="openTest" />
      </Tooltip>
      <Tooltip :text="form.flow_id ? __('Meta’s preview of the uploaded version') : __('Create the form on WhatsApp first')">
        <Button
          variant="subtle"
          icon-left="lucide-smartphone"
          :disabled="!form.flow_id"
          :label="__('Preview')"
          @click="metaPreview = true"
        />
      </Tooltip>
      <Button
        v-if="lifecycle"
        variant="subtle"
        :theme="lifecycle.theme || 'gray'"
        :icon-left="lifecycle.icon"
        :loading="busy === lifecycle.key"
        :disabled="!!busy"
        :label="lifecycle.label"
        @click="lifecycle.run"
      />
      <Button variant="solid" icon-left="lucide-save" :loading="saving" :label="__('Save')" @click="save" />
      <Dropdown :options="moreMenu" align="end">
        <Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" />
      </Dropdown>
    </header>

    <div v-if="loading" class="flex flex-1 items-center justify-center">
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>

    <div v-else-if="loadError" class="flex flex-1 items-center justify-center p-6">
      <EmptyState icon="lucide-circle-alert" :title="__('This form could not be opened')" :description="loadError">
        <Button variant="subtle" :label="__('Back to forms')" @click="router.push({ name: 'Forms' })" />
      </EmptyState>
    </div>

    <FormResponses v-else-if="view === 'responses'" :name="form.name" :screens="screens" />

    <template v-else>
      <div
        v-if="form.status && form.status !== 'Draft'"
        class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 bg-surface-gray-1 px-4 py-2 text-sm text-ink-gray-7"
      >
        <span class="lucide-info size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
        {{ statusNote }}
      </div>

      <div class="flex min-h-0 flex-1">
        <ScreenList
          :screens="screens"
          :selected="selectedScreen?.key || null"
          :issues="issues"
          @select="selectScreen"
          @add="addScreen"
          @move="moveScreen"
          @terminal="setTerminal"
          @duplicate="duplicateScreen"
          @remove="removeScreen"
        />

        <ScreenEditor
          v-if="selectedScreen"
          :screen="selectedScreen"
          :screens="screens"
          :selected-field="selectedField"
          :issues="issues"
          @change="(patch) => changeScreen(selectedScreen.key, patch)"
          @terminal="setTerminal(selectedScreen.key)"
          @add-field="addField"
          @select-field="(key) => (selectedField = key)"
          @change-field="changeField"
          @duplicate-field="duplicateField"
          @remove-field="removeField"
          @move-field="moveField"
          @move-field-to="moveFieldTo"
        />
        <div v-else class="flex min-w-0 flex-1 items-center justify-center bg-surface-gray-1 p-6">
          <EmptyState icon="lucide-layers" :title="__('No screen selected')" :description="__('Pick a screen on the left.')" />
        </div>

        <aside class="flex w-[340px] shrink-0 flex-col border-l border-outline-gray-2 bg-surface-base">
          <div class="border-b border-outline-gray-1 p-2">
            <TabButtons v-model="panel" :options="panels" class="w-full" />
          </div>
          <ScrollArea class="min-h-0 flex-1" viewport-class="p-4">
            <PhonePreview v-if="panel === 'preview' && selectedScreen" :screen="selectedScreen" :screens="screens" @select="selectScreen" />
            <FormSettings v-else-if="panel === 'settings'" :form="form" @change="(patch) => Object.assign(form, patch)" />
            <FormChecks v-else-if="panel === 'checks'" :issues="issues" :meta-errors="metaErrors" @select="showIssue" />
          </ScrollArea>
        </aside>
      </div>
    </template>

    <SendTestDialog v-model:open="testOpen" :name="form.name" :form-name="form.flow_name" :status="form.status" />
    <MetaPreviewDialog v-model:open="metaPreview" :name="form.name" @loaded="refresh" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import {
  Badge,
  Button,
  Dropdown,
  ErrorMessage,
  FormControl,
  LoadingIndicator,
  ScrollArea,
  Skeleton,
  TabButtons,
  Tooltip,
  call,
  toast,
} from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import FormChecks from '@/components/Forms/FormChecks.vue'
import FormResponses from '@/components/Forms/FormResponses.vue'
import FormSettings from '@/components/Forms/FormSettings.vue'
import FormStatusBadge from '@/components/Forms/FormStatusBadge.vue'
import FormSummary from '@/components/Forms/FormSummary.vue'
import MetaPreviewDialog from '@/components/Forms/MetaPreviewDialog.vue'
import PhonePreview from '@/components/Forms/PhonePreview.vue'
import ScreenEditor from '@/components/Forms/ScreenEditor.vue'
import ScreenList from '@/components/Forms/ScreenList.vue'
import SendTestDialog from '@/components/Forms/SendTestDialog.vue'
import {
  blankForm,
  blankScreens,
  checkForm,
  docMethod,
  newField,
  newScreen,
  readDoc,
  uid,
  uniqueScreenId,
  writeDoc,
} from '@/components/Forms/formSchema'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  compact: { type: Boolean, default: false },
})

const DOCTYPE = 'WhatsApp Flow'

const route = useRoute()
const router = useRouter()
const ui = useUI()

const form = ref(blankForm())
const screens = ref([])
const orphans = ref([])
const selectedKey = ref(null)
const selectedField = ref(null)
const dirty = ref(false)
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const busy = ref('')
const view = ref('build')
const panel = ref('preview')
const metaErrors = ref([])
const testOpen = ref(false)
const metaPreview = ref(false)
let hydrating = false
let wasFullScreen = false

const views = [
  { label: __('Build'), value: 'build', iconLeft: 'lucide-pencil-ruler' },
  { label: __('Responses'), value: 'responses', iconLeft: 'lucide-inbox' },
]

const issues = computed(() => checkForm(form.value, screens.value))
const errorCount = computed(() => issues.value.filter((issue) => issue.level === 'error').length)

const panels = computed(() => [
  { label: __('Preview'), value: 'preview' },
  { label: __('Settings'), value: 'settings' },
  { label: errorCount.value ? __('Checks ({0})').format(errorCount.value) : __('Checks'), value: 'checks' },
])

const selectedScreen = computed(() => screens.value.find((screen) => screen.key === selectedKey.value) || null)

const statusNote = computed(() => {
  if (form.value.status === 'Published') {
    return __('This form is live. Meta does not allow changes to a published form, so edits saved here are not sent to WhatsApp.')
  }
  if (form.value.status === 'Deprecated') return __('This form is deprecated and can no longer be sent.')
  if (form.value.status === 'Blocked') return __('Meta has blocked this form. Check its status for details.')
  if (form.value.status === 'Throttled') return __('Meta is limiting how often this form can be sent.')

  return ''
})

watch(
  [form, screens],
  () => {
    if (!hydrating) dirty.value = true
  },
  { deep: true },
)

async function hydrate(task) {
  hydrating = true
  try {
    await task()
  } finally {
    await nextTick()
    hydrating = false
  }
}

async function defaultAccount() {
  try {
    const rows = await call('frappe.client.get_list', {
      doctype: 'OneChat Account',
      fields: ['name'],
      filters: { is_default_outgoing: 1 },
      limit_page_length: 1,
    })
    return rows?.[0]?.name || ''
  } catch {
    return ''
  }
}

async function load(name) {
  loadError.value = ''
  metaErrors.value = []
  selectedField.value = null

  await hydrate(async () => {
    try {
      if (name === 'new') {
        form.value = blankForm()
        screens.value = blankScreens()
        orphans.value = []
        form.value.whatsapp_account = await defaultAccount()
      } else {
        loading.value = true
        const parsed = readDoc(await call('frappe.client.get', { doctype: DOCTYPE, name }))
        form.value = parsed.form
        screens.value = parsed.screens
        orphans.value = parsed.orphans
      }
      selectedKey.value = screens.value[0]?.key || null
    } catch (err) {
      loadError.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  })
  dirty.value = false
}

watch(
  () => route.params.name,
  (name) => {
    if (!name || route.name !== 'FormBuilder' || (name !== 'new' && name === form.value.name)) return
    load(String(name))
  },
  { immediate: true },
)

function applyServer(doc) {
  const sent = [...screens.value.flatMap((screen) => screen.fields), ...orphans.value]
  const fieldRows = [...(doc.fields || [])].sort((a, b) => a.idx - b.idx)
  const screenRows = [...(doc.screens || [])].sort((a, b) => a.idx - b.idx)

  for (const key of ['name', 'modified', 'status', 'flow_id', 'preview_url']) form.value[key] = doc[key] ?? form.value[key]
  screens.value.forEach((screen, index) => {
    if (screenRows[index]) screen.name = screenRows[index].name
  })
  sent.forEach((field, index) => {
    if (fieldRows[index]) field.name = fieldRows[index].name
  })
}

async function refresh() {
  if (!form.value.name) return

  try {
    const doc = await call('frappe.client.get', { doctype: DOCTYPE, name: form.value.name })
    await hydrate(async () => applyServer(doc))
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

async function save() {
  const title = String(form.value.flow_name || '').trim()
  if (!title) {
    toast.error(__('Give the form a name first'))
    return false
  }
  if (!form.value.whatsapp_account) {
    panel.value = 'settings'
    toast.error(__('Pick a WhatsApp account first'))
    return false
  }

  saving.value = true
  try {
    const doc = writeDoc(form.value, screens.value, orphans.value)
    let saved = form.value.name ? await call('frappe.client.save', { doc }) : await call('frappe.client.insert', { doc })

    if (saved.name !== title && form.value.name) {
      const renamed = await call('frappe.client.rename_doc', { doctype: DOCTYPE, old_name: saved.name, new_name: title })
      saved = await call('frappe.client.get', { doctype: DOCTYPE, name: renamed || title })
    }

    await hydrate(async () => applyServer(saved))
    dirty.value = false
    toast.success(__('Form saved'))

    if (route.params.name !== saved.name) {
      await router.replace({ name: 'FormBuilder', params: { name: saved.name } })
    }

    return true
  } catch (err) {
    toast.error(errorMessage(err))
    return false
  } finally {
    saving.value = false
  }
}

async function ready({ strict = true } = {}) {
  if (strict && errorCount.value) {
    panel.value = 'checks'
    view.value = 'build'
    toast.error(__('Fix the problems in Checks first'))
    return false
  }
  if (!form.value.name || dirty.value) return save()

  return true
}

async function runMethod(key, method, args) {
  busy.value = key
  try {
    const result = await call('run_doc_method', docMethod(form.value.name, method, args))
    await refresh()
    return { ok: true, result }
  } catch (err) {
    toast.error(errorMessage(err))
    await refresh()
    return { ok: false }
  } finally {
    busy.value = ''
  }
}

async function createOnWhatsApp() {
  if (!(await ready())) return

  const { ok } = await runMethod('create', 'create_on_whatsapp')
  if (ok) toast.success(__('Created on WhatsApp as a draft'))
}

async function uploadChanges() {
  if (!(await ready())) return

  const { ok } = await runMethod('upload', 'upload_flow_json')
  if (ok) toast.success(__('Changes uploaded to WhatsApp'))
}

async function publish() {
  if (!(await ready())) return

  ui.confirm({
    title: __('Publish {0}?').format(form.value.flow_name),
    message: __(
      'The latest version is uploaded and published. Meta does not allow changes to a published form; to change it later you will need a new form.',
    ),
    action: __('Upload & publish'),
    onConfirm: async () => {
      const upload = await runMethod('publish', 'upload_flow_json')
      if (!upload.ok) return
      const done = await runMethod('publish', 'publish_flow')
      if (done.ok) toast.success(__('Form published'))
    },
  })
}

function deprecate() {
  ui.confirm({
    title: __('Deprecate {0}?').format(form.value.flow_name),
    message: __('The form can no longer be sent. People who already opened it can still finish it. This cannot be undone.'),
    action: __('Deprecate'),
    theme: 'red',
    onConfirm: async () => {
      const { ok } = await runMethod('deprecate', 'deprecate_flow')
      if (ok) toast.success(__('Form deprecated'))
    },
  })
}

async function checkStatus() {
  if (dirty.value && !(await save())) return

  const { ok, result } = await runMethod('status', 'get_flow_status')
  if (!ok) return

  metaErrors.value = result?.validation_errors || []
  panel.value = 'checks'
  view.value = 'build'
  if (metaErrors.value.length) toast.error(__('Meta reported {0} problems').format(metaErrors.value.length))
  else toast.success(__('Status: {0}').format(form.value.status))
}

function deleteFromWhatsApp() {
  ui.confirm({
    title: __('Delete {0} from WhatsApp?').format(form.value.flow_name),
    message: __('The draft is removed from Meta. The form stays here so you can create it again.'),
    action: __('Delete from WhatsApp'),
    theme: 'red',
    onConfirm: async () => {
      if (dirty.value && !(await save())) return
      const { ok } = await runMethod('remove', 'delete_from_whatsapp')
      if (ok) toast.success(__('Deleted from WhatsApp'))
    },
  })
}

function deleteForm() {
  ui.confirm({
    title: __('Delete {0}?').format(form.value.flow_name),
    message: form.value.flow_id
      ? __('The form is removed from OneChat only; it stays in Meta’s WhatsApp Manager. This cannot be undone.')
      : __('The form and its screens are removed. This cannot be undone.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: DOCTYPE, name: form.value.name })
      dirty.value = false
      toast.success(__('Form deleted'))
      router.push({ name: 'Forms' })
    },
  })
}

async function openTest() {
  if (dirty.value && !(await save())) return
  testOpen.value = true
}

const lifecycle = computed(() => {
  const status = form.value.status || 'Draft'

  if (status === 'Draft' && !form.value.flow_id) {
    return { key: 'create', label: __('Create on WhatsApp'), icon: 'lucide-cloud-upload', run: createOnWhatsApp }
  }
  if (status === 'Draft') return { key: 'publish', label: __('Upload & publish'), icon: 'lucide-rocket', run: publish }
  if (status === 'Published') {
    return { key: 'deprecate', label: __('Deprecate'), icon: 'lucide-archive', theme: 'red', run: deprecate }
  }

  return null
})

const moreMenu = computed(() => [
  {
    label: __('Upload changes only'),
    icon: 'lucide-upload',
    condition: () => !!form.value.flow_id && form.value.status === 'Draft',
    onClick: uploadChanges,
  },
  {
    label: __('Check status with Meta'),
    icon: 'lucide-shield-check',
    condition: () => !!form.value.flow_id,
    onClick: checkStatus,
  },
  {
    label: __('Delete from WhatsApp'),
    icon: 'lucide-cloud-off',
    theme: 'red',
    condition: () => !!form.value.flow_id && form.value.status === 'Draft',
    onClick: deleteFromWhatsApp,
  },
  {
    label: __('Delete form'),
    icon: 'lucide-trash-2',
    theme: 'red',
    condition: () => !!form.value.name,
    onClick: deleteForm,
  },
])

function selectScreen(key) {
  selectedKey.value = key
  selectedField.value = null
  view.value = 'build'
}

function showIssue(issue) {
  if (issue.screenKey) selectedKey.value = issue.screenKey
  selectedField.value = issue.fieldKey || null
}

function changeScreen(key, patch) {
  const screen = screens.value.find((item) => item.key === key)
  if (!screen) return

  const previous = screen.screen_id
  Object.assign(screen, patch)

  if ('screen_id' in patch && previous && previous !== patch.screen_id) {
    for (const item of screens.value) {
      for (const field of item.fields) {
        if (field.field_type === 'EmbeddedLink' && field.init_value === previous) field.init_value = patch.screen_id
      }
    }
  }
}

function setTerminal(key) {
  for (const screen of screens.value) screen.terminal = screen.key === key
}

function addScreen() {
  const screen = newScreen(screens.value)
  const last = screens.value[screens.value.length - 1]
  const position = last?.terminal ? screens.value.length - 1 : screens.value.length

  screens.value.splice(position, 0, screen)
  selectScreen(screen.key)
}

function duplicateScreen(key) {
  const index = screens.value.findIndex((screen) => screen.key === key)
  if (index < 0) return

  const source = screens.value[index]
  const copy = {
    ...JSON.parse(JSON.stringify(source)),
    key: uid(),
    name: null,
    autoId: false,
    terminal: false,
    screen_title: __('{0} copy').format(source.screen_title),
    screen_id: uniqueScreenId(`${source.screen_id}_COPY`, screens.value),
  }
  copy.fields = copy.fields.map((field) => ({ ...field, key: uid(), name: null }))

  screens.value.splice(index + 1, 0, copy)
  selectScreen(copy.key)
}

function removeScreen(key) {
  const screen = screens.value.find((item) => item.key === key)
  if (!screen || screens.value.length < 2) return

  const drop = () => {
    const index = screens.value.indexOf(screen)
    screens.value.splice(index, 1)
    if (screen.terminal) screens.value[screens.value.length - 1].terminal = true
    if (selectedKey.value === key) selectScreen(screens.value[Math.max(0, index - 1)].key)
  }

  if (!screen.fields.length) {
    drop()
    return
  }

  ui.confirm({
    title: __('Delete {0}?').format(screen.screen_title || screen.screen_id),
    message: __('Its {0} fields are removed too.').format(screen.fields.length),
    action: __('Delete'),
    theme: 'red',
    onConfirm: drop,
  })
}

function moveScreen(from, to) {
  const list = screens.value
  list.splice(to, 0, list.splice(from, 1)[0])
}

function findField(key) {
  for (const screen of screens.value) {
    const index = screen.fields.findIndex((field) => field.key === key)
    if (index >= 0) return { screen, index, field: screen.fields[index] }
  }

  return null
}

function addField(type) {
  const screen = selectedScreen.value
  if (!screen) return

  const field = newField(type, screens.value)
  const footer = screen.fields.findIndex((item) => item.field_type === 'Footer')
  if (type === 'Footer' || footer < 0) screen.fields.push(field)
  else screen.fields.splice(footer, 0, field)

  selectedField.value = field.key
}

function changeField(key, patch) {
  const found = findField(key)
  if (found) Object.assign(found.field, patch)
}

function duplicateField(key) {
  const found = findField(key)
  if (!found) return

  const taken = screens.value.flatMap((screen) => screen.fields.map((field) => field.field_name))
  let fieldName = `${found.field.field_name}_copy`
  let number = 2
  while (taken.includes(fieldName)) fieldName = `${found.field.field_name}_copy_${number++}`

  const copy = { ...JSON.parse(JSON.stringify(found.field)), key: uid(), name: null, field_name: fieldName, autoName: false }
  found.screen.fields.splice(found.index + 1, 0, copy)
  selectedField.value = copy.key
}

function removeField(key) {
  const found = findField(key)
  if (!found) return

  found.screen.fields.splice(found.index, 1)
  if (selectedField.value === key) selectedField.value = null
}

function moveField(from, to) {
  const fields = selectedScreen.value?.fields
  if (!fields) return

  fields.splice(to, 0, fields.splice(from, 1)[0])
}

function moveFieldTo(key, screenKey) {
  const found = findField(key)
  const target = screens.value.find((screen) => screen.key === screenKey)
  if (!found || !target) return

  found.screen.fields.splice(found.index, 1)
  const footer = target.fields.findIndex((item) => item.field_type === 'Footer')
  if (footer < 0 || found.field.field_type === 'Footer') target.fields.push(found.field)
  else target.fields.splice(footer, 0, found.field)

  selectedKey.value = target.key
  selectedField.value = key
}

function guard(to) {
  if (!dirty.value) return true

  ui.confirm({
    title: __('Discard unsaved changes?'),
    message: __('Your changes to this form have not been saved.'),
    action: __('Discard'),
    theme: 'red',
    onConfirm: () => {
      dirty.value = false
      router.push(to.fullPath)
    },
  })

  return false
}

onBeforeRouteLeave(guard)
onBeforeRouteUpdate((to) => (to.params.name === form.value.name ? true : guard(to)))

function onBeforeUnload(event) {
  if (!dirty.value) return

  event.preventDefault()
  event.returnValue = ''
}

function onKeydown(event) {
  if (props.compact || !(event.ctrlKey || event.metaKey) || event.altKey) return
  if ((event.key || '').toLowerCase() !== 's') return

  event.preventDefault()
  if (!saving.value) save()
}

watch(
  () => props.compact,
  (compact) => (ui.fullScreen = !compact),
)

onMounted(() => {
  wasFullScreen = ui.fullScreen
  ui.fullScreen = !props.compact
  window.addEventListener('beforeunload', onBeforeUnload)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  ui.fullScreen = wasFullScreen
  window.removeEventListener('beforeunload', onBeforeUnload)
  document.removeEventListener('keydown', onKeydown)
})
</script>

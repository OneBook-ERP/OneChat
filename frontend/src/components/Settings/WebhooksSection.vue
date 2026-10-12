<template>
  <section class="flex flex-col gap-3">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-base font-semibold text-ink-gray-9">{{ __('Webhooks') }}</p>
        <p class="text-sm text-ink-gray-5">
          {{
            __(
              'Built on Frappe webhooks: OneChat sends a signed JSON POST to your URL when an event happens, with retries and a request log.',
            )
          }}
        </p>
      </div>
      <Button variant="subtle" icon-left="lucide-plus" :label="__('Add webhook')" @click="edit(null)" />
    </div>

    <div v-if="loading" class="flex flex-col gap-2">
      <Skeleton v-for="index in 2" :key="index" class="h-14 w-full rounded-4" />
    </div>

    <p v-else-if="!rows.length" class="rounded-4 bg-surface-gray-1 px-3 py-4 text-center text-sm text-ink-gray-5">
      {{ __('No webhooks yet.') }}
    </p>

    <div v-else class="divide-y divide-outline-gray-1 rounded-4 border border-outline-gray-2">
      <div v-for="row in rows" :key="row.name" class="flex items-center gap-3 px-3 py-2.5">
        <span class="size-2 shrink-0 rounded-full" :class="dot(row)" aria-hidden="true" />
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <code class="font-mono text-sm text-ink-gray-9">{{ row.event }}</code>
            <Badge v-if="!row.enabled" size="sm" theme="gray" :label="__('Off')" />
          </div>
          <TruncatedText as="p" class="truncate font-mono text-xs text-ink-gray-5" :text="row.url" />
          <p class="truncate text-xs" :class="row.last_error ? 'text-ink-red-7' : 'text-ink-gray-5'">
            <template v-if="!row.last_sent_at">{{ __('Nothing sent yet') }}</template>
            <template v-else-if="row.last_error">{{
              __('Last try {0} failed: {1}').format(timeAgo(row.last_sent_at), row.last_error)
            }}</template>
            <template v-else>{{ __('Last sent {0}').format(timeAgo(row.last_sent_at)) }}</template>
          </p>
        </div>
        <Switch :model-value="!!row.enabled" :aria-label="__('Enabled')" @update:model-value="(value) => toggle(row, value)" />
        <Dropdown :options="menu(row)" align="end">
          <Button variant="ghost" icon="lucide-ellipsis" :label="__('More actions')" />
        </Dropdown>
      </div>
    </div>

    <ResponsiveDialog v-model:open="form.open" :title="form.name ? __('Edit webhook') : __('Add webhook')" size="xl">
      <template #default>
        <div class="flex flex-col gap-4">
          <FormControl v-model="form.url" type="url" :label="__('URL')" placeholder="https://example.com/onechat" required />
          <div class="flex flex-col gap-2">
            <FormLabel :label="form.name ? __('Event') : __('Events')" required />
            <p v-if="!form.name" class="text-sm text-ink-gray-5">
              {{ __('Each event becomes its own Frappe webhook. They share one signing secret.') }}
            </p>
            <div v-for="group in grouped" :key="group.name" class="flex flex-col gap-2">
              <p class="mt-1 text-xs font-medium uppercase tracking-wide text-ink-gray-5">{{ group.name }}</p>
              <div v-for="item in group.items" :key="item.event" class="flex items-start gap-3">
                <Checkbox :model-value="form.events.includes(item.event)" @update:model-value="(value) => pick(item.event, value)" />
                <div class="min-w-0">
                  <p class="font-mono text-sm text-ink-gray-8">{{ item.event }}</p>
                  <p class="text-sm text-ink-gray-5">{{ item.description }}</p>
                </div>
              </div>
            </div>
          </div>
          <Password
            v-model="form.secret"
            :label="__('Signing secret')"
            :placeholder="form.name ? __('Leave empty to keep the current secret') : __('Leave empty to create one')"
            :description="
              __(
                'Frappe signs every request with it in the X-Frappe-Webhook-Signature header. Your server checks it to know the request came from OneChat.',
              )
            "
          />
          <Switch v-model="form.enabled" :label="__('Enabled')" />
          <ErrorMessage :message="form.error" />
        </div>
      </template>
      <template #actions>
        <div class="flex w-full justify-end gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="form.open = false" />
          <Button variant="solid" :loading="form.saving" :label="__('Save')" @click="save" />
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog v-model:open="secret.open" :title="__('Signing secret')" size="lg">
      <template #default>
        <div class="flex flex-col gap-3">
          <Alert
            theme="amber"
            :title="__('Copy it now')"
            :description="__('It is shown only once. Use it to check the X-Frappe-Webhook-Signature header.')"
          />
          <div class="flex items-center gap-2">
            <TruncatedText
              as="code"
              class="min-w-0 flex-1 truncate rounded-3 bg-surface-gray-2 px-2 py-1.5 font-mono text-sm text-ink-gray-8"
              :text="secret.value"
            />
            <Button variant="ghost" icon="lucide-copy" :label="__('Copy')" @click="copy(secret.value)" />
          </div>
        </div>
      </template>
      <template #actions>
        <div class="flex w-full justify-end">
          <Button variant="solid" :label="__('Done')" @click="secret.open = false" />
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog v-model:open="log.open" :title="__('Requests: {0}').format(log.title)" size="5xl">
      <template #default>
        <div v-if="log.loading" class="flex flex-col gap-2">
          <Skeleton v-for="index in 4" :key="index" class="h-10 w-full rounded-3" />
        </div>
        <p v-else-if="!log.rows.length" class="py-6 text-center text-sm text-ink-gray-5">{{ __('No requests logged yet.') }}</p>
        <div v-else class="flex flex-col gap-3">
          <div class="flex flex-wrap items-center gap-2 text-sm text-ink-gray-6">
            <Badge theme="green" variant="subtle" :label="__('{0} delivered').format(logStats.ok)" />
            <Badge v-if="logStats.failed" theme="red" variant="subtle" :label="__('{0} failed').format(logStats.failed)" />
            <span class="text-ink-gray-5">{{ __('Last {0} requests, newest first').format(log.rows.length) }}</span>
          </div>
          <ScrollArea class="-mx-1" viewport-class="max-h-[72vh] px-1">
            <div class="flex flex-col gap-2">
              <details
                v-for="row in log.rows"
                :key="row.name"
                class="group rounded-4 border border-outline-gray-2 open:border-outline-gray-3 open:bg-surface-gray-1"
              >
                <summary class="flex cursor-pointer list-none items-center gap-3 px-3 py-2.5 text-sm [&::-webkit-details-marker]:hidden">
                  <span
                    class="lucide-chevron-right size-4 shrink-0 text-ink-gray-5 transition-transform group-open:rotate-90"
                    aria-hidden="true"
                  />
                  <Badge size="sm" variant="subtle" :theme="row.error ? 'red' : 'green'" :label="outcome(row).label" class="shrink-0" />
                  <TruncatedText class="min-w-0 flex-1 truncate font-mono text-xs text-ink-gray-7" :text="row.reference_document" />
                  <span class="shrink-0 text-xs text-ink-gray-5" :title="formatDateTime(row.creation)">{{ timeAgo(row.creation) }}</span>
                </summary>

                <div class="flex flex-col gap-3 border-t border-outline-gray-2 px-3 pb-3 pt-3">
                  <div v-if="row.error" class="flex flex-col gap-1.5 rounded-4 bg-surface-red-1 px-3 py-2.5">
                    <p class="flex items-center gap-1.5 text-sm font-medium text-ink-red-7">
                      <span class="lucide-circle-alert size-4 shrink-0" aria-hidden="true" />{{ outcome(row).title }}
                    </p>
                    <p v-if="outcome(row).url" class="break-all font-mono text-xs text-ink-gray-7">{{ outcome(row).url }}</p>
                    <p class="text-sm text-ink-gray-7">{{ outcome(row).hint }}</p>
                  </div>

                  <TabButtons
                    v-model="tabs[row.name]"
                    class="self-start"
                    :options="[
                      { label: __('Payload'), value: 'payload' },
                      ...(row.response ? [{ label: __('Response'), value: 'response' }] : []),
                      ...(row.error ? [{ label: __('Error details'), value: 'error' }] : []),
                    ]"
                  />

                  <CodeBlock
                    v-if="(tabs[row.name] || 'payload') === 'payload'"
                    :title="__('Sent JSON')"
                    :code="pretty(row.data)"
                    max-height="max-h-[28rem]"
                  />

                  <template v-else-if="tabs[row.name] === 'response'">
                    <div v-if="isHtml(row.response)" class="flex flex-col gap-2">
                      <p class="text-sm text-ink-gray-6">
                        {{ __('The server answered with a web page instead of JSON, usually its error page. Its text:') }}
                      </p>
                      <TruncatedText
                        as="p"
                        class="line-clamp-4 rounded-4 bg-surface-base px-3 py-2 text-sm text-ink-gray-7"
                        :text="pageText(row.response) || __('(empty page)')"
                      />
                      <details>
                        <summary class="cursor-pointer text-xs text-ink-gray-5 hover:text-ink-gray-7">{{ __('Show raw HTML') }}</summary>
                        <CodeBlock class="mt-2" :title="__('Raw response')" :code="row.response" max-height="max-h-80" />
                      </details>
                    </div>
                    <CodeBlock v-else :title="__('Response body')" :code="pretty(row.response)" max-height="max-h-[28rem]" />
                  </template>

                  <CodeBlock v-else :title="__('Traceback')" :code="row.error" max-height="max-h-80" />
                </div>
              </details>
            </div>
          </ScrollArea>
        </div>
      </template>
    </ResponsiveDialog>
  </section>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Dropdown,
  ErrorMessage,
  FormControl,
  FormLabel,
  Password,
  ScrollArea,
  Skeleton,
  Switch,
  TabButtons,
  call,
  toast,
} from 'frappe-ui'
import CodeBlock from '@/components/Common/CodeBlock.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { useUI } from '@/stores/ui'
import { errorMessage, formatDateTime, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const METHOD = 'onechat.workspace.webhooks.'
const ui = useUI()

const rows = ref([])
const catalog = ref([])
const loading = ref(true)
const form = reactive({ open: false, name: null, url: '', events: [], secret: '', enabled: true, saving: false, error: '' })
const secret = reactive({ open: false, value: '' })
const log = reactive({ open: false, title: '', rows: [], loading: false })
const tabs = reactive({})

const logStats = computed(() => {
  const failed = log.rows.filter((row) => row.error).length
  return { failed, ok: log.rows.length - failed }
})

const HINTS = {
  400: 'The receiver rejected the request. Check that it accepts this JSON.',
  401: 'The receiver wants authentication. Add the key it expects, or check the signing secret.',
  403: 'The receiver refused the request. Check its permissions or the signing secret.',
  404: 'Nothing answers at this address. Check the URL for typos or a missing path.',
  405: 'The receiver does not accept POST requests at this address.',
  408: 'The receiver took too long to answer.',
  413: 'The payload was too large for the receiver.',
  429: 'The receiver is rate limiting. It will be retried later.',
}

function outcome(row) {
  if (!row.error) return { label: __('Delivered') }
  const text = String(row.error)
  const http = text.match(/(\d{3}) (?:Client|Server) Error: ([^\n]*?) for url: (\S+)/)
  if (http) {
    const code = Number(http[1])
    const hint =
      HINTS[code] || (code >= 500 ? 'The receiving server crashed or is down. Check its logs.' : 'The receiver did not accept the request.')
    return { label: `${code} ${http[2]}`, title: __('The server answered {0} {1}').format(code, http[2]), url: http[3], hint: __(hint) }
  }
  if (/timed? ?out|Timeout/i.test(text)) {
    return {
      label: __('Timed out'),
      title: __('The server did not answer in time'),
      hint: __('It may be slow or down. Frappe retries failed requests.'),
    }
  }
  if (/ConnectionError|Name or service not known|Failed to establish|refused/i.test(text)) {
    return {
      label: __('Unreachable'),
      title: __('Could not reach the server'),
      hint: __('Check the URL and that the server is online and reachable from this site.'),
    }
  }
  const last = text.trim().split('\n').at(-1)
  return { label: __('Failed'), title: __('The request failed'), hint: last }
}

function isHtml(value) {
  return /^\s*<(!doctype|html)/i.test(value || '')
}

function pageText(value) {
  try {
    const page = new DOMParser().parseFromString(value, 'text/html')
    page.querySelectorAll('script, style').forEach((node) => node.remove())
    return (page.body?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 600)
  } catch {
    return ''
  }
}

const grouped = computed(() => {
  const out = []
  for (const item of catalog.value) {
    let group = out.find((row) => row.name === item.group)
    if (!group) out.push((group = { name: item.group, items: [] }))
    group.items.push(item)
  }
  return out
})

function dot(row) {
  if (!row.enabled) return 'bg-surface-gray-4'
  if (row.last_error) return 'bg-surface-red-5'
  return row.last_sent_at ? 'bg-surface-green-6' : 'bg-surface-gray-4'
}

function pretty(value) {
  try {
    return JSON.stringify(JSON.parse(value), null, 2)
  } catch {
    return value
  }
}

function copy(value) {
  navigator.clipboard?.writeText(value).then(() => toast.success(__('Copied')))
}

async function load() {
  try {
    const [hooks, events] = await Promise.all([call(`${METHOD}webhooks`), catalog.value.length ? catalog.value : call(`${METHOD}catalog`)])
    rows.value = hooks
    catalog.value = events
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    loading.value = false
  }
}

function pick(event, value) {
  if (form.name) {
    form.events = value ? [event] : []
    return
  }
  form.events = value ? [...new Set([...form.events, event])] : form.events.filter((item) => item !== event)
}

function edit(row) {
  Object.assign(form, {
    open: true,
    name: row?.name || null,
    url: row?.url || '',
    events: row ? [row.event] : ['message.received', 'chat.created'],
    secret: '',
    enabled: row ? Boolean(row.enabled) : true,
    saving: false,
    error: '',
  })
}

async function save() {
  form.saving = true
  form.error = ''
  try {
    const saved = await call(`${METHOD}save`, {
      name: form.name,
      url: form.url,
      events: JSON.stringify(form.events),
      secret: form.secret || undefined,
      enabled: form.enabled ? 1 : 0,
    })
    form.open = false
    await load()
    if (saved.secret) Object.assign(secret, { open: true, value: saved.secret })
    else toast.success(__('Webhook saved'))
  } catch (err) {
    form.error = errorMessage(err)
  } finally {
    form.saving = false
  }
}

async function toggle(row, value) {
  const previous = row.enabled
  row.enabled = value ? 1 : 0
  try {
    await call(`${METHOD}set_enabled`, { name: row.name, enabled: value ? 1 : 0 })
  } catch (err) {
    row.enabled = previous
    toast.error(errorMessage(err))
  }
}

async function test(row) {
  try {
    const result = await call(`${METHOD}test`, { name: row.name })
    if (result?.success) toast.success(__('Test sent with the latest record'))
    else toast.error(__('Test failed: {0}').format(result?.error || __('no response')))
    load()
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

async function showLog(row) {
  Object.assign(log, { open: true, title: row.event, rows: [], loading: true })
  try {
    log.rows = await call(`${METHOD}deliveries`, { name: row.name })
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    log.loading = false
  }
}

function rotate(row) {
  ui.confirm({
    title: __('Create a new signing secret?'),
    message: __('The old secret stops working for this webhook. Update your server with the new one.'),
    action: __('Create new secret'),
    theme: 'red',
    onConfirm: async () => {
      const data = await call(`${METHOD}rotate_secret`, { name: row.name })
      Object.assign(secret, { open: true, value: data.secret })
    },
  })
}

function remove(row) {
  ui.confirm({
    title: __('Delete the {0} webhook?').format(row.event),
    message: __('Events stop being sent to {0}.').format(row.url),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call(`${METHOD}delete`, { name: row.name })
      rows.value = rows.value.filter((item) => item.name !== row.name)
      toast.success(__('Webhook deleted'))
    },
  })
}

function menu(row) {
  return [
    { label: __('Edit'), icon: 'lucide-pencil', onClick: () => edit(row) },
    { label: __('Send test'), icon: 'lucide-send', onClick: () => test(row) },
    { label: __('Request log'), icon: 'lucide-list', onClick: () => showLog(row) },
    {
      label: __('Open in desk'),
      icon: 'lucide-external-link',
      onClick: () => window.open(`/app/webhook/${encodeURIComponent(row.name)}`, '_blank', 'noopener'),
    },
    { label: __('New signing secret'), icon: 'lucide-key-round', onClick: () => rotate(row) },
    { label: __('Delete'), icon: 'lucide-trash-2', theme: 'red', onClick: () => remove(row) },
  ]
}

onMounted(load)
</script>

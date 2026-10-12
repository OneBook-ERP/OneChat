<template>
  <ResponsiveDialog v-model:open="open" :title="name ? __('Edit link') : __('New link')" size="3xl">
    <template #default>
      <div v-if="loading" class="flex flex-col gap-3">
        <Skeleton v-for="row in 5" :key="row" class="h-9 w-full" />
      </div>

      <div v-else class="grid gap-6 md:grid-cols-[minmax(0,1fr)_260px]">
        <div class="flex min-w-0 flex-col gap-4">
          <FormControl v-model="doc.title" type="text" :label="__('Title')" :required="true" :placeholder="__('Shop window poster')" />

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <LinkField
              :model-value="doc.whatsapp_account"
              doctype="OneChat Account"
              :label="__('Account')"
              :required="true"
              @update:model-value="setAccount"
            />
            <PhoneField
              v-if="!instagram"
              v-model="doc.display_number"
              :label="__('WhatsApp number')"
              :placeholder="lookingUp ? __('Looking up…') : ''"
              :description="numberHint"
            />
          </div>

          <p v-if="instagram" class="-mt-1 text-sm text-ink-gray-5">
            {{
              igUsername
                ? __('Opens a DM with @{0}. Instagram links can’t prefill a message.').format(igUsername)
                : __('Test the Instagram account’s connection first, so OneChat knows its username.')
            }}
          </p>
          <FormControl
            v-else
            v-model="doc.prefilled_message"
            type="textarea"
            :rows="3"
            :label="__('Prefilled message')"
            :placeholder="__('Hi! I saw your poster and want to know more.')"
            :description="__('People can edit it before sending.')"
          />

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormControl
              v-model="doc.ref_code"
              type="text"
              :label="__('Ref code')"
              :maxlength="12"
              :description="__('4 to 12 letters or digits')"
            />
            <LinkField v-model="doc.label" doctype="OneChat Label" :label="__('Label new contacts')" />
          </div>

          <Switch
            :model-value="!!doc.track"
            :label="__('Track conversations')"
            :description="__('Tracked invisibly. Customers do not see a code, and clicks on the short link are counted too.')"
            @update:model-value="(value) => (doc.track = value ? 1 : 0)"
          />

          <FormControl
            v-if="doc.track"
            v-model="doc.meta_ad_ids"
            type="text"
            :label="__('Meta ad IDs (optional)')"
            :placeholder="__('120212345678900123, 120212345678900456')"
            :description="__('Chats from click-to-WhatsApp ads with these IDs count for this link, with no message needed.')"
          />

          <div v-if="name" class="flex flex-col gap-2">
            <p class="text-base font-medium text-ink-gray-8">{{ __('Performance') }}</p>
            <ErrorMessage v-if="stats.error" :message="errorMessage(stats.error)" />
            <div class="grid grid-cols-3 gap-3">
              <NumberCard :title="__('Clicks')" :value="stats.data ? stats.data.clicks : null" :loading="stats.loading && !stats.data" />
              <NumberCard
                :title="__('Conversations started')"
                :value="stats.data ? stats.data.conversations : null"
                :loading="stats.loading && !stats.data"
              />
              <NumberCard
                :title="__('Last 30 days')"
                :value="stats.data ? stats.data.recent : null"
                :loading="stats.loading && !stats.data"
                :sparkline="stats.data?.recent ? { data: stats.data.series, type: 'bar' } : undefined"
              />
            </div>
            <p v-if="stats.data?.clicks" class="text-sm text-ink-gray-5">
              {{
                __('{0}% of clicks became a chat').format(Math.min(100, Math.round((stats.data.conversations * 100) / stats.data.clicks)))
              }}
            </p>
            <p v-if="stats.data?.last_conversation_at" class="text-sm text-ink-gray-5">
              {{ __('Last conversation {0}').format(timeAgo(stats.data.last_conversation_at)) }}
            </p>
          </div>

          <ErrorMessage :message="error" />
        </div>

        <aside class="flex flex-col gap-3 md:sticky md:top-0 md:self-start">
          <div class="flex aspect-square w-full items-center justify-center rounded-4 border border-outline-gray-1 bg-surface-base p-2">
            <Spinner v-if="qr.loading && !svg" class="size-5 text-ink-gray-5" />
            <img v-else-if="svg" :src="svgUrl" :alt="__('QR code for {0}').format(doc.title || __('this link'))" class="size-full" />
            <div v-else class="flex flex-col items-center gap-2 px-4 text-center">
              <span class="lucide-qr-code size-6 text-ink-gray-4" aria-hidden="true" />
              <p class="text-sm text-ink-gray-5">{{ qrHint }}</p>
            </div>
          </div>

          <div v-if="url" class="rounded-4 bg-surface-gray-1 px-3 py-2">
            <p class="text-xs text-ink-gray-5">{{ shortLink ? __('Short link, counts clicks') : __('WhatsApp link') }}</p>
            <p class="mt-0.5 break-all font-mono text-xs text-ink-gray-7">{{ shareUrl }}</p>
          </div>

          <div class="flex flex-col gap-2">
            <Button variant="subtle" icon-left="lucide-copy" :label="__('Copy link')" :disabled="!url" @click="copy" />
            <div class="grid grid-cols-2 gap-2">
              <Button variant="subtle" icon-left="lucide-file-down" :label="__('SVG')" :disabled="!svg" @click="downloadSvg" />
              <Button variant="subtle" icon-left="lucide-image-down" :label="__('PNG')" :disabled="!svg" @click="downloadPng" />
            </div>
          </div>
        </aside>
      </div>
    </template>

    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <div>
          <Button v-if="name" variant="ghost" theme="red" icon-left="lucide-trash-2" :label="__('Delete')" @click="remove" />
        </div>
        <div class="flex items-center gap-2">
          <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
          <Button variant="solid" :loading="saving" :label="__('Save')" @click="save" />
        </div>
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, Skeleton, Spinner, Switch, call, createResource, debounce, toast } from 'frappe-ui'
import PhoneField from '@/components/Common/PhoneField.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { NumberCard } from 'frappe-ui/charts'
import LinkField from '@/components/Common/LinkField.vue'
import { useUI } from '@/stores/ui'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
})

const emit = defineEmits(['saved', 'deleted'])

const open = defineModel('open', { type: Boolean, default: false })

const ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
const PNG_SIZE = 1024

const ui = useUI()
const doc = ref({})
const loading = ref(false)
const saving = ref(false)
const lookingUp = ref(false)
const lookupFailed = ref(false)
const error = ref('')
const svg = ref('')

const qr = createResource({
  url: 'onechat.campaigns.chat_links.qr',
  onSuccess(data) {
    svg.value = data?.url === shareUrl.value ? data.svg || '' : svg.value
  },
  onError() {
    svg.value = ''
  },
})

const stats = createResource({
  url: 'onechat.campaigns.chat_links.stats',
  makeParams: () => ({ name: props.name, days: 30 }),
})

const digits = computed(() => String(doc.value.display_number || '').replace(/\D/g, ''))
const accountChannel = ref('WhatsApp')
const igUsername = ref('')
const instagram = computed(() => accountChannel.value === 'Instagram')

const SYMBOLS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
const MARK = '\u2063'
const MARKS = ['\u200b', '\u200c', '\u200d', '\u2060']

function hidden(code) {
  const body = [...code]
    .map((char) => SYMBOLS.indexOf(char))
    .filter((index) => index >= 0)
    .map((index) => MARKS[Math.floor(index / 16)] + MARKS[Math.floor(index / 4) % 4] + MARKS[index % 4])
    .join('')
  return `${MARK}${body}${MARK}`
}

const message = computed(() => {
  const text = (doc.value.prefilled_message || '').trim()
  const code = (doc.value.ref_code || '').trim().toUpperCase()

  return doc.value.track && code ? `${text}${hidden(code)}` : text
})

const url = computed(() => {
  if (instagram.value) {
    if (!igUsername.value) return ''
    const code = (doc.value.ref_code || '').trim().toUpperCase()
    return `https://ig.me/m/${igUsername.value}` + (doc.value.track && code ? `?ref=${encodeURIComponent(code)}` : '')
  }
  if (!digits.value) return ''

  return `https://wa.me/${digits.value}` + (message.value ? `?text=${encodeURIComponent(message.value)}` : '')
})

const shortLink = computed(() => {
  const code = (doc.value.ref_code || '').trim().toUpperCase()
  const saved = props.name && doc.value.track && code && doc.value.short_url?.endsWith(`/c/${code}`)
  return saved ? doc.value.short_url : ''
})

const shareUrl = computed(() => shortLink.value || url.value)

const svgUrl = computed(() => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg.value)}`)

const numberHint = computed(() => {
  if (lookupFailed.value && !doc.value.display_number) return __('Could not read it from Meta. Type it with the country code.')

  return __('Include the country code')
})

const qrHint = computed(() => {
  if (!url.value) return __('Add the WhatsApp number to see the QR code.')
  if (qr.data && !qr.data.svg) return __('QR codes need the pyqrcode package on the server. The link still works.')

  return __('QR code unavailable')
})

function randomCode() {
  const bytes = crypto.getRandomValues(new Uint8Array(4))
  return 'OC' + Array.from(bytes, (byte) => ALPHABET[byte % ALPHABET.length]).join('')
}

function blank() {
  return {
    title: '',
    whatsapp_account: null,
    display_number: '',
    prefilled_message: '',
    ref_code: randomCode(),
    track: 1,
    label: null,
  }
}

watch(
  open,
  async (value) => {
    if (!value) return

    error.value = ''
    svg.value = ''
    lookupFailed.value = false

    if (!props.name) {
      doc.value = blank()
      const account = await call('frappe.client.get_value', {
        doctype: 'OneChat Account',
        filters: { is_default_outgoing: 1 },
        fieldname: 'name',
      }).catch(() => null)
      if (account?.name && !doc.value.whatsapp_account) setAccount(account.name)
      return
    }

    loading.value = true
    try {
      doc.value = await call('frappe.client.get', { doctype: 'OneChat Chat Link', name: props.name })
      stats.reload()
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

const loadQr = debounce((value) => {
  if (value) qr.submit({ url: value })
}, 400)

watch(
  shareUrl,
  (value) => {
    if (!value) svg.value = ''
    loadQr(value)
  },
  { immediate: true },
)

async function loadChannel(account) {
  const row = account
    ? await call('frappe.client.get_value', {
        doctype: 'OneChat Account',
        filters: { name: account },
        fieldname: ['channel', 'ig_username'],
      }).catch(() => null)
    : null
  accountChannel.value = row?.channel || 'WhatsApp'
  igUsername.value = row?.ig_username || ''
}

watch(() => doc.value.whatsapp_account, loadChannel, { immediate: true })

async function setAccount(account) {
  doc.value.whatsapp_account = account
  await loadChannel(account)
  if (!account || instagram.value || doc.value.display_number) return

  lookingUp.value = true
  lookupFailed.value = false
  try {
    const number = await call('onechat.campaigns.chat_links.account_number', { whatsapp_account: account })
    if (number && !doc.value.display_number) doc.value.display_number = number
    lookupFailed.value = !number
  } catch {
    lookupFailed.value = true
  } finally {
    lookingUp.value = false
  }
}

function problems() {
  const row = doc.value
  if (!row.title?.trim()) return __('Give the link a title')
  if (!row.whatsapp_account) return __('Pick an account')
  if (instagram.value && !igUsername.value) return __('Test the Instagram account’s connection first')
  if (row.ref_code && !/^[A-Za-z0-9]{4,12}$/.test(row.ref_code.trim())) return __('Ref code must be 4 to 12 letters or digits')

  return ''
}

async function save() {
  error.value = problems()
  if (error.value) return

  saving.value = true
  const values = {
    title: doc.value.title.trim(),
    whatsapp_account: doc.value.whatsapp_account,
    display_number: doc.value.display_number || '',
    prefilled_message: doc.value.prefilled_message || '',
    ref_code: (doc.value.ref_code || '').trim().toUpperCase(),
    track: doc.value.track ? 1 : 0,
    label: doc.value.label || null,
    meta_ad_ids: doc.value.track ? (doc.value.meta_ad_ids || '').trim() : '',
  }

  try {
    const saved = props.name
      ? await call('frappe.client.set_value', { doctype: 'OneChat Chat Link', name: props.name, fieldname: values })
      : await call('frappe.client.insert', { doc: { doctype: 'OneChat Chat Link', ...values } })

    toast.success(props.name ? __('Link saved') : __('Link created'))
    emit('saved', saved)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function fileName(extension) {
  const slug = (doc.value.title || 'whatsapp-link')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  return `${slug || 'whatsapp-link'}-qr.${extension}`
}

function download(blob, filename) {
  const href = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

async function copy() {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    toast.success(__('Link copied'))
  } catch {
    toast.error(__('Could not copy. Select the text and copy it yourself.'))
  }
}

function downloadSvg() {
  download(new Blob([svg.value], { type: 'image/svg+xml' }), fileName('svg'))
}

function downloadPng() {
  const image = new Image()
  image.onload = () => {
    const canvas = document.createElement('canvas')
    canvas.width = PNG_SIZE
    canvas.height = PNG_SIZE
    const context = canvas.getContext('2d')
    context.fillStyle = 'white'
    context.fillRect(0, 0, PNG_SIZE, PNG_SIZE)
    context.imageSmoothingEnabled = false
    context.drawImage(image, 0, 0, PNG_SIZE, PNG_SIZE)
    canvas.toBlob((blob) => blob && download(blob, fileName('png')), 'image/png')
  }
  image.onerror = () => toast.error(__('Could not render the QR code'))
  image.src = svgUrl.value
}

function remove() {
  ui.confirm({
    title: __('Delete this link?'),
    message: __('Printed QR codes and shared links keep working, but conversations are no longer counted.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: 'OneChat Chat Link', name: props.name })
      toast.success(__('Deleted'))
      emit('deleted', props.name)
      open.value = false
    },
  })
}
</script>

<template>
  <ResponsiveDialog v-model:open="open" :title="__('Send products')" size="lg">
    <template #default>
      <div class="flex flex-col gap-3">
        <FormControl type="text" v-model="search" :placeholder="__('Search catalog products')" @update:model-value="lookup">
          <template #prefix>
            <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
          </template>
        </FormControl>

        <ScrollArea class="rounded-4 border border-outline-gray-2" viewport-class="max-h-80">
          <div v-if="loading && !items.length" class="flex flex-col gap-2 p-2">
            <Skeleton v-for="row in 4" :key="row" class="h-12 w-full" />
          </div>
          <p v-else-if="!items.length" class="px-3 py-6 text-center text-sm text-ink-gray-5">
            {{
              search
                ? __('No catalog products match your search.')
                : __('Your WhatsApp catalog has no products yet. Add them on the Catalog page or sync them from ERPNext.')
            }}
          </p>
          <div v-else class="flex flex-col p-1">
            <button
              v-for="item in items"
              :key="item.item_code"
              type="button"
              class="flex items-center gap-3 rounded-3 px-2 py-1.5 text-left hover:bg-surface-gray-1 disabled:cursor-not-allowed disabled:opacity-50"
              :class="{ 'bg-surface-gray-2': picked.includes(item.item_code) }"
              :disabled="item.review_status === 'rejected'"
              @click="toggle(item)"
            >
              <span
                :class="picked.includes(item.item_code) ? 'lucide-square-check text-ink-gray-9' : 'lucide-square text-ink-gray-4'"
                class="size-4 shrink-0"
                aria-hidden="true"
              />
              <img :src="item.image" :alt="item.item_name" class="size-10 shrink-0 rounded-3 bg-surface-gray-2 object-cover" />
              <div class="min-w-0 flex-1">
                <TruncatedText as="p" class="truncate text-sm font-medium text-ink-gray-8" :text="item.item_name" />
                <TruncatedText as="p" class="truncate text-xs text-ink-gray-5" :text="item.item_code" />
              </div>
              <Badge v-if="item.review_status === 'rejected'" size="sm" variant="subtle" theme="red" :label="__('Rejected by Meta')" />
              <Badge
                v-else-if="item.review_status && item.review_status !== 'approved'"
                size="sm"
                variant="subtle"
                theme="amber"
                :label="__('In review')"
              />
              <Badge
                v-else-if="item.availability && item.availability !== 'in stock'"
                size="sm"
                variant="subtle"
                theme="gray"
                :label="__(item.availability)"
              />
              <span v-if="item.price" class="shrink-0 text-sm tabular-nums text-ink-gray-8">{{ item.price }}</span>
            </button>
          </div>
        </ScrollArea>

        <p class="text-sm text-ink-gray-5">
          {{ __('{0} of {1} selected. One product is sent as a product card, more as a product list.').format(picked.length, MAX) }}
        </p>

        <FormControl v-if="picked.length > 1" v-model="header" :label="__('Header')" :placeholder="__('Our products')" :maxlength="60" />
        <FormControl
          v-model="body"
          type="textarea"
          :label="__('Message')"
          :placeholder="picked.length > 1 ? __('Take a look at these products') : __('Optional')"
          :rows="2"
        />
        <ErrorMessage :message="error" />
      </div>
    </template>

    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="open = false" />
        <Button variant="solid" icon-left="lucide-send" :label="__('Send')" :disabled="!picked.length" :loading="sending" @click="send" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { ref, watch } from 'vue'
import { Badge, Button, ErrorMessage, FormControl, ScrollArea, Skeleton, call, debounce } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { runAction } from '@/data/integrations'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const MAX = 30

const props = defineProps({
  contact: { type: String, required: true },
  action: { type: Object, required: true },
})

const emit = defineEmits(['done'])

const open = defineModel('open', { type: Boolean, default: false })

const search = ref('')
const items = ref([])
const picked = ref([])
const header = ref('')
const body = ref('')
const loading = ref(false)
const sending = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  try {
    items.value = await call('onechat.integrations.erpnext_commerce.products', {
      contact: props.contact,
      search: search.value.trim() || undefined,
    })
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

const lookup = debounce(load, 300)

function toggle(item) {
  error.value = ''
  if (picked.value.includes(item.item_code)) {
    picked.value = picked.value.filter((code) => code !== item.item_code)
    return
  }
  if (picked.value.length >= MAX) {
    error.value = __('You can send up to {0} products at once.').format(MAX)
    return
  }
  picked.value = [...picked.value, item.item_code]
}

async function send() {
  sending.value = true
  error.value = ''
  try {
    const result = await runAction(props.contact, props.action, {
      items: picked.value,
      header: header.value.trim(),
      body: body.value.trim(),
    })
    emit('done', result)
    open.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    sending.value = false
  }
}

watch(
  open,
  (value) => {
    if (!value) return

    search.value = ''
    picked.value = []
    header.value = ''
    body.value = ''
    error.value = ''
    load()
  },
  { immediate: true },
)
</script>

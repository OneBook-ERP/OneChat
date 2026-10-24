<template>
  <div class="flex flex-col gap-5">
    <ErrorMessage :message="error" />
    <div v-if="loading && !state" class="flex flex-col gap-3">
      <Skeleton class="h-24 w-full rounded-5" />
      <Skeleton class="h-64 w-full rounded-5" />
    </div>

    <section v-else-if="access" class="flex flex-col gap-4 rounded-5 border border-outline-gray-2 p-5">
      <div class="flex items-start gap-3">
        <span class="grid size-9 shrink-0 place-content-center rounded-full bg-surface-amber-2 text-ink-amber-8" aria-hidden="true">
          <span :class="ACCESS[access.kind].icon" class="size-4" />
        </span>
        <div class="min-w-0">
          <h2 class="text-base font-semibold text-ink-gray-9">{{ __(ACCESS[access.kind].title) }}</h2>
          <p class="mt-0.5 text-sm text-ink-gray-6">{{ __(ACCESS[access.kind].text) }}</p>
        </div>
      </div>

      <ol v-if="access.kind === 'permission'" class="ml-12 list-decimal space-y-1 pl-4 text-sm text-ink-gray-7">
        <li>{{ __('In Meta Business Settings, open Users → System users and pick the user OneChat’s token belongs to.') }}</li>
        <li>
          {{ __('Generate a new token for your app with business_management and catalog_management, plus the two WhatsApp permissions.') }}
        </li>
        <li>{{ __('Paste it into this number in Settings → WhatsApp and save, then check again.') }}</li>
      </ol>
      <ol v-else-if="access.kind === 'token'" class="ml-12 list-decimal space-y-1 pl-4 text-sm text-ink-gray-7">
        <li>{{ __('Generate a new token for the system user in Meta Business Settings.') }}</li>
        <li>{{ __('Paste it into this number in Settings → WhatsApp and save, then check again.') }}</li>
      </ol>

      <div class="ml-12 flex flex-wrap items-center gap-2">
        <Button variant="solid" icon-left="lucide-rotate-cw" :label="__('Check again')" :loading="loading" @click="load" />
        <Button
          v-if="access.kind !== 'error'"
          icon-right="lucide-arrow-up-right"
          :label="__('Open Meta Business Settings')"
          link="https://business.facebook.com/settings/system-users"
        />
        <Button
          v-if="access.kind !== 'error' && sync"
          variant="ghost"
          :label="__('WhatsApp settings')"
          @click="ui.openSettings('accounts')"
        />
      </div>

      <Tooltip v-if="access.detail" :text="access.detail">
        <p class="ml-12 truncate text-xs text-ink-gray-5">{{ __('Meta: {0}').format(access.detail) }}</p>
      </Tooltip>
    </section>

    <template v-else-if="state && !state.catalog">
      <section class="flex flex-col gap-4 rounded-5 border border-outline-gray-2 p-5">
        <div>
          <h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Create a catalog') }}</h2>
          <p class="mt-1 text-sm text-ink-gray-6">
            {{
              __(
                'Customers browse it from the chat and send orders on WhatsApp. It is created in {0} and connected to this number.',
              ).format(state.business?.name || __('your Meta business'))
            }}
          </p>
        </div>
        <div class="flex flex-wrap items-end gap-2">
          <FormControl
            v-model="newName"
            class="w-full sm:w-72"
            type="text"
            :label="__('Catalog name')"
            :placeholder="__('Store catalog')"
          />
          <Button
            variant="solid"
            icon-left="lucide-plus"
            :label="__('Create catalog')"
            :loading="busy === 'create'"
            :disabled="!newName.trim()"
            @click="createCatalog"
          />
        </div>
      </section>

      <section v-if="state.owned.length" class="flex flex-col gap-2 rounded-5 border border-outline-gray-2 p-5">
        <h2 class="text-base font-semibold text-ink-gray-9">{{ __('Or use a catalog you already have') }}</h2>
        <div
          v-for="row in state.owned"
          :key="row.id"
          class="flex items-center justify-between gap-3 border-t border-outline-gray-1 py-2.5 first:border-0"
        >
          <div class="min-w-0">
            <TruncatedText as="p" class="truncate text-base text-ink-gray-8" :text="row.name" />
            <p class="text-sm text-ink-gray-5">{{ __('{0} products · ID {1}').format(formatNumber(row.product_count || 0), row.id) }}</p>
          </div>
          <Button
            size="sm"
            variant="subtle"
            :label="__('Connect')"
            :loading="busy === `connect-${row.id}`"
            @click="connectCatalog(row.id)"
          />
        </div>
      </section>
    </template>

    <template v-else-if="state">
      <section class="flex flex-col gap-4 rounded-5 border border-outline-gray-2 p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="lucide-shopping-bag size-5 text-ink-gray-6" aria-hidden="true" />
              <TruncatedText as="h2" class="truncate text-lg font-semibold text-ink-gray-9" :text="state.catalog.name" />
            </div>
            <p class="mt-1 text-sm text-ink-gray-5">
              {{
                [
                  state.catalog.product_count === 1
                    ? __('1 product')
                    : __('{0} products').format(formatNumber(state.catalog.product_count || 0)),
                  __('ID {0}').format(state.catalog.id),
                  state.business?.name && __('owned by {0}').format(state.business.name),
                ]
                  .filter(Boolean)
                  .join(' · ')
              }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <Button
              v-if="erpnext && sync"
              variant="subtle"
              icon-left="lucide-refresh-cw"
              :label="__('Sync from ERPNext')"
              :loading="busy === 'sync'"
              @click="syncErpnext"
            />
            <Dropdown :options="catalogMenu" align="end">
              <Button variant="subtle" icon-right="lucide-chevron-down" :label="__('Catalog')" />
            </Dropdown>
          </div>
        </div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div class="flex items-center justify-between gap-3 rounded-4 bg-surface-gray-1 px-3 py-2.5">
            <div class="min-w-0">
              <p class="text-sm font-medium text-ink-gray-8">{{ __('Show the catalog in chats') }}</p>
              <p class="text-xs text-ink-gray-5">{{ __('Adds the shop button to your WhatsApp profile and chats') }}</p>
            </div>
            <Switch
              :model-value="state.visible"
              :disabled="busy === 'commerce'"
              @update:model-value="(value) => setCommerce({ visible: value })"
            />
          </div>
          <div class="flex items-center justify-between gap-3 rounded-4 bg-surface-gray-1 px-3 py-2.5">
            <div class="min-w-0">
              <p class="text-sm font-medium text-ink-gray-8">{{ __('Allow a cart') }}</p>
              <p class="text-xs text-ink-gray-5">{{ __('Customers add several products and send one order') }}</p>
            </div>
            <Switch
              :model-value="state.cart"
              :disabled="busy === 'commerce'"
              @update:model-value="(value) => setCommerce({ cart: value })"
            />
          </div>
        </div>
      </section>

      <div v-if="setup" class="flex items-center justify-between gap-3 rounded-4 border border-outline-gray-2 px-3 py-2.5">
        <p class="flex min-w-0 items-center gap-2 text-sm text-ink-gray-7">
          <span class="lucide-package size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
          {{ __('Add and edit products and collections on the Catalog page.') }}
        </p>
        <Button size="sm" variant="subtle" icon-right="lucide-arrow-right" :label="__('Manage products')" @click="openCatalog" />
      </div>

      <template v-else>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <TabButtons
            v-model="tab"
            :options="[
              { label: __('Products'), value: 'products' },
              { label: __('Collections'), value: 'sets' },
            ]"
          />
          <div v-if="tab === 'products'" class="flex flex-wrap items-center gap-2">
            <FormControl v-model="search" class="w-full sm:w-60" type="text" :placeholder="__('Search name or product ID')">
              <template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
            </FormControl>
            <Button
              v-if="picked.length"
              variant="subtle"
              theme="red"
              icon-left="lucide-trash-2"
              :label="__('Delete {0}').format(picked.length)"
              @click="removeProducts(picked)"
            />
            <Button variant="solid" icon-left="lucide-plus" :label="__('Add product')" @click="editProduct(null)" />
          </div>
          <Button v-else variant="solid" icon-left="lucide-plus" :label="__('New collection')" @click="editSet(null)" />
        </div>

        <template v-if="tab === 'products'">
          <div v-if="productsLoading && !products.length" class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <Skeleton v-for="row in 8" :key="row" class="aspect-[5/4] w-full rounded-5" />
          </div>
          <EmptyState
            v-else-if="!products.length"
            icon="lucide-package"
            :title="search ? __('No products match') : __('No products yet')"
            :description="erpnext ? __('Add products here or sync them from ERPNext.') : __('Add your first product.')"
          />
          <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <div
              v-for="row in products"
              :key="row.id"
              class="group relative flex flex-col overflow-hidden rounded-5 border bg-surface-base transition-shadow hover:shadow-md"
              :class="picked.includes(row.retailer_id) ? 'border-outline-gray-4 ring-1 ring-outline-gray-4' : 'border-outline-gray-2'"
            >
              <div class="relative aspect-[5/3] w-full shrink-0 overflow-hidden bg-surface-gray-2">
                <img
                  v-if="row.image_url"
                  :src="row.image_url"
                  :alt="row.name"
                  class="absolute inset-0 size-full object-cover"
                  loading="lazy"
                />
                <span v-else class="absolute inset-0 grid place-content-center"
                  ><span class="lucide-image size-8 text-ink-gray-4" aria-hidden="true"
                /></span>
                <div
                  class="absolute left-2 top-2 rounded-2 bg-surface-base/90 p-1 shadow-sm transition-opacity"
                  :class="
                    picked.includes(row.retailer_id)
                      ? 'opacity-100'
                      : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100 max-sm:opacity-100'
                  "
                >
                  <Checkbox
                    :model-value="picked.includes(row.retailer_id)"
                    :aria-label="__('Select {0}').format(row.name)"
                    @update:model-value="(value) => togglePick(row.retailer_id, value)"
                  />
                </div>
                <div class="absolute right-2 top-2 rounded-3 bg-surface-base/90 shadow-sm">
                  <Dropdown :options="productMenu(row)" align="end">
                    <Button variant="ghost" size="sm" icon="lucide-ellipsis" :label="__('Actions for {0}').format(row.name)" />
                  </Dropdown>
                </div>
              </div>
              <div class="flex flex-1 flex-col gap-1.5 p-3">
                <TruncatedText as="p" class="line-clamp-2 text-base font-medium leading-snug text-ink-gray-9" :text="row.name" />
                <TruncatedText
                  as="p"
                  class="truncate text-xs text-ink-gray-5"
                  :text="[row.retailer_id, row.brand].filter(Boolean).join(' · ')"
                />
                <p class="mt-auto pt-1 text-lg font-semibold tabular-nums text-ink-gray-9">{{ row.price }}</p>
                <div class="flex flex-wrap gap-1">
                  <Badge
                    size="sm"
                    variant="subtle"
                    :theme="
                      row.availability === 'in stock'
                        ? 'green'
                        : ['available for order', 'preorder'].includes(row.availability)
                        ? 'blue'
                        : 'gray'
                    "
                    :label="__(row.availability || 'unknown')"
                  />
                  <Badge
                    v-if="REVIEW[row.review_status]"
                    size="sm"
                    variant="subtle"
                    :theme="REVIEW[row.review_status].theme"
                    :label="__(REVIEW[row.review_status].label)"
                  />
                  <Tooltip
                    v-if="row.visibility === 'staging'"
                    :text="__('Meta keeps this product hidden, so customers do not see it on WhatsApp')"
                  >
                    <Badge size="sm" variant="subtle" theme="red" :label="__('Hidden')" />
                  </Tooltip>
                </div>
              </div>
            </div>
          </div>
          <div v-if="more" class="flex justify-center">
            <Button variant="subtle" :label="__('Load more')" :loading="productsLoading" @click="loadProducts(true)" />
          </div>
        </template>

        <template v-else>
          <div v-if="setsLoading && !sets.length" class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <Skeleton v-for="row in 4" :key="row" class="aspect-[5/4] w-full rounded-5" />
          </div>
          <EmptyState
            v-else-if="!sets.length"
            icon="lucide-layers"
            :title="__('No collections yet')"
            :description="__('Group products, like New arrivals or Sofas, to send them together from a chat or a flow.')"
          />
          <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <div
              v-for="row in sets"
              :key="row.id"
              class="relative flex flex-col overflow-hidden rounded-5 border border-outline-gray-2 bg-surface-base transition-shadow hover:shadow-md"
            >
              <div class="relative aspect-[5/3] w-full shrink-0 overflow-hidden bg-surface-gray-2">
                <div v-if="row.images?.length >= 4" class="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-px">
                  <img
                    v-for="image in row.images.slice(0, 4)"
                    :key="image"
                    :src="image"
                    alt=""
                    class="size-full min-h-0 object-cover"
                    loading="lazy"
                  />
                </div>
                <img
                  v-else-if="row.images?.length"
                  :src="row.images[0]"
                  alt=""
                  class="absolute inset-0 size-full object-cover"
                  loading="lazy"
                />
                <span v-else class="absolute inset-0 grid place-content-center"
                  ><span class="lucide-layers size-8 text-ink-gray-4" aria-hidden="true"
                /></span>
                <div class="absolute right-2 top-2 rounded-3 bg-surface-base/90 shadow-sm">
                  <Dropdown :options="setMenu(row)" align="end">
                    <Button variant="ghost" size="sm" icon="lucide-ellipsis" :label="__('Actions for {0}').format(row.name)" />
                  </Dropdown>
                </div>
              </div>
              <div class="flex flex-col gap-0.5 p-3">
                <TruncatedText as="p" class="line-clamp-2 text-base font-medium leading-snug text-ink-gray-9" :text="row.name" />
                <p class="text-sm text-ink-gray-6">
                  {{ row.product_count === 1 ? __('1 product') : __('{0} products').format(formatNumber(row.product_count || 0)) }}
                </p>
                <TruncatedText as="p" class="truncate text-xs text-ink-gray-4" :text="__('ID {0}').format(row.id)" />
              </div>
            </div>
          </div>
        </template>
      </template>
    </template>
  </div>

  <ResponsiveDialog v-model:open="productOpen" :title="productForm.editing ? __('Edit product') : __('Add product')" size="xl">
    <template #default>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormControl
          v-model="productForm.retailer_id"
          type="text"
          :label="__('Product ID')"
          :disabled="productForm.editing"
          :description="__('Your SKU or item code. It cannot change later.')"
        />
        <FormControl v-model="productForm.name" type="text" :label="__('Name')" />
        <FormControl v-model="productForm.description" class="sm:col-span-2" type="textarea" :rows="3" :label="__('Description')" />
        <div class="grid grid-cols-[minmax(0,1fr)_6rem] gap-2">
          <FormControl v-model="productForm.price" type="number" :label="__('Price')" />
          <FormControl v-model="productForm.currency" type="text" :label="__('Currency')" placeholder="INR" />
        </div>
        <FormControl
          v-model="productForm.availability"
          type="select"
          :label="__('Availability')"
          :options="[
            { label: __('In stock'), value: 'in stock' },
            { label: __('Available for order'), value: 'available for order' },
            { label: __('Preorder'), value: 'preorder' },
            { label: __('Out of stock'), value: 'out of stock' },
          ]"
        />
        <FormControl v-model="productForm.brand" type="text" :label="__('Brand')" />
        <FormControl v-model="productForm.url" type="text" :label="__('Product page')" :placeholder="__('Optional link to your website')" />
        <div class="flex flex-col gap-1.5 sm:col-span-2">
          <FormLabel :label="__('Image')" required />
          <div class="flex items-center gap-3">
            <img
              v-if="productForm.image_url"
              :src="productForm.image_url"
              alt=""
              class="size-14 rounded-3 bg-surface-gray-2 object-cover"
            />
            <FileUploader :file-types="'image/*'" :private="false" @success="(file) => (productForm.image_url = file.file_url)">
              <template #default="{ uploading, progress, openFileSelector }">
                <Button
                  variant="subtle"
                  icon-left="lucide-image-up"
                  :loading="uploading"
                  :label="uploading ? `${progress}%` : productForm.image_url ? __('Replace image') : __('Upload image')"
                  @click="openFileSelector"
                />
              </template>
            </FileUploader>
          </div>
        </div>
      </div>
      <ErrorMessage :message="productError" class="mt-3" />
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="productOpen = false" />
        <Button variant="solid" :label="__('Save')" :loading="busy === 'product'" @click="saveProduct" />
      </div>
    </template>
  </ResponsiveDialog>

  <ResponsiveDialog v-model:open="setOpen" :title="setForm.id ? __('Edit collection') : __('New collection')" size="lg">
    <template #default>
      <div class="flex flex-col gap-3">
        <FormControl v-model="setForm.name" type="text" :label="__('Name')" :placeholder="__('New arrivals')" />
        <div class="flex flex-col gap-1.5">
          <FormLabel :label="__('Products')" />
          <MultiSelect v-model="setForm.ids" class="w-full" :options="productOptions" :placeholder="__('Pick products')" />
          <p class="text-xs text-ink-gray-5">
            {{ __('Lists the products loaded on the Products tab. Load more there to pick from the rest.') }}
          </p>
        </div>
      </div>
      <ErrorMessage :message="setError" class="mt-3" />
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="setOpen = false" />
        <Button variant="solid" :label="__('Save')" :loading="busy === 'set'" @click="saveSet" />
      </div>
    </template>
  </ResponsiveDialog>

  <ResponsiveDialog v-model:open="renameOpen" :title="__('Rename catalog')" size="sm">
    <template #default>
      <FormControl v-model="renameValue" type="text" :label="__('Name')" />
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="renameOpen = false" />
        <Button variant="solid" :label="__('Save')" :loading="busy === 'rename'" :disabled="!renameValue.trim()" @click="renameCatalog" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  Badge,
  Button,
  Checkbox,
  Dropdown,
  ErrorMessage,
  FileUploader,
  FormControl,
  FormLabel,
  MultiSelect,
  ScrollArea,
  Select,
  Skeleton,
  Switch,
  TabButtons,
  Tooltip,
  call,
  debounce,
  toast,
} from 'frappe-ui'
import EmptyState from '@/components/Common/EmptyState.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { activeIntegrations } from '@/data/integrations'
import { useUI } from '@/stores/ui'
import { useRouter } from 'vue-router'
import { errorMessage, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  account: { type: String, required: true },
  sync: { type: Boolean, default: true },
  setup: { type: Boolean, default: false },
})
const emit = defineEmits(['changed'])

const API = 'onechat.whatsapp.catalog.'
const REVIEW = {
  approved: { label: 'Approved', theme: 'green' },
  rejected: { label: 'Rejected', theme: 'red' },
  pending: { label: 'In review', theme: 'amber' },
  outdated: { label: 'Outdated', theme: 'gray' },
  '': { label: 'Not reviewed', theme: 'amber' },
}

const ui = useUI()
const router = useRouter()

function openCatalog() {
  ui.settingsDialog = false
  router.push({ name: 'Catalog', query: { account: props.account } })
}

const ACCESS = {
  permission: {
    icon: 'lucide-key-round',
    title: 'Give OneChat access to catalogs',
    text: 'The access token saved for this number can’t create or manage catalogs yet. Meta needs two more permissions on it.',
  },
  token: {
    icon: 'lucide-key-round',
    title: 'The access token was rejected',
    text: 'It has expired or was revoked in Meta, so OneChat can’t reach your catalogs.',
  },
  error: {
    icon: 'lucide-cloud-off',
    title: 'Couldn’t load the catalog',
    text: 'Meta didn’t answer as expected. Try again in a moment.',
  },
}

const access = computed(() => state.value?.blocked || (state.value && !state.value.catalog && state.value.limited) || null)
const account = computed(() => props.account)
const state = ref(null)
const loading = ref(false)
const error = ref('')
const busy = ref('')
const newName = ref('')
const tab = ref('products')
const search = ref('')
const products = ref([])
const after = ref(null)
const productsLoading = ref(false)
const picked = ref([])
const sets = ref([])
const setsLoading = ref(false)
const setsLoaded = ref(false)
const productOpen = ref(false)
const productError = ref('')
const productForm = reactive(blankProduct())
const setOpen = ref(false)
const setError = ref('')
const setForm = reactive({ id: null, name: '', ids: [] })
const renameOpen = ref(false)
const renameValue = ref('')

const erpnext = computed(() => activeIntegrations.value.some((row) => row.name === 'erpnext'))
const more = computed(
  () => Boolean(after.value) && (Boolean(search.value) || products.value.length < (state.value?.catalog?.product_count || 0)),
)
const productOptions = computed(() => {
  const known = products.value.map((row) => ({ label: `${row.name} (${row.retailer_id})`, value: row.retailer_id }))
  const extra = setForm.ids.filter((id) => !known.some((row) => row.value === id)).map((id) => ({ label: id, value: id }))
  return [...known, ...extra]
})

const catalogMenu = computed(() => [
  {
    label: __('Rename'),
    icon: 'lucide-pencil',
    onClick: () => ((renameValue.value = state.value.catalog.name), (renameOpen.value = true)),
  },
  { label: __('Disconnect from this number'), icon: 'lucide-unplug', onClick: disconnectCatalog },
  { label: __('Delete catalog'), icon: 'lucide-trash-2', theme: 'red', onClick: deleteCatalog },
])

function blankProduct() {
  return {
    editing: false,
    retailer_id: '',
    name: '',
    description: '',
    price: '',
    currency: 'INR',
    availability: 'in stock',
    brand: '',
    url: '',
    image_url: '',
  }
}

async function run(key, work, message) {
  busy.value = key
  error.value = ''
  try {
    const result = await work()
    if (message) toast.success(message)
    return result
  } catch (err) {
    error.value = errorMessage(err)
    return null
  } finally {
    busy.value = ''
  }
}

async function load() {
  if (!account.value) return
  loading.value = true
  error.value = ''
  try {
    state.value = await call(`${API}state`, { account: account.value, with_products: props.setup ? 0 : 1 })
    if (state.value.catalog && !props.setup) {
      if (state.value.products && !search.value) showProducts(state.value.products)
      else loadProducts()
      refreshSets()
    }
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function loadProducts(more = false) {
  productsLoading.value = true
  try {
    const data = await call(`${API}products`, {
      account: account.value,
      search: search.value || undefined,
      after: more ? after.value : undefined,
    })
    if (more) {
      products.value = [...products.value, ...data.rows]
      after.value = data.rows.length ? data.after : null
    } else showProducts(data)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    productsLoading.value = false
  }
}

function showProducts(data) {
  products.value = data.rows
  after.value = data.after
  picked.value = []
}

function refreshSets() {
  setsLoaded.value = false
  if (tab.value === 'sets') loadSets()
}

async function loadSets() {
  setsLoading.value = true
  try {
    sets.value = await call(`${API}product_sets`, { account: account.value })
    setsLoaded.value = true
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    setsLoading.value = false
  }
}

async function createCatalog() {
  const result = await run(
    'create',
    () => call(`${API}create`, { account: account.value, name: newName.value }),
    __('Catalog created and connected'),
  )
  if (result) {
    state.value = result
    newName.value = ''
    loadProducts()
    refreshSets()
  }
}

async function connectCatalog(id) {
  const result = await run(
    `connect-${id}`,
    () => call(`${API}connect`, { account: account.value, catalog_id: id }),
    __('Catalog connected'),
  )
  if (result) {
    state.value = result
    loadProducts()
    refreshSets()
  }
}

function disconnectCatalog() {
  ui.confirm({
    title: __('Disconnect this catalog?'),
    message: __('Customers stop seeing it on this number. The catalog and its products stay in Meta, so you can connect it again later.'),
    action: __('Disconnect'),
    theme: 'red',
    onConfirm: async () => {
      const result = await run(
        'disconnect',
        () => call(`${API}disconnect`, { account: account.value, catalog_id: state.value.catalog.id }),
        __('Catalog disconnected'),
      )
      if (result) state.value = result
    },
  })
}

function deleteCatalog() {
  ui.confirm({
    title: __('Delete {0}?').format(state.value.catalog.name),
    message: __('The catalog and all its products and collections are deleted from Meta. This cannot be undone.'),
    action: __('Delete catalog'),
    theme: 'red',
    onConfirm: async () => {
      const result = await run(
        'delete',
        () => call(`${API}delete`, { account: account.value, catalog_id: state.value.catalog.id }),
        __('Catalog deleted'),
      )
      if (result) state.value = result
    },
  })
}

async function renameCatalog() {
  const result = await run(
    'rename',
    () => call(`${API}rename`, { account: account.value, catalog_id: state.value.catalog.id, name: renameValue.value }),
    __('Catalog renamed'),
  )
  if (result) {
    state.value = result
    renameOpen.value = false
  }
}

async function setCommerce(change) {
  const result = await run('commerce', () =>
    call(`${API}set_commerce`, {
      account: account.value,
      cart: change.cart === undefined ? undefined : change.cart ? 1 : 0,
      visible: change.visible === undefined ? undefined : change.visible ? 1 : 0,
    }),
  )
  if (result) state.value = result
}

function togglePick(id, value) {
  picked.value = value ? [...picked.value, id] : picked.value.filter((item) => item !== id)
}

function productMenu(row) {
  return [
    { label: __('Edit'), icon: 'lucide-pencil', onClick: () => editProduct(row) },
    { label: __('Delete'), icon: 'lucide-trash-2', theme: 'red', onClick: () => removeProducts([row.retailer_id]) },
  ]
}

function editProduct(row) {
  productError.value = ''
  Object.assign(
    productForm,
    row
      ? {
          editing: true,
          retailer_id: row.retailer_id,
          name: row.name || '',
          description: row.description || '',
          price: String(row.price || '').replace(/[^\d.]/g, ''),
          currency: row.currency || 'INR',
          availability: row.availability || 'in stock',
          brand: row.brand || '',
          url: row.url || '',
          image_url: row.image_url || '',
        }
      : blankProduct(),
  )
  productOpen.value = true
}

async function saveProduct() {
  busy.value = 'product'
  productError.value = ''
  try {
    const { editing, ...values } = productForm
    toast.success(await call(`${API}save_product`, { account: account.value, values: JSON.stringify(values) }))
    productOpen.value = false
    setTimeout(() => loadProducts(), 4000)
  } catch (err) {
    productError.value = errorMessage(err)
  } finally {
    busy.value = ''
  }
}

function removeProducts(ids) {
  ui.confirm({
    title: ids.length === 1 ? __('Delete this product?') : __('Delete {0} products?').format(ids.length),
    message: __('They are removed from the Meta catalog. Items in ERPNext are not touched.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      const message = await run('delete-products', () =>
        call(`${API}delete_products`, { account: account.value, retailer_ids: JSON.stringify(ids) }),
      )
      if (message) {
        toast.success(message)
        products.value = products.value.filter((row) => !ids.includes(row.retailer_id))
        picked.value = []
      }
    },
  })
}

function setIds(row) {
  try {
    const filter = typeof row.filter === 'string' ? JSON.parse(row.filter) : row.filter
    return filter?.retailer_id?.is_any || []
  } catch {
    return []
  }
}

function setMenu(row) {
  return [
    { label: __('Edit'), icon: 'lucide-pencil', onClick: () => editSet(row) },
    { label: __('Delete'), icon: 'lucide-trash-2', theme: 'red', onClick: () => removeSet(row) },
  ]
}

function editSet(row) {
  setError.value = ''
  Object.assign(setForm, row ? { id: row.id, name: row.name, ids: setIds(row) } : { id: null, name: '', ids: [] })
  setOpen.value = true
}

async function saveSet() {
  busy.value = 'set'
  setError.value = ''
  try {
    sets.value = await call(`${API}save_product_set`, {
      account: account.value,
      name: setForm.name,
      retailer_ids: JSON.stringify(setForm.ids),
      set_id: setForm.id || undefined,
    })
    toast.success(__('Collection saved'))
    setOpen.value = false
  } catch (err) {
    setError.value = errorMessage(err)
  } finally {
    busy.value = ''
  }
}

function removeSet(row) {
  ui.confirm({
    title: __('Delete {0}?').format(row.name),
    message: __('Only the collection is deleted. Its products stay in the catalog.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      const result = await run(
        'delete-set',
        () => call(`${API}delete_product_set`, { account: account.value, set_id: row.id }),
        __('Collection deleted'),
      )
      if (result) sets.value = result
    },
  })
}

async function syncErpnext() {
  const message = await run('sync', () => call('onechat.integrations.erpnext_commerce.start_sync', { account: account.value }))
  if (message) toast.success(message)
}

watch(
  search,
  debounce(() => loadProducts(), 300),
)

watch(tab, (value) => {
  if (value === 'sets' && !setsLoaded.value && state.value?.catalog) loadSets()
})

watch(
  () => props.account,
  () => {
    state.value = null
    products.value = []
    sets.value = []
    setsLoaded.value = false
    load()
  },
)

watch(
  () => state.value?.catalog?.id || null,
  (id) => emit('changed', id),
)

onMounted(load)

defineExpose({ load, loading })
</script>

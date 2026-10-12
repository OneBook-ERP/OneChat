<template>
  <SettingsHeader>
    <div class="flex items-center justify-between gap-3">
      <div class="flex min-w-0 items-center gap-2">
        <Button variant="ghost" icon="lucide-arrow-left" :label="__('Back to accounts')" @click="emit('back')" />
        <TruncatedText
          as="h2"
          class="truncate text-lg font-semibold text-ink-gray-8"
          :text="name ? doc.account_name || name : __('New account')"
        />
      </div>
      <div v-if="['setup', 'catalog', 'payments'].includes(section)" class="flex shrink-0 items-center gap-2">
        <Button
          v-if="name && section === 'setup'"
          variant="ghost"
          theme="red"
          icon-left="lucide-trash-2"
          :label="__('Delete')"
          :disabled="loading"
          @click="remove"
        />
        <Button
          variant="solid"
          :label="name ? __('Save') : __('Create')"
          data-tour="save-account"
          :loading="saving"
          :disabled="loading"
          @click="save"
        />
      </div>
    </div>
  </SettingsHeader>

  <SettingsBody>
    <div v-if="loading" class="flex flex-col gap-3 pt-6">
      <Skeleton v-for="row in 6" :key="row" class="h-9 w-full" />
    </div>

    <template v-else>
      <div v-if="name" class="flex flex-col gap-4 pt-6">
        <Alert
          v-if="doc.account_alert"
          :theme="ALERT_THEMES[doc.account_alert_level] || 'blue'"
          :title="__(ALERT_TITLES[doc.account_alert_level] || 'From Meta')"
          :description="alertText"
          dismissible
          @dismiss="dismissAlert"
        />
        <TabButtons v-model="section" class="self-start" :options="sections" />
      </div>

      <AccountProfile v-if="name && section === 'profile'" :name="name" :business="doc.verified_name || doc.account_name" />

      <div v-else-if="name && section === 'payments'" class="flex flex-col gap-6 pt-6">
        <ErrorMessage :message="error" />
        <WhatsAppPayPanel :account="name" @changed="({ configuration }) => (doc.pay_configuration = configuration)" />
        <div class="flex flex-col gap-4">
          <div class="flex items-center gap-1">
            <p class="text-sm font-medium text-ink-gray-5">{{ __('Record payments in ERPNext') }}</p>
            <InfoHint
              :title="__('Record payments in ERPNext')"
              :text="
                __(
                  'When a customer pays, OneChat creates and submits a Payment Entry against the invoice or order. Save to keep these settings.',
                )
              "
            />
          </div>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormControl
              v-model="doc.pay_goods_type"
              type="select"
              :label="__('What you sell')"
              :options="[
                { label: __('Physical goods'), value: 'physical-goods' },
                { label: __('Digital goods or services'), value: 'digital-goods' },
              ]"
            />
            <div class="flex items-end pb-1.5">
              <Switch v-model="payAutoEntry" :label="__('Create Payment Entry when paid')" />
            </div>
            <FormControl
              v-if="payOptions.accounts.length"
              v-model="doc.pay_deposit_account"
              type="select"
              :label="__('Deposit account')"
              :options="[{ label: __('Company default'), value: '' }, ...payOptions.accounts.map((value) => ({ label: value, value }))]"
              :disabled="!payAutoEntry"
            />
            <FormControl
              v-else
              v-model="doc.pay_deposit_account"
              type="text"
              :label="__('Deposit account')"
              :placeholder="__('Company default')"
              :disabled="!payAutoEntry"
            />
            <FormControl
              v-if="payOptions.modes.length"
              v-model="doc.pay_mode_of_payment"
              type="select"
              :label="__('Mode of payment')"
              :options="[{ label: __('Not set'), value: '' }, ...payOptions.modes.map((value) => ({ label: value, value }))]"
              :disabled="!payAutoEntry"
            />
            <FormControl v-else v-model="doc.pay_mode_of_payment" type="text" :label="__('Mode of payment')" :disabled="!payAutoEntry" />
          </div>
        </div>
      </div>

      <div v-else-if="name && section === 'catalog'" class="flex flex-col gap-6 pt-6">
        <ErrorMessage :message="error" />
        <CatalogManager :account="name" :sync="false" setup @changed="(id) => (doc.catalog_id = id)" />
        <div v-if="commerce" class="flex flex-col gap-4">
          <div class="flex items-center gap-1">
            <p class="text-sm font-medium text-ink-gray-5">{{ __('Sync items from ERPNext') }}</p>
            <InfoHint
              :title="__('Sync items from ERPNext')"
              :text="
                __(
                  'Sends enabled sales items that have an image and a price to this catalog, so customers can browse and order inside WhatsApp. Save to keep these settings.',
                )
              "
            />
          </div>

          <div class="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
            <div>
              <FieldLabel :label="__('Price list')" :description="__(CATALOG.price_list)" />
              <FormControl
                v-if="catalogOptions.price_lists.length"
                v-model="doc.commerce_price_list"
                type="select"
                :options="[{ label: __('Default selling price list'), value: '' }, ...optionsOf('price_lists')]"
              />
              <FormControl v-else v-model="doc.commerce_price_list" type="text" :placeholder="__('Default selling price list')" />
            </div>
            <div class="flex items-center justify-between gap-3 rounded-4 border border-outline-gray-2 px-3 py-2 sm:col-span-2">
              <div class="min-w-0">
                <p class="text-sm font-medium text-ink-gray-8">{{ __('Prices include GST') }}</p>
                <p class="text-sm text-ink-gray-5">
                  {{
                    __(
                      'Adds each item’s GST rate to the catalog price, using the tax template ERPNext picks for a sales order. WhatsApp orders are converted back to the price before tax.',
                    )
                  }}
                </p>
              </div>
              <Switch :model-value="!!doc.catalog_with_gst" @update:model-value="(value) => (doc.catalog_with_gst = value ? 1 : 0)" />
            </div>
            <div>
              <FieldLabel :label="__('Item groups')" :description="__(`${CATALOG.items} ${CATALOG.item_groups}`)" />
              <MultiSelect
                v-model="filters.catalog_item_groups"
                class="w-full"
                :options="optionsOf('item_groups')"
                :placeholder="__('All item groups')"
              />
            </div>
            <div>
              <FieldLabel :label="__('Brands')" :description="__(CATALOG.brands)" />
              <MultiSelect v-model="filters.catalog_brands" class="w-full" :options="optionsOf('brands')" :placeholder="__('All brands')" />
            </div>
            <FieldControl v-model="doc.catalog_stock" :field="CATALOG.catalog_stock" />
            <FieldControl v-if="useStock" v-model="doc.catalog_when_out" :field="CATALOG.catalog_when_out" />
            <div>
              <FieldLabel :label="__('Warehouses')" :description="__(CATALOG.warehouses)" />
              <MultiSelect
                v-model="filters.catalog_warehouses"
                class="w-full"
                :options="optionsOf('warehouses')"
                :placeholder="useStock ? __('All warehouses') : __('Only used with ERPNext stock')"
                :disabled="!useStock"
              />
            </div>
            <div class="flex flex-col gap-1.5 sm:col-span-2">
              <FieldLabel
                :label="__('More conditions')"
                :description="__('Only items that match every condition are synced. Use any Item field, including custom fields.')"
              />
              <RecordFilters v-model="itemFilters" :fields="catalogOptions.item_fields" :empty-text="__('No extra conditions.')" />
            </div>
            <div class="sm:col-span-2">
              <FieldControl v-model="doc.catalog_auto_sync" :field="CATALOG.catalog_auto_sync" />
            </div>
          </div>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex min-w-0 flex-1 items-center gap-2">
              <span
                :class="doc.catalog_last_synced ? 'lucide-circle-check text-ink-green-6' : 'lucide-circle-dashed text-ink-gray-5'"
                class="size-4 shrink-0"
                aria-hidden="true"
              />
              <p class="truncate text-sm text-ink-gray-7" :title="doc.catalog_sync_status || ''">
                {{
                  doc.catalog_last_synced
                    ? __('Last synced {0}').format(timeAgo(doc.catalog_last_synced))
                    : __('Items have not been synced yet')
                }}
                <span v-if="doc.catalog_sync_status" class="text-ink-gray-5"> · {{ doc.catalog_sync_status.split(NEWLINE)[0] }}</span>
              </p>
              <InfoHint
                v-if="doc.catalog_sync_status && doc.catalog_sync_status.includes(NEWLINE)"
                :title="__('Last sync')"
                :text="doc.catalog_sync_status"
              />
            </div>
            <Button
              icon-left="lucide-refresh-cw"
              :label="__('Sync items to catalog')"
              :loading="syncing"
              :disabled="!name || !doc.catalog_id"
              @click="syncCatalog"
            />
          </div>
        </div>
      </div>

      <div v-else class="flex flex-col gap-6 pt-6">
        <ErrorMessage :message="error" />

        <AccountSetupGuide
          :doc="doc"
          :saved="!!name"
          :has-token="hasToken"
          :has-secret="hasSecret"
          :checking="checking"
          @test="checkConnection"
          @connect="connectInstagram"
        />

        <div v-if="name" class="rounded-5 border border-outline-gray-1 px-4 py-3.5">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="flex min-w-0 flex-1 items-start gap-3">
              <span class="mt-0.5 grid size-8 shrink-0 place-content-center rounded-full" :class="CONNECTION[connectionState].tone">
                <span :class="CONNECTION[connectionState].icon" class="size-4" aria-hidden="true" />
              </span>
              <div class="min-w-0">
                <p class="text-base font-medium text-ink-gray-8">{{ __(CONNECTION[connectionState].label) }}</p>
                <p class="mt-0.5 break-words text-sm text-ink-gray-5">
                  {{ doc.connection_message || __('Save your changes, then test that the token and IDs work with Meta.') }}
                </p>
                <p v-if="doc.last_checked_at" class="mt-0.5 text-sm text-ink-gray-4">
                  {{ __('Checked {0}').format(formatDateTime(doc.last_checked_at)) }}
                </p>
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <Button
                v-if="instagram"
                variant="solid"
                icon-left="lucide-log-in"
                :loading="connecting"
                :label="hasToken ? __('Reconnect Instagram') : __('Connect with Instagram')"
                @click="connectInstagram"
              />
              <Button
                icon-left="lucide-plug-zap"
                :loading="checking"
                :label="__('Test connection')"
                data-tour="test-connection"
                @click="checkConnection"
              />
            </div>
          </div>

          <dl
            v-if="doc.connection_status === 'Connected'"
            class="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-outline-gray-1 pt-3 sm:grid-cols-4"
          >
            <div v-for="item in health" :key="item.label" class="min-w-0">
              <dt class="text-sm text-ink-gray-5">{{ __(item.label) }}</dt>
              <TruncatedText as="dd" class="mt-0.5 truncate text-base" :class="item.class || 'text-ink-gray-8'" :text="item.value || '—'" />
            </div>
          </dl>
        </div>

        <div v-for="group in visibleGroups" :key="group.label" :data-tour="group.tour">
          <p class="mb-3 text-sm font-medium text-ink-gray-5">{{ __(group.label) }}</p>
          <div class="grid grid-cols-2 gap-x-4 gap-y-4">
            <div v-for="field in group.fields" :key="field.fieldname" :class="field.half ? 'col-span-2 sm:col-span-1' : 'col-span-2'">
              <FieldControl v-model="doc[field.fieldname]" :field="fieldFor(field)" />
            </div>
          </div>
        </div>

        <div v-if="instagram" data-tour="instagram-signin">
          <p class="mb-3 text-sm font-medium text-ink-gray-5">{{ __('Instagram sign-in') }}</p>
          <p class="mb-1.5 text-xs text-ink-gray-5">{{ __('Redirect URL') }}</p>
          <div class="flex items-center gap-2">
            <TruncatedText
              as="code"
              class="min-w-0 flex-1 truncate rounded-3 bg-surface-gray-2 px-2.5 py-1.5 font-mono text-sm text-ink-gray-7"
              :text="oauthRedirect"
            />
            <Button icon-left="lucide-copy" :label="__('Copy')" @click="copy(oauthRedirect)" />
          </div>
          <p class="mt-1.5 text-sm text-ink-gray-5">
            {{
              __(
                'In your Meta app, add this under Instagram → API setup with Instagram login → Business login settings → OAuth redirect URIs. Then use Connect with Instagram above.',
              )
            }}
          </p>
        </div>

        <div data-tour="webhook-setup">
          <p class="mb-3 text-sm font-medium text-ink-gray-5">{{ __('Webhook') }}</p>
          <div class="flex flex-col gap-4">
            <div>
              <p class="mb-1.5 text-xs text-ink-gray-5">{{ __('Callback URL') }}</p>
              <div class="flex items-center gap-2">
                <TruncatedText
                  as="code"
                  class="min-w-0 flex-1 truncate rounded-3 bg-surface-gray-2 px-2.5 py-1.5 font-mono text-sm text-ink-gray-7"
                  :text="webhookUrl"
                />
                <Button icon-left="lucide-copy" :label="__('Copy')" @click="copy(webhookUrl)" />
              </div>
              <p class="mt-1.5 text-sm text-ink-gray-5">
                {{
                  instagram
                    ? __(
                        'Paste this into Instagram → API setup with Instagram login → Configure webhooks in your Meta app, with the verify token below.',
                      )
                    : __('Paste this into the WhatsApp webhook settings of your Meta app, with the verify token below.')
                }}
              </p>
              <div v-if="name" class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                <span
                  class="inline-flex items-center gap-1.5"
                  :class="doc.webhook_verified_at || doc.webhook_last_event_at ? 'text-ink-green-6' : 'text-ink-gray-5'"
                >
                  <span
                    :class="doc.webhook_verified_at || doc.webhook_last_event_at ? 'lucide-circle-check' : 'lucide-circle-dashed'"
                    class="size-3.5"
                    aria-hidden="true"
                  />
                  {{
                    doc.webhook_verified_at
                      ? __('Verified {0}').format(timeAgo(doc.webhook_verified_at))
                      : doc.webhook_last_event_at
                        ? __('Working')
                        : __('Not verified yet')
                  }}
                </span>
                <span class="inline-flex items-center gap-1.5" :class="doc.webhook_last_event_at ? 'text-ink-green-6' : 'text-ink-gray-5'">
                  <span :class="doc.webhook_last_event_at ? 'lucide-radio' : 'lucide-circle-dashed'" class="size-3.5" aria-hidden="true" />
                  {{
                    doc.webhook_last_event_at
                      ? __('Last event {0}').format(timeAgo(doc.webhook_last_event_at))
                      : __('No events received yet')
                  }}
                </span>
              </div>
            </div>

            <div class="flex items-end gap-2">
              <FieldControl
                v-model="doc.webhook_verify_token"
                class="min-w-0 flex-1"
                :field="{ fieldname: 'webhook_verify_token', label: 'Webhook verify token', type: 'password' }"
              />
              <Button :label="__('Generate')" @click="generateToken" />
              <Button
                icon="lucide-copy"
                :label="__('Copy verify token')"
                :disabled="!doc.webhook_verify_token"
                @click="copy(doc.webhook_verify_token)"
              />
            </div>
            <div data-tour="app-secret">
              <FieldControl
                v-model="doc.app_secret"
                :field="{
                  fieldname: 'app_secret',
                  label: 'App secret',
                  type: 'password',
                  placeholder: hasSecret ? 'Leave blank to keep the current secret' : '',
                  description: 'Meta app → App settings → Basic. OneChat uses it to reject webhook calls that did not come from Meta.',
                }"
              />
              <p v-if="!hasSecret && !doc.app_secret" class="mt-1.5 flex items-center gap-1.5 text-sm text-ink-amber-5">
                <span class="lucide-triangle-alert size-3.5 shrink-0" aria-hidden="true" />
                {{
                  instagram
                    ? __('Instagram webhooks are rejected until you add the app secret.')
                    : __('WhatsApp webhooks are rejected until you add the app secret.')
                }}
              </p>
            </div>
          </div>
        </div>

        <div class="divide-y divide-outline-gray-1">
          <SettingsRow
            v-if="name && doc.business_id"
            :title="__('Spend data')"
            :description="
              doc.spend_storage === LIVE_SPEND
                ? __('Costs for this number are fetched from Meta when Insights opens. Nothing is stored.')
                : __('A copy of Meta\'s daily spend for this number is kept in OneChat, so Insights loads fast and keeps history.')
            "
          >
            <TabButtons
              :model-value="doc.spend_storage || STORED_SPEND"
              :options="[
                { label: __('Stored'), value: STORED_SPEND },
                { label: __('Live'), value: LIVE_SPEND },
              ]"
              @update:model-value="changeSpendStorage"
            />
          </SettingsRow>
          <SettingsRow
            v-if="!instagram"
            :title="__('Default for incoming messages')"
            :description="__('Messages from new contacts are filed under this account')"
          >
            <Switch :model-value="!!doc.is_default_incoming" @update:model-value="(value) => (doc.is_default_incoming = value ? 1 : 0)" />
          </SettingsRow>
          <SettingsRow
            v-if="!instagram"
            :title="__('Default for outgoing messages')"
            :description="__('Replies and broadcasts use this account unless told otherwise')"
          >
            <Switch :model-value="!!doc.is_default_outgoing" @update:model-value="(value) => (doc.is_default_outgoing = value ? 1 : 0)" />
          </SettingsRow>
          <SettingsRow :title="__('Read receipts')" :description="__(READ_RECEIPT_HELP[doc.read_receipts || READ_RECEIPTS[0].value])">
            <Select
              class="w-60"
              :options="READ_RECEIPTS"
              :model-value="doc.read_receipts || READ_RECEIPTS[0].value"
              @update:model-value="(value) => (doc.read_receipts = value)"
            />
          </SettingsRow>
        </div>
      </div>
    </template>
  </SettingsBody>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  Alert,
  Button,
  ErrorMessage,
  FormControl,
  MultiSelect,
  Select,
  SettingsBody,
  SettingsHeader,
  SettingsRow,
  Skeleton,
  Switch,
  TabButtons,
  call,
  toast,
} from 'frappe-ui'
import FieldControl from '@/components/Common/FieldControl.vue'
import FieldLabel from '@/components/Common/FieldLabel.vue'
import InfoHint from '@/components/Common/InfoHint.vue'
import RecordFilters from '@/components/Common/RecordFilters.vue'
import AccountProfile from './AccountProfile.vue'
import CatalogManager from '@/components/Campaigns/CatalogManager.vue'
import WhatsAppPayPanel from './WhatsAppPayPanel.vue'
import AccountSetupGuide from './AccountSetupGuide.vue'
import { activeIntegrations } from '@/data/integrations'
import { useSocket } from '@/data/socket'
import { useUI } from '@/stores/ui'
import { errorMessage, formatDateTime, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  name: { type: String, default: null },
})

const emit = defineEmits(['back', 'saved', 'deleted'])

const ui = useUI()

const WHATSAPP_API = { url: 'https://graph.facebook.com', version: 'v21.0' }

const DEFAULTS = {
  status: 'Active',
  channel: 'WhatsApp',
  ...WHATSAPP_API,
  is_default_incoming: 0,
  is_default_outgoing: 0,
  read_receipts: 'When an agent opens the chat',
}

const GROUPS = [
  {
    label: 'Account',
    tour: 'account-fields',
    fields: [
      { fieldname: 'account_name', label: 'Account name', type: 'data', required: true, half: true },
      {
        fieldname: 'status',
        label: 'Status',
        type: 'select',
        options: ['Active', 'Inactive'],
        half: true,
        description: "Inactive accounts don't send or receive messages",
      },
      {
        fieldname: 'channel',
        label: 'Channel',
        type: 'select',
        options: ['WhatsApp', 'Instagram'],
        half: true,
        description: "Can't be changed after saving",
      },
    ],
  },
  {
    label: 'Meta connection',
    tour: 'meta-fields',
    fields: [
      { fieldname: 'url', label: 'API URL', type: 'url', half: true, whatsapp: true },
      { fieldname: 'version', label: 'API version', type: 'data', placeholder: 'v21.0', half: true, whatsapp: true },
      { fieldname: 'phone_id', label: 'Phone number ID', type: 'data', required: true, half: true, whatsapp: true },
      { fieldname: 'business_id', label: 'Business account ID', type: 'data', half: true, whatsapp: true },
      { fieldname: 'app_id', label: 'App ID', type: 'data', half: true },
      { fieldname: 'token', label: 'Access token', type: 'password', half: true },
    ],
  },
]

const CATALOG = {
  catalog_id: {
    fieldname: 'catalog_id',
    label: 'Catalog ID',
    type: 'data',
    placeholder: 'e.g. 1234567890',
    description: 'From Meta Commerce Manager → Catalog → Settings. The catalog must be connected to this WhatsApp Business account.',
  },
  price_list:
    'Prices sent to the catalog and used for WhatsApp orders. Leave it on the default to use the selling price list from ERPNext Selling Settings.',
  items:
    'Only enabled sales items with an image and a price are sent. Narrow them further by item group or brand. Leave both empty to send every such item.',
  item_groups: 'Sub-groups are included, so picking a parent group sends everything under it.',
  brands: 'Only items of these brands are sent.',
  warehouses: 'Stock is counted only in these warehouses and their sub-warehouses. Leave empty to count every warehouse.',
  catalog_stock: {
    fieldname: 'catalog_stock',
    label: 'Availability',
    type: 'select',
    options: [
      { label: 'Always in stock', value: 'Always in stock' },
      { label: 'Use ERPNext stock', value: 'Use ERPNext stock' },
    ],
    description: 'Use ERPNext stock marks stock items with no quantity as out of stock. Keep Always in stock for made-to-order items.',
  },
  catalog_when_out: {
    fieldname: 'catalog_when_out',
    label: 'When stock runs out',
    type: 'select',
    options: [
      { label: 'Show as out of stock', value: 'Show as out of stock' },
      { label: 'Keep it orderable', value: 'Keep it orderable' },
      { label: 'Follow ERPNext negative stock', value: 'Follow ERPNext negative stock' },
    ],
    description:
      'Out of stock hides the Add button. Keep it orderable marks the item Available for order, so customers can still order it and know it ships later. Follow ERPNext does that only when Allow Negative Stock is on in Stock Settings.',
  },
  catalog_auto_sync: {
    fieldname: 'catalog_auto_sync',
    label: 'Sync every night',
    type: 'check',
    description: 'Keeps prices, images and availability up to date without pressing Sync.',
  },
}

const READ_RECEIPTS = [
  { label: __('When an agent opens the chat'), value: 'When an agent opens the chat' },
  { label: __('When a message arrives'), value: 'When a message arrives' },
  { label: __('Never'), value: 'Never' },
]
const READ_RECEIPT_HELP = {
  'When an agent opens the chat': 'The customer sees blue ticks once someone on your team opens the chat.',
  'When a message arrives': 'The customer sees blue ticks straight away, even before anyone reads the message.',
  Never: 'The customer never sees blue ticks from this number.',
}

const STORED_SPEND = 'Store in OneChat'
const LIVE_SPEND = 'Fetch live from Meta'

function changeSpendStorage(mode) {
  if (mode === (doc.value.spend_storage || STORED_SPEND)) return
  const apply = async () => {
    try {
      toast.success(await call('onechat.insights.costs.set_storage', { account: props.name, mode }))
      doc.value.spend_storage = mode
    } catch (err) {
      error.value = errorMessage(err)
    }
  }
  if (mode === LIVE_SPEND) {
    ui.confirm({
      title: __('Stop storing spend for this number?'),
      message: __(
        'The spend already stored for this number is deleted. Its costs are then fetched from Meta each time Insights opens, so they load a little slower. Budget alerts keep working.',
      ),
      action: __('Delete and go live'),
      theme: 'red',
      onConfirm: apply,
    })
    return
  }
  apply()
}

const CATALOG_VALUES = ['catalog_id', 'commerce_price_list', 'catalog_stock', 'catalog_when_out']
const CATALOG_CHECKS = ['catalog_with_gst']
const NEWLINE = String.fromCharCode(10)
const CATALOG_LISTS = ['catalog_item_groups', 'catalog_brands', 'catalog_warehouses']

const FIELDS = [
  ...GROUPS.flatMap((group) => group.fields.map((field) => field.fieldname)),
  'webhook_verify_token',
  'app_secret',
  'is_default_incoming',
  'is_default_outgoing',
  'read_receipts',
]

const commerce = computed(() => activeIntegrations.value.some((row) => row.name === 'erpnext'))
const filters = reactive({ catalog_item_groups: [], catalog_brands: [], catalog_warehouses: [] })
const catalogOptions = reactive({ item_groups: [], brands: [], warehouses: [], price_lists: [], item_fields: [] })
const itemFilters = ref([])
const useStock = computed(() => doc.value.catalog_stock === 'Use ERPNext stock')

function parseList(value) {
  try {
    const list = value ? JSON.parse(value) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

function optionsOf(key) {
  const names = new Set(catalogOptions[key])
  if (key !== 'price_lists') for (const name of filters[`catalog_${key}`] || []) names.add(name)
  return [...names].map((name) => ({ label: name, value: name }))
}

async function loadCatalogOptions() {
  if (!commerce.value) return
  try {
    Object.assign(catalogOptions, await call('onechat.integrations.erpnext_commerce.catalog_filters'))
  } catch {
    return
  }
}

const doc = ref({ ...DEFAULTS })
const loading = ref(!!props.name)
const saving = ref(false)
const error = ref('')
const syncing = ref(false)
const checking = ref(false)
const hasSecret = ref(false)
const hasToken = ref(false)
const section = ref('setup')

const setupDone = computed(() =>
  Boolean(props.name && commerce.value && doc.value.business_id && doc.value.connection_status === 'Connected'),
)

const instagram = computed(() => doc.value.channel === 'Instagram')

const visibleGroups = computed(() =>
  GROUPS.map((group) => ({ ...group, fields: group.fields.filter((field) => !(instagram.value && field.whatsapp)) })),
)

watch(
  () => doc.value.channel,
  (channel) => {
    if (props.name) return
    Object.assign(
      doc.value,
      channel === 'Instagram' ? { url: '', version: '', is_default_incoming: 0, is_default_outgoing: 0 } : WHATSAPP_API,
    )
  },
)

const sections = computed(() => [
  { label: __('Setup'), value: 'setup', iconLeft: 'lucide-plug' },
  ...(instagram.value ? [] : [{ label: __('Business profile'), value: 'profile', iconLeft: 'lucide-store' }]),
  ...(setupDone.value
    ? [
        { label: __('Catalog'), value: 'catalog', iconLeft: 'lucide-shopping-bag' },
        { label: __('Payments'), value: 'payments', iconLeft: 'lucide-wallet' },
      ]
    : []),
])

watch(setupDone, (done) => {
  if (!done && ['catalog', 'payments'].includes(section.value)) section.value = 'setup'
})

const payOptions = reactive({ accounts: [], modes: [] })
const payAutoEntry = computed({
  get: () => doc.value.pay_auto_entry === undefined || doc.value.pay_auto_entry === null || !!Number(doc.value.pay_auto_entry),
  set: (value) => (doc.value.pay_auto_entry = value ? 1 : 0),
})

watch(section, async (value) => {
  if (value !== 'payments' || payOptions.accounts.length || payOptions.modes.length) return
  try {
    Object.assign(payOptions, await call('onechat.whatsapp.pay.erp_options'))
  } catch {
    return
  }
})

const ALERT_THEMES = { Critical: 'red', Warning: 'amber', Info: 'blue' }
const ALERT_TITLES = { Critical: 'Action needed', Warning: 'Heads up from Meta', Info: 'Update from Meta' }

const alertText = computed(() =>
  doc.value.account_alert_at ? `${doc.value.account_alert} (${timeAgo(doc.value.account_alert_at)})` : doc.value.account_alert,
)

const CONNECTION = {
  none: { label: 'Not checked yet', icon: 'lucide-plug', tone: 'bg-surface-gray-2 text-ink-gray-5' },
  Connected: { label: 'Connected to Meta', icon: 'lucide-circle-check', tone: 'bg-surface-green-2 text-ink-green-3' },
  Error: { label: 'Connection problem', icon: 'lucide-circle-alert', tone: 'bg-surface-red-2 text-ink-red-4' },
}
const QUALITY = { Green: 'text-ink-green-3', Yellow: 'text-ink-amber-3', Red: 'text-ink-red-4' }

const connectionState = computed(() => (CONNECTION[doc.value.connection_status] ? doc.value.connection_status : 'none'))

const health = computed(() =>
  instagram.value
    ? [
        { label: 'Instagram account ID', value: doc.value.ig_user_id },
        { label: 'Username', value: doc.value.ig_username && `@${doc.value.ig_username}` },
        { label: 'Token expires', value: doc.value.token_expires_at && formatDateTime(doc.value.token_expires_at) },
      ]
    : whatsappHealth.value,
)

const whatsappHealth = computed(() => [
  { label: 'Verified name', value: doc.value.verified_name },
  { label: 'Phone number', value: doc.value.display_phone_number },
  { label: 'Quality', value: doc.value.quality_rating, class: QUALITY[doc.value.quality_rating] },
  { label: 'Messaging limit', value: doc.value.messaging_limit },
])

const oauthRedirect = `${window.location.origin}/api/method/onechat.instagram.oauth.callback`
const connecting = ref(false)

async function connectInstagram() {
  if (!props.name) {
    error.value = __('Save the account first.')
    return
  }
  connecting.value = true
  error.value = ''
  try {
    window.location.href = await call('onechat.instagram.oauth.start', { name: props.name })
  } catch (err) {
    error.value = errorMessage(err)
    connecting.value = false
  }
}

const webhookUrl = computed(
  () => `${window.location.origin}/api/method/onechat.${instagram.value ? 'instagram' : 'whatsapp'}.webhook.webhook`,
)

function fieldFor(field) {
  if (field.fieldname === 'account_name' || field.fieldname === 'channel') return { ...field, readOnly: !!props.name }
  if (field.fieldname === 'token' && instagram.value) {
    return {
      ...field,
      label: 'Instagram access token',
      required: false,
      placeholder: props.name && hasToken.value ? 'Leave blank to keep the current token' : 'Optional if you use Connect with Instagram',
    }
  }
  if (field.fieldname === 'app_id' && instagram.value) return { ...field, label: 'Instagram app ID' }
  if (field.fieldname === 'token' && props.name) {
    return { ...field, required: false, placeholder: 'Leave blank to keep the current token' }
  }
  if (field.fieldname === 'token') return { ...field, required: true }

  return field
}

async function load() {
  if (!props.name) return

  try {
    const value = await call('frappe.client.get', { doctype: 'OneChat Account', name: props.name })
    hasSecret.value = !!value.app_secret
    hasToken.value = !!value.token
    doc.value = { ...value, token: '', app_secret: '' }
    for (const fieldname of CATALOG_LISTS) filters[fieldname] = parseList(value[fieldname])
    itemFilters.value = parseList(value.catalog_item_filters)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function values() {
  const out = {}

  for (const fieldname of FIELDS) out[fieldname] = doc.value[fieldname] ?? null
  if (commerce.value) Object.assign(out, catalogValues(), payValues())
  if (props.name) {
    delete out.account_name
    if (!out.token) delete out.token
    if (!out.app_secret) delete out.app_secret
  }

  return out
}

function catalogValues() {
  const out = { catalog_auto_sync: doc.value.catalog_auto_sync ? 1 : 0 }
  for (const fieldname of CATALOG_CHECKS) out[fieldname] = doc.value[fieldname] ? 1 : 0
  for (const fieldname of CATALOG_VALUES) out[fieldname] = doc.value[fieldname] || null
  for (const fieldname of CATALOG_LISTS) out[fieldname] = filters[fieldname].length ? JSON.stringify(filters[fieldname]) : null
  out.catalog_item_filters = itemFilters.value.length ? JSON.stringify(itemFilters.value) : null
  return out
}

function payValues() {
  return {
    pay_goods_type: doc.value.pay_goods_type || 'physical-goods',
    pay_auto_entry: payAutoEntry.value ? 1 : 0,
    pay_deposit_account: doc.value.pay_deposit_account || null,
    pay_mode_of_payment: doc.value.pay_mode_of_payment || null,
  }
}

function missing() {
  return visibleGroups.value
    .flatMap((group) => group.fields)
    .map(fieldFor)
    .filter((field) => field.required && !String(doc.value[field.fieldname] ?? '').trim())
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
      ? await call('frappe.client.set_value', { doctype: 'OneChat Account', name: props.name, fieldname: values() })
      : await call('frappe.client.insert', { doc: { doctype: 'OneChat Account', ...values() } })

    toast.success(props.name ? __('Account saved') : __('Account created'))
    emit('saved', saved)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

function remove() {
  ui.confirm({
    title: __('Delete this account?'),
    message: __('Messages already filed under it stay, but OneChat stops using this number.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('frappe.client.delete', { doctype: 'OneChat Account', name: props.name })
      toast.success(__('Account deleted'))
      emit('deleted', props.name)
    },
  })
}

async function dismissAlert() {
  try {
    await call('onechat.whatsapp.accounts.dismiss_alert', { name: props.name })
    doc.value.account_alert = null
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

async function checkConnection() {
  checking.value = true
  try {
    Object.assign(doc.value, await call('onechat.whatsapp.accounts.check', { name: props.name }))
    if (doc.value.connection_status === 'Connected') toast.success(__('Connected to Meta'))
    else toast.error(__('Connection problem'))
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    checking.value = false
  }
}

function generateToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  doc.value.webhook_verify_token = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(__('Copied'))
  } catch {
    toast.error(__('Could not copy. Select the text and copy it yourself.'))
  }
}

async function syncCatalog() {
  syncing.value = true
  error.value = ''
  try {
    await call('frappe.client.set_value', {
      doctype: 'OneChat Account',
      name: props.name,
      fieldname: catalogValues(),
    })
    const message = await call('onechat.integrations.erpnext_commerce.start_sync', { account: props.name })
    doc.value.catalog_sync_status = __('Sync in progress')
    toast.success(message)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    syncing.value = false
  }
}

function onSynced(data) {
  if (data?.account !== props.name) return

  doc.value.catalog_sync_status = data.status
  doc.value.catalog_last_synced = new Date().toISOString()
  toast.success(__('Catalog sync finished'))
}

onMounted(() => {
  load()
  loadCatalogOptions()
  useSocket().on('onechat_catalog_sync', onSynced)
})

onBeforeUnmount(() => useSocket().off('onechat_catalog_sync', onSynced))
</script>

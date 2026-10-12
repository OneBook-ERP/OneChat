<template>
  <PageHeader v-if="isDesktop && !embedded">
    <Breadcrumbs :items="crumbs" />
    <div class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </PageHeader>

  <PageHeaderBase v-else class="z-10 flex h-[var(--mobile-header-height,52px)] items-center gap-1 border-b bg-surface-base px-2">
    <PageHeaderBackButton v-if="back" :to="back" size="lg" />

    <h1 class="flex min-w-0 flex-1 items-center text-xl-semibold leading-tight text-ink-gray-9">
      <button
        v-if="section && !back"
        type="button"
        class="inline-flex h-10 min-w-0 max-w-full items-center gap-1 rounded-5 px-2 transition-colors active:bg-surface-gray-2"
        :aria-label="__('Switch page in {0}').format(__(section.label))"
        @click="picker = true"
      >
        <TruncatedText class="min-w-0 truncate" :text="heading" />
        <span class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
      </button>
      <TruncatedText v-else class="min-w-0 truncate px-1" :text="heading" />
    </h1>

    <div v-if="!embedded" class="flex shrink-0 items-center">
      <template v-if="$slots.actions && !actions().supported">
        <slot name="actions" />
      </template>
      <Dropdown v-else-if="actions().secondary.length" :options="actions().secondary" align="end">
        <Button variant="ghost" size="lg" icon="lucide-ellipsis" :label="__('More actions')" />
      </Dropdown>
      <Button variant="ghost" size="lg" icon="lucide-search" :label="__('Search')" @click="ui.openSearch" />
      <NotificationsBell />
      <Dropdown :options="menuOptions" align="end">
        <Button
          variant="ghost"
          size="lg"
          :label="session.user.availability === 'Away' ? __('Account, you are away') : __('Account, you are available')"
        >
          <template #icon>
            <span class="relative inline-flex">
              <Avatar :image="session.user.image" :label="session.user.full_name" size="md" />
              <span
                class="absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full ring-2 ring-surface-base"
                :class="session.user.availability === 'Away' ? 'bg-surface-gray-5' : 'bg-surface-green-6'"
                aria-hidden="true"
              />
            </span>
          </template>
        </Button>
      </Dropdown>
    </div>
  </PageHeaderBase>

  <div
    v-if="!isDesktop && !embedded && actions().primary"
    class="pointer-events-none fixed inset-x-0 z-20 flex justify-end px-4"
    :class="ui.fullScreen ? 'bottom-[calc(1rem+env(safe-area-inset-bottom))]' : 'bottom-[calc(4.5rem+env(safe-area-inset-bottom))]'"
  >
    <Button
      class="pointer-events-auto !h-12 max-w-full !rounded-full !px-5 shadow-xl"
      variant="solid"
      size="lg"
      :icon-left="actions().primary.icon"
      :label="actions().primary.label"
      :loading="actions().primary.loading"
      :disabled="actions().primary.disabled"
      @click="actions().primary.onClick"
    />
  </div>

  <ResponsiveDialog v-if="section" v-model:open="picker" :title="__(section.label)" size="sm">
    <template #default>
      <div class="-mx-2">
        <SectionNav :section="section" :counts="section.key === 'inbox' ? inboxCounts : {}" touch @navigate="picker = false" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { Comment, Fragment, computed, ref, useSlots } from 'vue'
import { useRoute } from 'vue-router'
import { Avatar, Breadcrumbs, Button, Dropdown, PageHeader, PageHeaderBackButton, PageHeaderBase } from 'frappe-ui'
import NotificationsBell from '@/components/Common/NotificationsBell.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import SectionNav from './SectionNav.vue'
import { useAccountOptions } from '@/composables/useAccountOptions'
import { useNumberMenu } from '@/composables/useNumberMenu'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { embedded } from '@/data/embed'
import { appName } from '@/data/install'
import { inboxCounts } from '@/data/inbox'
import { useSection } from '@/composables/useSection'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  title: { type: String, default: '' },
  tail: { type: Array, default: () => [] },
  back: { type: [String, Object], default: null },
})

const route = useRoute()
const slots = useSlots()
const picker = ref(false)
const ui = useUI()
const { isDesktop } = useBreakpoint()
const { section, current } = useSection()
const accountOptions = useAccountOptions()
const { numbers, numberMenu } = useNumberMenu()
const menuOptions = computed(() =>
  !isDesktop.value && numbers.hasMenu ? [...numberMenu.value, ...accountOptions.value] : accountOptions.value,
)

const heading = computed(
  () => props.title || (current.value?.label || route.meta.title ? __(current.value?.label || route.meta.title) : appName.value),
)

const crumbs = computed(() => {
  if (!section.value) return [{ label: heading.value }, ...props.tail]

  const head = { label: __(section.value.label), route: section.value.route }
  const page = current.value ? { label: __(current.value.label), route: current.value.to } : { label: __(route.meta.title || '') }

  return [head, page, ...props.tail].filter((crumb) => crumb.label)
})

function flatten(nodes) {
  return nodes.flatMap((node) => {
    if (node.type === Fragment) return flatten(Array.isArray(node.children) ? node.children : [])
    if (node.type === Comment) return []
    if (typeof node.type === 'symbol' && typeof node.children === 'string' && !node.children.trim()) return []

    return [node]
  })
}

function flag(value) {
  return value === '' || Boolean(value)
}

function describe(node) {
  const attrs = node.props || {}
  const handlers = [].concat(attrs.onClick || [])

  return {
    label: attrs.label,
    icon: attrs['icon-left'] || attrs.iconLeft || attrs.icon,
    variant: attrs.variant,
    loading: flag(attrs.loading),
    disabled: flag(attrs.disabled),
    onClick: (event) => handlers.forEach((handler) => handler(event)),
  }
}

function actions() {
  const nodes = flatten(slots.actions?.() || [])
  const supported = nodes.every((node) => node.type === Button && node.props?.label)
  if (!supported) return { supported, primary: null, secondary: [] }

  const described = nodes.map(describe)
  const primary = described.findLast((action) => action.variant === 'solid') || null
  const secondary = described
    .filter((action) => action !== primary)
    .map((action) => ({
      label: action.label,
      icon: action.icon,
      disabled: action.disabled || action.loading,
      onClick: action.onClick,
    }))

  return { supported, primary, secondary }
}
</script>

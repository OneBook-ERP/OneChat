<template>
  <SidebarRail class="border-r">
    <Dropdown v-if="numbers.hasMenu" :options="numberMenu" side="right" align="start" :offset="8">
      <button
        type="button"
        class="relative flex size-9 items-center justify-center rounded-4 hover:bg-surface-gray-3"
        :title="
          numbers.scoped ? __('Some accounts or teams are hidden') : __('Accounts and teams')
        "
      >
        <Avatar :image="appLogo" :label="appName" size="lg" shape="square" class="size-7" />
        <span
          v-if="numbers.scoped"
          class="absolute -bottom-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-surface-amber-2 px-1 text-2xs font-bold text-ink-amber-7 ring-2 ring-[--surface-sidebar]"
        >
          {{ numbers.hidden.length + numbers.hiddenTeams.length }}
        </span>
      </button>
    </Dropdown>
    <div v-else class="flex size-9 items-center justify-center" :title="appName">
      <Avatar :image="appLogo" :label="appName" size="lg" shape="square" class="size-7" />
    </div>

    <div class="flex w-full flex-1 flex-col items-center gap-3 pt-3">
      <SidebarRailItem
        v-for="item in sections"
        :key="item.key"
        :label="__(item.label)"
        :icon="item.icon"
        :active="section?.key === item.key"
        :badge="item.key === 'inbox' ? unreadTotal : 0"
        badge-style="count"
        @click="router.push(item.route)"
      />
    </div>

    <div class="flex flex-col items-center gap-2.5">
      <SidebarRailItem
        v-if="session.user.is_admin && onboarding.status && !onboarding.complete && !onboarding.dismissed"
        :label="__('Setup guide, {0} steps left').format(onboarding.remaining)"
        variant="ghost"
        icon="lucide-rocket"
        :active="onboarding.open"
        :badge="onboarding.remaining"
        badge-style="count"
        @click="onboarding.show()"
      />
      <SidebarRailItem :label="__('Search')" variant="ghost" icon="lucide-search" @click="ui.openSearch" />
      <NotificationsBell rail />
      <SidebarRailItem
        :label="__('Settings')"
        variant="ghost"
        icon="lucide-settings"
        :active="ui.settingsDialog"
        @click="ui.openSettings()"
      />

      <SidebarRailItem
        v-if="section"
        :label="ui.sidebarCollapsed ? __('Show the sidebar') : __('Hide the sidebar')"
        variant="ghost"
        :icon="ui.sidebarCollapsed ? 'lucide-panel-left-open' : 'lucide-panel-left-close'"
        @click="ui.toggleSidebar"
      />

      <Dropdown :options="accountOptions" side="right" align="end" :offset="8">
        <span class="flex">
          <SidebarRailItem :label="session.user.full_name">
            <span class="relative flex">
              <Avatar :image="session.user.image" :label="session.user.full_name" size="lg" shape="square" class="size-7" />
              <span
                class="absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full ring-2 ring-[--surface-sidebar]"
                :class="session.user.availability === 'Away' ? 'bg-surface-gray-5' : 'bg-surface-green-6'"
                aria-hidden="true"
              />
            </span>
          </SidebarRailItem>
        </span>
      </Dropdown>
    </div>
  </SidebarRail>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Avatar, Dropdown, SidebarRail, SidebarRailItem } from 'frappe-ui'
import NotificationsBell from '@/components/Common/NotificationsBell.vue'
import { useAccountOptions } from '@/composables/useAccountOptions'
import { useNumberMenu } from '@/composables/useNumberMenu'
import { useSection } from '@/composables/useSection'
import { unreadTotal } from '@/data/inbox'
import { appLogo, appName } from '@/data/install'
import { session } from '@/data/session'
import { useOnboarding } from '@/stores/onboarding'
import { useUI } from '@/stores/ui'
import { translate as __ } from '@/translation'

const router = useRouter()
const ui = useUI()
const onboarding = useOnboarding()
const { sections, section } = useSection()

const accountOptions = useAccountOptions({ settings: false })
const { numbers, numberMenu } = useNumberMenu()
</script>

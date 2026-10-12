<template>
  <MobileShell>
    <slot />

    <template v-if="!ui.fullScreen" #nav>
      <MobileNav>
        <MobileNavItem
          v-for="item in navSections"
          :key="item.key"
          :label="__(item.label)"
          :icon="item.icon"
          :to="item.route"
          :active="section?.key === item.key"
        >
          <template v-if="item.key === 'inbox' && unreadTotal" #default="{ active }">
            <span class="relative flex">
              <span :class="[item.icon, active ? 'text-ink-gray-8' : 'text-ink-gray-5']" class="size-6" aria-hidden="true" />
              <Badge variant="solid" theme="red" size="sm" class="absolute -right-2.5 -top-1.5 tabular-nums">
                {{ countLabel(unreadTotal) }}
              </Badge>
            </span>
          </template>
        </MobileNavItem>
      </MobileNav>
    </template>
  </MobileShell>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, MobileNav, MobileNavItem, MobileShell } from 'frappe-ui'
import { useSection } from '@/composables/useSection'
import { unreadTotal } from '@/data/inbox'
import { useUI } from '@/stores/ui'
import { countLabel } from '@/utils/format'
import { translate as __ } from '@/translation'

const ui = useUI()
const { sections, section } = useSection()

const navSections = computed(() => sections.value.filter((item) => item.key !== 'audit'))
</script>

import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { activeIntegrations, linkTypes } from '@/data/integrations'
import { LABEL_DOTS, counts, labels } from '@/data/inbox'
import { SECTIONS, matches, withLabels, withLinks } from '@/data/navigation'
import { session } from '@/data/session'

export function useSection() {
  const route = useRoute()

  const channelKey = computed(() => (counts.data?.channels || []).join(','))

  const readable = (item) => !item.doctype || session.user.can_read?.[item.doctype] !== false

  const sections = computed(() =>
    SECTIONS.filter(
      (item) => (!item.admin || session.user.is_admin) && (!item.systemManager || session.user.is_system_manager) && readable(item),
    ),
  )
  const section = computed(() => {
    const base = SECTIONS.find((item) => item.key === route.meta.section) || null
    const built = withLabels(withLinks(base, linkTypes.value), labels.data || [], LABEL_DOTS)
    if (!built) return built
    const active = new Set(activeIntegrations.value.map((row) => row.name))
    const channels = channelKey.value ? channelKey.value.split(',') : []
    return {
      ...built,
      groups: built.groups
        .map((group) => ({
          ...group,
          items: group.items.filter(
            (item) =>
              (!item.integration || active.has(item.integration)) && (!item.channel || channels.includes(item.channel)) && readable(item),
          ),
        }))
        .filter((group) => group.items.length),
    }
  })

  const current = computed(() => {
    for (const group of section.value?.groups || []) {
      const item = group.items.find((row) => matches(route, row.to))
      if (item) return item
    }

    return null
  })

  const isActive = (to) => matches(route, to)

  return { sections, section, current, isActive }
}

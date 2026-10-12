import { call, createResource } from 'frappe-ui'
import { reactive } from 'vue'

const GUEST = {
  name: 'Guest',
  full_name: 'Guest',
  image: null,
  is_admin: false,
  is_system_manager: false,
  availability: 'Available',
}

export const session = reactive({
  user: { availability: 'Available', ...(window.onechat_user || GUEST) },
  logout: () => {
    logoutResource.submit()
  },
  setAvailability: async (status) => {
    await call('onechat.inbox.routing.set_availability', { status })
    session.user.availability = status
  },
})

export function can(doctype, ptype = 'read') {
  return session.user.can?.[doctype]?.[ptype] !== false
}

const logoutResource = createResource({
  url: 'logout',
  onSuccess: () => window.location.replace('/login'),
})

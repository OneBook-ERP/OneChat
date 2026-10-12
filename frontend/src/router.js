import { createRouter, createWebHistory } from 'vue-router'
import { SECTIONS } from '@/data/navigation'
import { embedded } from '@/data/embed'
import { session } from '@/data/session'

const routes = [
  { path: '/', redirect: '/inbox' },
  {
    path: '/inbox/:contact?',
    name: 'Inbox',
    component: () => import('@/pages/Inbox.vue'),
    meta: { section: 'inbox', title: 'Conversations', fixed: true },
  },
  {
    path: '/comments',
    name: 'Comments',
    component: () => import('@/pages/Comments.vue'),
    meta: { section: 'inbox', title: 'Comments', fixed: true },
  },
  {
    path: '/contacts',
    name: 'Contacts',
    component: () => import('@/pages/Contacts.vue'),
    meta: { section: 'contacts', title: 'Contacts', fixed: true },
  },
  {
    path: '/contacts/:contact',
    name: 'CustomerProfile',
    component: () => import('@/pages/CustomerProfile.vue'),
    meta: { section: 'contacts', title: 'Customer' },
  },
  {
    path: '/contacts/segments',
    name: 'Segments',
    component: () => import('@/pages/Segments.vue'),
    meta: { section: 'contacts', title: 'Segments', fixed: true },
  },
  {
    path: '/contacts/duplicates',
    name: 'Duplicates',
    component: () => import('@/pages/Duplicates.vue'),
    meta: { section: 'contacts', title: 'Duplicates', fixed: true },
  },
  {
    path: '/contacts/notes',
    name: 'Notes',
    component: () => import('@/pages/Notes.vue'),
    meta: { section: 'contacts', title: 'Notes', fixed: true },
  },
  { path: '/campaigns', redirect: '/campaigns/templates' },
  {
    path: '/campaigns/templates',
    name: 'Templates',
    component: () => import('@/pages/Templates.vue'),
    meta: { section: 'campaigns', title: 'Templates', admin: true, fixed: true },
  },
  {
    path: '/campaigns/broadcasts',
    name: 'Broadcasts',
    component: () => import('@/pages/Broadcasts.vue'),
    meta: { section: 'campaigns', title: 'Broadcasts', admin: true, fixed: true },
  },
  {
    path: '/campaigns/lists',
    name: 'RecipientLists',
    component: () => import('@/pages/RecipientLists.vue'),
    meta: { section: 'campaigns', title: 'Recipient lists', admin: true, fixed: true },
  },
  {
    path: '/campaigns/forms',
    name: 'Forms',
    component: () => import('@/pages/Forms.vue'),
    meta: { section: 'campaigns', title: 'Forms', admin: true, fixed: true },
  },
  {
    path: '/campaigns/forms/:name',
    name: 'FormBuilder',
    component: () => import('@/pages/FormBuilder.vue'),
    meta: { section: 'campaigns', title: 'Form builder', admin: true, fixed: true },
  },
  {
    path: '/campaigns/media',
    name: 'Media',
    component: () => import('@/pages/Media.vue'),
    meta: { section: 'campaigns', title: 'Media library', admin: true },
  },
  {
    path: '/campaigns/catalog',
    name: 'Catalog',
    component: () => import('@/pages/Catalog.vue'),
    meta: { section: 'campaigns', title: 'Catalog', admin: true, fixed: true },
  },
  {
    path: '/campaigns/links',
    name: 'ChatLinks',
    component: () => import('@/pages/ChatLinks.vue'),
    meta: { section: 'campaigns', title: 'Links & QR', admin: true, fixed: true },
  },
  {
    path: '/campaigns/report',
    name: 'DeliveryReport',
    component: () => import('@/pages/DeliveryReport.vue'),
    meta: { section: 'campaigns', title: 'Delivery report', admin: true },
  },
  { path: '/automation', redirect: '/automation/rules' },
  {
    path: '/automation/rules',
    name: 'Rules',
    component: () => import('@/pages/Rules.vue'),
    meta: { section: 'automation', title: 'Notification rules', admin: true, fixed: true },
  },
  {
    path: '/automation/flows',
    name: 'Flows',
    component: () => import('@/pages/Flows.vue'),
    meta: { section: 'automation', title: 'Flows', admin: true, fixed: true },
  },
  {
    path: '/automation/flows/:name',
    name: 'FlowBuilder',
    component: () => import('@/pages/FlowBuilder.vue'),
    meta: { section: 'automation', title: 'Flow builder', admin: true, fixed: true },
  },
  {
    path: '/automation/auto-replies',
    name: 'AutoReplies',
    component: () => import('@/pages/AutoReplies.vue'),
    meta: { section: 'automation', title: 'Auto replies', admin: true, fixed: true },
  },
  {
    path: '/automation/logs',
    name: 'ExecutionLogs',
    component: () => import('@/pages/ExecutionLogs.vue'),
    meta: { section: 'automation', title: 'Execution logs', admin: true, fixed: true },
  },
  {
    path: '/insights',
    name: 'Insights',
    component: () => import('@/pages/Insights.vue'),
    meta: { section: 'insights', title: 'Overview', admin: true },
  },
  {
    path: '/audit',
    name: 'AuditLog',
    component: () => import('@/pages/AuditLog.vue'),
    meta: { section: 'audit', title: 'Audit log', systemManager: true, fixed: true },
  },
  {
    path: '/open',
    name: 'OpenRecord',
    component: () => import('@/pages/OpenRecord.vue'),
    meta: { section: 'inbox', title: 'Open chat', fixed: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/NotFound.vue'),
    meta: { title: 'Page not found' },
  },
]

const router = createRouter({
  history: createWebHistory('/onechat'),
  routes,
})

router.beforeEach((to) => {
  if (embedded && to.meta.section !== 'inbox') return { name: 'Inbox' }
  const section = SECTIONS.find((item) => item.key === to.meta.section)
  if (section?.doctype && session.user.can_read?.[section.doctype] === false) {
    const fallback = SECTIONS.find(
      (item) => item.route && (!item.doctype || session.user.can_read?.[item.doctype] !== false) && !item.admin,
    )
    if (fallback && fallback.key !== section.key) return fallback.route
  }
  if (to.meta.admin && !session.user.is_admin) return { name: 'Inbox' }
  if (to.meta.systemManager && !session.user.is_system_manager) return { name: 'Inbox' }
})

export default router

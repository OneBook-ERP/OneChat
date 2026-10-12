const CHAT_ICON = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>`
const EXTERNAL_ICON = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>`
const CLOSE_ICON = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`

const BASE = '/onechat'

const config = () => frappe.boot.onechat

let $panel = null
let frame = null
let loaded = false

function badge(count) {
  $('.onechat-launcher-count')
    .text(count > 99 ? '99+' : count)
    .toggle(count > 0)
  $('.onechat-launcher').attr('title', count ? __('OneChat · {0} unread', [count]) : __('OneChat'))
}

function refresh() {
  frappe
    .xcall('onechat.inbox.conversations.counts')
    .then((counts) => badge(counts?.unread || 0))
    .catch(() => {})
}

const refreshSoon = frappe.utils.debounce(refresh, 800)

function currentPath() {
  try {
    const { pathname, search } = frame.contentWindow.location
    return pathname.startsWith(BASE) ? pathname.slice(BASE.length) + search : '/inbox'
  } catch {
    return '/inbox'
  }
}

function buildPanel() {
  $panel = $(`
    <aside class="onechat-panel" role="dialog" aria-label="${__('OneChat')}">
      <header class="onechat-panel-head">
        <span class="onechat-panel-title">${CHAT_ICON}<span>${__('OneChat')}</span></span>
        <span class="onechat-panel-actions">
          <button type="button" class="onechat-panel-button" data-action="expand" title="${__('Open full app')}">${EXTERNAL_ICON}</button>
          <button type="button" class="onechat-panel-button" data-action="close" title="${__('Close')}">${CLOSE_ICON}</button>
        </span>
      </header>
      <iframe class="onechat-panel-frame" title="${__('OneChat inbox')}"></iframe>
    </aside>
  `).appendTo(document.body)

  frame = $panel.find('iframe')[0]
  $panel.on('click', '[data-action="close"]', closePanel)
  $panel.on('click', '[data-action="expand"]', () => window.open(BASE + currentPath(), '_blank'))
}

function openPanel(path = '/inbox') {
  if (!$panel) buildPanel()

  if (!loaded) {
    frame.src = BASE + path
    loaded = true
  } else if (path !== '/inbox') {
    frame.contentWindow.postMessage({ type: 'onechat:open', path }, window.location.origin)
  }

  $panel.addClass('is-open')
  $('.onechat-launcher').addClass('is-active')
  $('.onechat-notice').addClass('is-hidden')
}

function closePanel() {
  $panel?.removeClass('is-open')
  $('.onechat-launcher').removeClass('is-active')
  $('.onechat-notice').removeClass('is-hidden')
}

function togglePanel() {
  $panel?.hasClass('is-open') ? closePanel() : openPanel()
}

function mountLauncher() {
  if ($('.onechat-launcher').length) return

  const $nav = $('.navbar .navbar-collapse .navbar-nav').first()
  if (!$nav.length) return

  const $item = $(`
    <li class="nav-item onechat-launcher-item">
      <button type="button" class="nav-link btn-reset onechat-launcher" title="${__('OneChat')}">
        ${CHAT_ICON}
        <span class="onechat-launcher-count" style="display: none"></span>
      </button>
    </li>
  `)
  const $notifications = $nav.find('.dropdown-notifications').first()
  $notifications.length ? $item.insertBefore($notifications) : $nav.prepend($item)
  $item.on('click', '.onechat-launcher', togglePanel)

  $(document).on('keydown', (event) => {
    if (event.key === 'Escape' && $panel?.hasClass('is-open')) closePanel()
  })

  refresh()
  frappe.realtime.doctype_subscribe?.('OneChat Contact')
  frappe.realtime.on('onechat_inbox', refreshSoon)
}

function openContact(contact) {
  openPanel(`/inbox/${encodeURIComponent(contact)}`)
}

function pickChat(frm, rows) {
  const dialog = new frappe.ui.Dialog({
    title: __('WhatsApp chats for {0}', [frm.docname]),
    fields: [{ fieldtype: 'HTML', fieldname: 'list' }],
  })
  const $list = $('<div class="onechat-chat-list"></div>')
  for (const row of rows) {
    const title = frappe.utils.escape_html(row.contact_name || row.mobile_no || row.name)
    const detail = frappe.utils.escape_html([row.mobile_no, row.last_message].filter(Boolean).join(' · '))
    $(`
      <button type="button" class="onechat-chat-row">
        <span class="onechat-chat-row-title">${title}${row.main ? ` <span class="onechat-chat-row-main">★ ${__('Main')}</span>` : ''}</span>
        <span class="onechat-chat-row-detail">${detail}</span>
      </button>
    `)
      .on('click', () => {
        dialog.hide()
        openContact(row.name)
      })
      .appendTo($list)
  }
  dialog.fields_dict.list.$wrapper.empty().append($list)
  dialog.show()
}

function openChat(frm) {
  frappe.xcall('onechat.workspace.desk.chats', { doctype: frm.doctype, name: frm.docname }).then((rows) => {
    if (!rows?.length) return
    rows.length === 1 ? openContact(rows[0].name) : pickChat(frm, rows)
  })
}

function chatLabel(count) {
  if (!count) return __('Start WhatsApp chat')
  if (count === 1) return __('Chat on WhatsApp')
  return __('WhatsApp chats ({0})', [count])
}

function addFormButtons() {
  for (const doctype of config().doctypes || []) {
    frappe.ui.form.on(doctype, 'refresh', (frm) => {
      if (frm.is_new()) return
      const $button = frm.add_custom_button(__('Chat on WhatsApp'), () => openChat(frm))
      $button.addClass('onechat-chat-button').attr('title', __('Open the WhatsApp conversation in OneChat'))
      const render = (count) => $button.html(`${CHAT_ICON}<span>${frappe.utils.escape_html(chatLabel(count))}</span>`)
      render(1)
      frappe
        .xcall('onechat.workspace.desk.chat_count', { doctype: frm.doctype, name: frm.docname })
        .then(render)
        .catch(() => {})
    })
  }
}

const payConfig = () => frappe.boot.onechat_payments
const CLOSED_ORDERS = ['Closed', 'Completed', 'Cancelled', 'On Hold']

function dueOf(frm) {
  const doc = frm.doc
  if (frm.doctype === 'Sales Invoice') return flt(doc.outstanding_amount)
  if (CLOSED_ORDERS.includes(doc.status) || flt(doc.per_billed) >= 100) return 0
  return flt(doc.rounded_total || doc.grand_total) - flt(doc.advance_paid)
}

function paymentNote(info, method) {
  const note = (text, tone) => `<p class="onechat-pay-note is-${tone}">${frappe.utils.escape_html(text)}</p>`
  const open = info.open || {}
  let out = ''
  if (method === 'whatsapp') {
    out = info.window
      ? note(__('The customer reviews the order and pays inside WhatsApp.'), 'ok')
      : note(__('The customer has not written in 24 hours, so WhatsApp will not deliver this. Send a payment link instead.'), 'warn')
    if ((open.links || []).length)
      out += note(__('Sending cancels the open payment link {0}, so the customer can only pay once.', [open.links.join(', ')]), 'info')
    return out
  }
  if (!info.gateway) return note(__('No default payment gateway is set up in ERPNext, so the link cannot be created.'), 'warn')
  if (info.window) out = note(__('The customer wrote recently, so they get a message with a Pay button.'), 'ok')
  else if (info.template) out = note(__('The chat is closed, so the link goes out as your payment template.'), 'info')
  else
    out = note(
      __(
        'The chat is closed and no payment template is set. It is sent as a normal message, which WhatsApp may hold until the customer writes back.',
      ),
      'warn',
    )
  if ((open.whatsapp || []).length)
    out += note(__('Sending withdraws the open WhatsApp payment request, so the customer can only pay once.'), 'info')
  return out
}

function blockedFor(info, method) {
  return method === 'whatsapp' ? !info.window : !info.gateway
}

function sendPaymentLink(frm) {
  frappe.xcall('onechat.integrations.payments.desk_link_options', { doctype: frm.doctype, name: frm.docname }).then((info) => {
    const dialog = new frappe.ui.Dialog({
      title: __('Send payment link on WhatsApp'),
      fields: [
        {
          fieldtype: 'Select',
          fieldname: 'method',
          label: __('Send as'),
          options: [
            { label: __('In WhatsApp'), value: 'whatsapp' },
            { label: __('Payment link'), value: 'link' },
          ],
          default: info.whatsapp && info.window ? 'whatsapp' : 'link',
          hidden: !info.whatsapp,
          onchange: () => refresh(),
        },
        { fieldtype: 'HTML', fieldname: 'note' },
        { fieldtype: 'Data', fieldname: 'mobile_no', label: __('WhatsApp number'), options: 'Phone', default: info.mobile_no, reqd: 1 },
        {
          fieldtype: 'Currency',
          fieldname: 'amount',
          label: __('Amount'),
          default: info.due,
          description: __('Up to {0}. Lower it to ask for part of it.', [info.due_label]),
        },
        { fieldtype: 'Small Text', fieldname: 'message', label: __('Message (optional)') },
      ],
      primary_action_label: __('Send'),
      primary_action(values) {
        dialog.disable_primary_action()
        frappe
          .xcall('onechat.integrations.payments.desk_send_link', {
            doctype: frm.doctype,
            name: frm.docname,
            mobile_no: values.mobile_no,
            amount: values.amount,
            message: values.message,
            method: values.method,
          })
          .then((message) => {
            dialog.hide()
            frappe.show_alert({ message, indicator: 'green' })
            frm.reload_doc()
          })
          .finally(() => refresh())
      },
    })
    function refresh() {
      const method = dialog.get_value('method') || 'link'
      dialog.fields_dict.note.$wrapper.html(paymentNote(info, method))
      blockedFor(info, method) ? dialog.disable_primary_action() : dialog.enable_primary_action()
    }
    dialog.show()
    refresh()
  })
}

function addPaymentButtons() {
  for (const doctype of payConfig().doctypes || []) {
    frappe.ui.form.on(doctype, 'refresh', (frm) => {
      if (frm.doc.docstatus !== 1 || dueOf(frm) <= 0) return
      frm.add_custom_button(__('WhatsApp Payment Link'), () => sendPaymentLink(frm), __('Create'))
    })
  }
}

if (payConfig()) addPaymentButtons()

const NOTICE_DISMISSED = () => `onechat-dismissed-announcements:${frappe.session.user}`
const NOTICE_LATER = 'onechat-desk-announcements-later'
const NOTICE_DELAY = 1500
const NOTICE_DOTS = {
  new: 'var(--blue-500)',
  info: 'var(--gray-500)',
  success: 'var(--green-500)',
  warning: 'var(--orange-500)',
  ad: 'var(--gray-500)',
}
const NOTICE_LABELS = { new: 'New', warning: 'Notice', success: 'Update', ad: 'Sponsored' }

function storedList(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || '[]')
  } catch {
    return []
  }
}

function dismissNotice(id) {
  try {
    const rest = storedList(NOTICE_DISMISSED()).filter((value) => value !== id)
    localStorage.setItem(NOTICE_DISMISSED(), JSON.stringify([...rest, id].slice(-200)))
  } catch {
    return
  }
}

function laterThisSession() {
  try {
    return sessionStorage.getItem(NOTICE_LATER) === '1'
  } catch {
    return false
  }
}

function rememberLater() {
  try {
    sessionStorage.setItem(NOTICE_LATER, '1')
  } catch {
    return
  }
}

function safeUrl(value) {
  return /^https?:\/\//i.test(value || '') ? value : null
}

function liveNotice(item, now = Date.now()) {
  if (!item?.id || !(item.title || item.body)) return false
  if (item.starts_at && new Date(item.starts_at).getTime() > now) return false
  if (item.ends_at && new Date(item.ends_at).getTime() < now) return false
  return !(item.dismissible !== false && storedList(NOTICE_DISMISSED()).includes(item.id))
}

function noticeHtml(item, index, total) {
  const escape = frappe.utils.escape_html
  const image = item.type === 'image' ? safeUrl(item.media?.src) : null
  const action = item.action && safeUrl(item.action.url) ? item.action : null
  const label = item.label || __(NOTICE_LABELS[item.theme] || 'Announcement')
  const dot = NOTICE_DOTS[item.theme] || NOTICE_DOTS.info
  const close =
    item.dismissible !== false
      ? `<button type="button" class="onechat-panel-button" data-notice="dismiss" title="${__('Dismiss')}">${CLOSE_ICON}</button>`
      : ''
  const pager =
    total > 1
      ? `<span class="onechat-notice-pager">
          <button type="button" class="onechat-panel-button" data-notice="previous" title="${__('Previous')}">&lsaquo;</button>
          ${__('{0} of {1}', [index + 1, total])}
          <button type="button" class="onechat-panel-button" data-notice="next" title="${__('Next')}">&rsaquo;</button>
        </span>`
      : ''
  return `
    <aside class="onechat-notice" role="status" aria-live="polite">
      ${image ? `<img class="onechat-notice-image" src="${escape(image)}" alt="" loading="lazy">` : ''}
      <div class="onechat-notice-body">
        <div class="onechat-notice-top">
          <div class="onechat-notice-text">
            <p class="onechat-notice-label"><span class="onechat-notice-dot" style="background: ${dot}"></span>${escape(label)}</p>
            ${item.title ? `<p class="onechat-notice-title">${escape(item.title)}</p>` : ''}
            ${item.body ? `<p class="onechat-notice-copy">${escape(item.body)}</p>` : ''}
          </div>
          ${close}
        </div>
        <div class="onechat-notice-actions">
          ${
            action
              ? `<a class="btn btn-primary btn-sm" href="${escape(action.url)}" target="_blank" rel="noopener">${escape(
                  action.label || __('Learn more'),
                )}</a>`
              : ''
          }
          <button type="button" class="btn btn-link btn-sm" data-notice="later">${__('Later')}</button>
          ${pager}
        </div>
      </div>
    </aside>`
}

function showNotices(queue, index = 0) {
  $('.onechat-notice').remove()
  if (!queue.length) return
  const position = (index + queue.length) % queue.length
  const $notice = $(noticeHtml(queue[position], position, queue.length)).appendTo(document.body)
  if ($panel?.hasClass('is-open')) $notice.addClass('is-hidden')
  $notice.on('click', '[data-notice="dismiss"]', () => {
    dismissNotice(queue[position].id)
    showNotices(
      queue.filter((_, place) => place !== position),
      position,
    )
  })
  $notice.on('click', '[data-notice="later"]', () => {
    rememberLater()
    $notice.remove()
  })
  $notice.on('click', '[data-notice="previous"]', () => showNotices(queue, position - 1))
  $notice.on('click', '[data-notice="next"]', () => showNotices(queue, position + 1))
}

function loadNotices() {
  if (laterThisSession()) return
  frappe
    .xcall('onechat.workspace.announcements.announcements')
    .then((items) => showNotices((items || []).filter((item) => liveNotice(item))))
    .catch(() => {})
}

if (config()) {
  addFormButtons()
  $(document).on('app_ready', mountLauncher)
  $(document).on('app_ready', () => setTimeout(loadNotices, NOTICE_DELAY))
}

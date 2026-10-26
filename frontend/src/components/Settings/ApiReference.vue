<template>
  <section class="flex flex-col gap-4">
    <div>
      <p class="text-base font-semibold text-ink-gray-9">{{ __('API reference') }}</p>
      <p class="text-sm text-ink-gray-5">
        {{
          __(
            'Use a Frappe API key and secret, created in the desk under User → Settings → API Access. The key acts as that user, with their role and what they can see.',
          )
        }}
      </p>
    </div>

    <div class="grid gap-2 rounded-4 bg-surface-gray-1 p-3 text-sm text-ink-gray-7 sm:grid-cols-2">
      <p>
        <span class="font-medium text-ink-gray-8">{{ __('Base URL') }}</span> · <code class="font-mono">{{ base }}</code>
      </p>
      <p>
        <span class="font-medium text-ink-gray-8">{{ __('Auth header') }}</span> ·
        <code class="font-mono">Authorization: token KEY:SECRET</code>
      </p>
      <p>
        <span class="font-medium text-ink-gray-8">{{ __('Contacts') }}</span> ·
        {{ contactsHelp }}
      </p>
      <p>
        <span class="font-medium text-ink-gray-8">{{ __('Responses') }}</span> ·
        {{ __('JSON inside "message"; errors return 4xx with "exception"') }}
      </p>
    </div>

    <TabButtons v-model="tab" :options="tabs" />

    <template v-if="tab !== 'events'">
      <details v-for="item in shownEndpoints" :key="item.name" class="rounded-4 border border-outline-gray-2 px-3 py-2">
        <summary class="flex cursor-pointer items-center gap-2 text-sm">
          <Badge :theme="item.method === 'POST' ? 'green' : 'blue'" :label="item.method" />
          <TruncatedText as="code" class="min-w-0 flex-1 truncate font-mono text-ink-gray-8" :text="item.name" />
          <TruncatedText class="hidden truncate text-ink-gray-5 sm:inline" :text="item.title" />
        </summary>
        <div class="mt-3 flex flex-col gap-3">
          <p class="text-sm text-ink-gray-7">{{ item.description }}</p>
          <table v-if="item.params.length" class="w-full text-left text-sm">
            <thead>
              <tr class="text-xs text-ink-gray-5">
                <th class="py-1 pr-3 font-medium">{{ __('Parameter') }}</th>
                <th class="py-1 pr-3 font-medium">{{ __('Required') }}</th>
                <th class="py-1 font-medium">{{ __('Description') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-outline-gray-1">
              <tr v-for="param in item.params" :key="param[0]">
                <td class="py-1.5 pr-3 align-top font-mono text-ink-gray-8">{{ param[0] }}</td>
                <td class="py-1.5 pr-3 align-top text-ink-gray-6">{{ param[1] ? __('Yes') : __('No') }}</td>
                <td class="py-1.5 align-top text-ink-gray-7">{{ param[2] }}</td>
              </tr>
            </tbody>
          </table>
          <CodeBlock :title="__('Example request')" :code="curl(item)" />
          <CodeBlock v-if="item.response" :title="__('Response')" :code="json(item.response)" />
        </div>
      </details>
    </template>

    <template v-else>
      <p class="text-sm text-ink-gray-6">
        {{
          __(
            'Each webhook is a Frappe webhook that POSTs JSON. Check X-Frappe-Webhook-Signature: a base64 HMAC-SHA256 of the raw body with your signing secret. Frappe retries failures and logs every request.',
          )
        }}
      </p>
      <details v-for="item in events" :key="item.event" class="rounded-4 border border-outline-gray-2 px-3 py-2">
        <summary class="flex cursor-pointer items-center gap-2 text-sm">
          <code class="font-mono text-ink-gray-9">{{ item.event }}</code>
          <TruncatedText class="min-w-0 flex-1 truncate text-ink-gray-5" :text="item.description" />
        </summary>
        <CodeBlock class="mt-2" :title="__('Sample payload')" :code="json(sample(item.event))" />
      </details>
      <CodeBlock :title="__('Check the signature')" :code="verifySnippet" />
    </template>
  </section>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, ref } from 'vue'
import { Badge, TabButtons, call } from 'frappe-ui'
import CodeBlock from '@/components/Common/CodeBlock.vue'
import { translate as __ } from '@/translation'

const base = window.location.origin
const contactsHelp = __(
  'a phone number with country code (+919876543210), an Instagram @username, ig:<Instagram ID>, or a OneChat contact ID. Instagram contacts can only be messaged after they write to you.',
)
const PREFIX = '/api/method/onechat.api.v1.'

const CONTACT = {
  id: 'WC-0042',
  name: 'Priya',
  phone: '+91 98765 43210',
  email: 'priya@example.com',
  assigned_to: 'asha@example.com',
  status: 'Open',
  labels: ['Hot lead'],
  linked_doctype: 'Customer',
  linked_name: 'CUST-0019',
}
const MESSAGE = {
  id: 'MSG-9913',
  direction: 'outgoing',
  type: 'text',
  text: 'Your order has shipped',
  template: null,
  status: 'Queued',
  source: 'Agent',
  created_at: '2026-09-30 10:15:02',
}

const ENDPOINTS = [
  {
    group: 'messages',
    name: 'send_message',
    method: 'POST',
    title: __('Send a text message'),
    description: __('Sends text inside the 24-hour customer service window. Creates the contact if it does not exist.'),
    params: [
      ['to', true, __('Phone number, @username or contact ID')],
      ['text', true, __('Message text; WhatsApp formatting like *bold* works')],
      ['name', false, __('Contact name, used when a new contact is created')],
    ],
    body: { to: '+919876543210', text: 'Your order has shipped' },
    response: { contact: CONTACT, message: MESSAGE },
  },
  {
    group: 'messages',
    name: 'send_template',
    method: 'POST',
    title: __('Send a template'),
    description: __('Starts or re-opens a conversation with an approved template. Parameters fill the template variables in order.'),
    params: [
      ['to', true, __('Phone number, @username or contact ID')],
      ['template', true, __('Template name, as returned by list_templates')],
      ['parameters', false, __('List of values for the variables')],
      ['name', false, __('Contact name for a new contact')],
    ],
    body: { to: '+919876543210', template: 'order_update', parameters: ['Priya', 'SO-1042'] },
    response: { contact: CONTACT, message: { ...MESSAGE, type: 'text', template: 'order_update' } },
  },
  {
    group: 'messages',
    name: 'send_media',
    method: 'POST',
    title: __('Send an image, video, audio or document'),
    description: __('Sends a file from a public URL inside the 24-hour window.'),
    params: [
      ['to', true, __('Phone number, @username or contact ID')],
      ['url', true, __('Public link to the file')],
      ['type', false, __('image (default), video, audio or document')],
      ['caption', false, __('Text shown under the file')],
    ],
    body: { to: '+919876543210', url: 'https://example.com/catalog.pdf', type: 'document', caption: 'Our new catalog' },
    response: { contact: CONTACT, message: { ...MESSAGE, type: 'document', text: 'Our new catalog' } },
  },
  {
    group: 'messages',
    name: 'get_messages',
    method: 'GET',
    title: __('Recent messages'),
    description: __('The latest messages with a contact, newest first.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['limit', false, __('Up to 100, default 20')],
    ],
    body: { phone: '+919876543210', limit: 20 },
    response: { contact: CONTACT, messages: [{ ...MESSAGE, direction: 'incoming', text: 'Is the sofa in stock?', status: 'received' }] },
  },
  {
    group: 'conversations',
    name: 'list_conversations',
    method: 'GET',
    title: __('List conversations'),
    description: __('Conversations the key can see, most recent first.'),
    params: [
      ['status', false, __('open, pending or resolved')],
      ['assigned_to', false, __('A user email, "me" or "none"')],
      ['label', false, __('Only conversations with this label')],
      ['unread', false, __('1 for unread only')],
      ['search', false, __('Name, number, email or @username')],
      ['channel', false, __('whatsapp or instagram')],
      ['start', false, __('Offset for paging')],
      ['limit', false, __('Up to 100, default 20')],
    ],
    body: { status: 'open', assigned_to: 'me', limit: 20 },
    response: [{ ...CONTACT, unread: 2, last_message: 'Is the sofa in stock?', last_message_at: '2026-09-30 10:12:44' }],
  },
  {
    group: 'conversations',
    name: 'assign',
    method: 'POST',
    title: __('Assign a conversation'),
    description: __('Assign to a person, or to the next available agent in a team. Send neither to unassign.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['user', false, __('User email')],
      ['team', false, __('Team name; picks the next available agent')],
    ],
    body: { phone: '+919876543210', team: 'Sales' },
    response: CONTACT,
  },
  {
    group: 'conversations',
    name: 'set_status',
    method: 'POST',
    title: __('Change status'),
    description: __('Mark a conversation open, pending or resolved.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['status', true, __('open, pending or resolved')],
      ['reason', false, __('Why it was resolved, required when Inbox rules ask for a reason')],
      ['note', false, __('Optional note saved with the resolution')],
    ],
    body: { phone: '+919876543210', status: 'resolved' },
    response: { ...CONTACT, status: 'Resolved' },
  },
  {
    group: 'conversations',
    name: 'add_labels',
    method: 'POST',
    title: __('Add labels'),
    description: __('Adds labels that already exist in OneChat. Existing labels are kept.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['labels', true, __('List of label names, or comma separated')],
    ],
    body: { phone: '+919876543210', labels: ['Hot lead', 'Website'] },
    response: { ...CONTACT, labels: ['Hot lead', 'Website'] },
  },
  {
    group: 'conversations',
    name: 'remove_labels',
    method: 'POST',
    title: __('Remove labels'),
    description: __('Removes the given labels and keeps the rest.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['labels', true, __('List of label names, or comma separated')],
    ],
    body: { phone: '+919876543210', labels: ['Website'] },
    response: CONTACT,
  },
  {
    group: 'conversations',
    name: 'add_note',
    method: 'POST',
    title: __('Add an internal note'),
    description: __('Only the team sees notes. Mention teammates with @Name.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['text', true, __('Note text')],
    ],
    body: { phone: '+919876543210', text: 'Called back, wants delivery on Friday' },
    response: { contact: 'WC-0042', note: { id: 'NOTE-0103', text: 'Called back, wants delivery on Friday' } },
  },
  {
    group: 'contacts',
    name: 'get_contact',
    method: 'GET',
    title: __('Look up a contact'),
    description: __('Who it is assigned to, its status, labels and linked record.'),
    params: [['phone', true, __('Phone number, @username or contact ID')]],
    body: { phone: '+919876543210' },
    response: CONTACT,
  },
  {
    group: 'contacts',
    name: 'create_contact',
    method: 'POST',
    title: __('Create a contact'),
    description: __('Fails if a contact with the number already exists.'),
    params: [
      ['phone', true, __('Phone number')],
      ['name', false, __('Full name')],
      ['email', false, __('Email')],
      ['labels', false, __('Labels to add')],
    ],
    body: { phone: '+919876543210', name: 'Priya', email: 'priya@example.com', labels: ['Website'] },
    response: CONTACT,
  },
  {
    group: 'contacts',
    name: 'update_contact',
    method: 'POST',
    title: __('Update a contact'),
    description: __('Change the name or email. Fields you leave out stay the same.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['name', false, __('Full name')],
      ['email', false, __('Email')],
    ],
    body: { phone: '+919876543210', name: 'Priya Raman' },
    response: { ...CONTACT, name: 'Priya Raman' },
  },
  {
    group: 'contacts',
    name: 'set_opt_out',
    method: 'POST',
    title: __('Marketing consent'),
    description: __('Stop or allow marketing templates and broadcasts for a contact. Admin keys only.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['opted_out', false, __('1 to stop (default), 0 to allow')],
    ],
    body: { phone: '+919876543210', opted_out: 1 },
    response: CONTACT,
  },
  {
    group: 'automation',
    name: 'list_templates',
    method: 'GET',
    title: __('List templates'),
    description: __('Templates you can send, with their variables.'),
    params: [['status', false, __('APPROVED (default), PENDING, REJECTED, or empty for all')]],
    body: {},
    response: [
      {
        name: 'order_update',
        template: 'order_update',
        language: 'en',
        category: 'UTILITY',
        status: 'APPROVED',
        body: 'Hi {{1}}, order {{2}} has shipped.',
        variables: ['customer_name', 'order'],
      },
    ],
  },
  {
    group: 'automation',
    name: 'start_flow',
    method: 'POST',
    title: __('Start a flow'),
    description: __('Runs a chatbot flow for a contact. Inside the flow, each variable is available as vars followed by its name.'),
    params: [
      ['phone', true, __('Phone number, @username or contact ID')],
      ['flow', true, __('Flow name')],
      ['variables', false, __('Object of values for the flow')],
    ],
    body: { phone: '+919876543210', flow: 'Order follow-up', variables: { order: 'SO-1042' } },
    response: { contact: 'WC-0042', flow: 'Order follow-up', status: 'Waiting', run: 'RUN-00881' },
  },
]

const SAMPLES = {
  contact: { ...CONTACT, opted_out: 0, unread: 1, last_message_at: '2026-09-30 10:12:44' },
  message: {
    id: 'MSG-9913',
    contact: 'WC-0042',
    direction: 'incoming',
    from: '919876543210',
    to: null,
    type: 'text',
    text: 'Is the sofa in stock?',
    template: null,
    status: 'received',
    source: null,
    created_at: '2026-09-30 10:12:44',
  },
}

const tab = ref('messages')
const events = ref([])

const tabs = [
  { label: __('Messages'), value: 'messages' },
  { label: __('Conversations'), value: 'conversations' },
  { label: __('Contacts'), value: 'contacts' },
  { label: __('Templates & flows'), value: 'automation' },
  { label: __('Webhook events'), value: 'events' },
]

const shownEndpoints = computed(() => ENDPOINTS.filter((item) => item.group === tab.value))

function json(value) {
  return JSON.stringify(value, null, 2)
}

function curl(item) {
  const url = `${base}${PREFIX}${item.name}`
  const auth = '-H "Authorization: token KEY:SECRET"'
  if (item.method === 'GET') {
    const query = Object.entries(item.body)
      .map(([key, value]) => `  --data-urlencode ${key}=${value}`)
      .join(' \\\n')
    return `curl -G ${url} \\\n  ${auth}${query ? ` \\\n${query}` : ''}`
  }
  return `curl -X POST ${url} \\\n  ${auth} \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(item.body)}'`
}

function sample(event) {
  if (event.startsWith('message.') || event === 'form.submitted') {
    const message = { ...SAMPLES.message }
    if (event === 'message.sent' || event === 'message.status')
      Object.assign(message, {
        direction: 'outgoing',
        from: null,
        to: '919876543210',
        status: event === 'message.status' ? 'read' : 'Queued',
        source: 'Agent',
      })
    if (event === 'form.submitted')
      Object.assign(message, { type: 'flow', form: 'Lead form', answers: '{"name": "Priya", "budget": "50000"}' })
    return { event, message }
  }
  if (event === 'chat.created')
    return {
      event,
      conversation: { id: 'CONV-2231', contact: 'WC-0042', assigned_to: null, team: 'Sales', opened_at: '2026-09-30 10:12:44' },
    }
  if (event === 'note.added')
    return {
      event,
      note: {
        id: 'NOTE-0103',
        contact: 'WC-0042',
        text: 'Wants delivery on Friday',
        author: 'asha@example.com',
        created_at: '2026-09-30 11:02:10',
      },
    }
  if (event === 'flow.finished')
    return {
      event,
      run: {
        id: 'RUN-00881',
        flow: 'Order follow-up',
        status: 'Success',
        contact: 'WC-0042',
        error: null,
        started_at: '2026-09-30 10:00:01',
        ended_at: '2026-09-30 10:04:12',
      },
    }
  if (event === 'broadcast.completed')
    return {
      event,
      broadcast: {
        id: 'BULK-WA-2026-00012',
        title: 'October offer',
        template: 'offer_a',
        recipients: 1200,
        sent: 1184,
        skipped: 16,
        status: 'Completed',
        ab_winner: 'A',
      },
    }
  return {
    event,
    contact: {
      ...SAMPLES.contact,
      status: event === 'chat.resolved' ? 'Resolved' : 'Open',
      opted_out: event === 'contact.opted_out' ? 1 : 0,
    },
  }
}

const verifySnippet = `# Python
import base64, hashlib, hmac
expected = base64.b64encode(hmac.new(SECRET.encode(), raw_body, hashlib.sha256).digest()).decode()
valid = hmac.compare_digest(expected, request.headers["X-Frappe-Webhook-Signature"])

// Node.js
const expected = crypto.createHmac("sha256", SECRET).update(rawBody).digest("base64")
const valid = crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(req.headers["x-frappe-webhook-signature"]))`

onMounted(async () => {
  try {
    events.value = await call('onechat.workspace.webhooks.catalog')
  } catch {
    events.value = []
  }
})
</script>

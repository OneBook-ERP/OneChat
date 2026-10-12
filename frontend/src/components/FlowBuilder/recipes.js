import { defaultConfig, nodeDef, triggerTypeOf } from './nodeTypes'

function step(id, type, config = {}, label) {
  return {
    id,
    type: 'custom',
    position: { x: 0, y: 0 },
    data: { label: label || nodeDef(type).label, nodeType: type, config: { ...defaultConfig(type), ...config } },
  }
}

function link(source, target, handle = null) {
  return { id: `e-${source}-${target}-${handle || 'next'}`, source, target, sourceHandle: handle, targetHandle: null }
}

function option(id, title, description = '') {
  return { id, title, description }
}

function layout(nodes, edges) {
  const children = {}
  for (const edge of edges) (children[edge.source] ||= []).push(edge.target)

  const depth = { [nodes[0].id]: 0 }
  const queue = [nodes[0].id]
  while (queue.length) {
    const id = queue.shift()
    for (const child of children[id] || []) {
      if (depth[child] === undefined) {
        depth[child] = depth[id] + 1
        queue.push(child)
      }
    }
  }

  const rows = {}
  for (const node of nodes) (rows[depth[node.id] ?? 0] ||= []).push(node)
  for (const [level, row] of Object.entries(rows)) {
    row.forEach((node, index) => {
      node.position = { x: Math.round((index - (row.length - 1) / 2) * 320), y: Number(level) * 230 }
    })
  }

  return { nodes, edges }
}

function flow(graph) {
  return { ...graph, trigger_type: triggerTypeOf(graph.nodes) }
}

export const RECIPES = [
  {
    key: 'comment_to_dm',
    title: 'Comment keyword to DM',
    description: 'When someone comments a keyword on your Instagram post, DM them the details and reply publicly.',
    icon: 'lucide-message-square-text',
    category: 'Sales',
    build: () => {
      const nodes = [
        step('start', 'comment_received', {
          match: 'keywords',
          keywords: [{ value: 'price' }, { value: 'details' }, { value: 'link' }],
          public_replies: [{ value: 'Sent you a DM 💬' }, { value: 'Check your DMs!' }, { value: 'Details sent to your inbox 📩' }],
          once_per_person: true,
        }),
        step('details', 'send_buttons', {
          text: 'Hi {{first_name}} 👋 Thanks for your comment! Here are the details. What would you like next?',
          buttons: [option('price', 'Price list'), option('human', 'Talk to us')],
          save_as: 'choice',
        }),
        step('price', 'send_message', {
          text: 'Here is our price list:\n\n• Product one\n• Product two\n\nReply with a product name to know more.',
        }),
        step('handover', 'handover', { text: 'Connecting you to our team, someone will reply shortly.', mode: 'round_robin' }),
      ]
      const edges = [link('start', 'details'), link('details', 'price', 'price'), link('details', 'handover', 'human')]
      return flow(layout(nodes, edges))
    },
  },
  {
    key: 'welcome_menu',
    title: 'Welcome menu',
    description: 'Greet new customers with buttons for products, order status and talking to a person.',
    icon: 'lucide-hand-heart',
    category: 'Customer Service',
    build: () => {
      const nodes = [
        step('start', 'message_received', { match: 'first' }),
        step('menu', 'send_buttons', {
          text: 'Hi {{first_name}} 👋 Thanks for messaging us! How can we help you today?',
          buttons: [option('products', 'Browse products'), option('order', 'Order status'), option('human', 'Talk to us')],
          save_as: 'topic',
        }),
        step('catalog', 'send_message', {
          text: 'Here is what we offer:\n\n• Product one\n• Product two\n\nReply with the product name to know more.',
        }),
        step('ask_order', 'ask_question', { text: 'Please send your order number.', save_as: 'order_no' }),
        step('find_order', 'find_record', { doctype: 'Sales Order', field: 'name', value: '{{answers.order_no}}', save_as: 'order' }),
        step('order_found', 'send_message', {
          text: 'Order *{{records.order.name}}* is {{records.order.status}}.\nExpected delivery: {{records.order.delivery_date}}',
        }),
        step('order_missing', 'send_message', { text: 'Sorry, we could not find that order. Let us connect you to our team.' }),
        step('handover', 'handover', { text: 'Connecting you to our team, someone will reply shortly.', mode: 'round_robin' }),
      ]
      const edges = [
        link('start', 'menu'),
        link('menu', 'catalog', 'products'),
        link('menu', 'ask_order', 'order'),
        link('menu', 'handover', 'human'),
        link('ask_order', 'find_order', 'answered'),
        link('find_order', 'order_found', 'found'),
        link('find_order', 'order_missing', 'not_found'),
        link('order_missing', 'handover'),
      ]
      return flow(layout(nodes, edges))
    },
  },
  {
    key: 'faq_menu',
    title: 'FAQ menu',
    description: 'Answer common questions from a list menu when customers type "menu" or "help".',
    icon: 'lucide-circle-help',
    category: 'Support',
    build: () => {
      const nodes = [
        step('start', 'message_received', { match: 'keywords', keywords: [{ value: 'menu' }, { value: 'help' }, { value: 'faq' }] }),
        step('menu', 'send_list', {
          text: 'What would you like to know?',
          button_label: 'See topics',
          rows: [
            option('hours', 'Opening hours'),
            option('delivery', 'Delivery'),
            option('payment', 'Payments'),
            option('returns', 'Returns & refunds'),
            option('human', 'Talk to a person'),
          ],
          save_as: 'topic',
        }),
        step('hours', 'send_message', { text: 'We are open Monday to Saturday, 9 AM to 7 PM.' }),
        step('delivery', 'send_message', { text: 'We deliver in 2 to 4 working days. Delivery is free above ₹999.' }),
        step('payment', 'send_message', { text: 'We accept UPI, cards, net banking and cash on delivery.' }),
        step('returns', 'send_message', { text: 'You can return unused items within 7 days of delivery for a full refund.' }),
        step('human', 'handover', { text: 'Sure, connecting you to our team.', mode: 'round_robin' }),
      ]
      const edges = [
        link('start', 'menu'),
        link('menu', 'hours', 'hours'),
        link('menu', 'delivery', 'delivery'),
        link('menu', 'payment', 'payment'),
        link('menu', 'returns', 'returns'),
        link('menu', 'human', 'human'),
      ]
      return flow(layout(nodes, edges))
    },
  },
  {
    key: 'lead_capture',
    title: 'Capture leads',
    description: 'Ask for name, email and need, create an ERPNext Lead and assign an agent.',
    icon: 'lucide-user-plus',
    category: 'Sales',
    needs: 'ERPNext',
    build: () => {
      const nodes = [
        step('start', 'message_received', {
          match: 'keywords',
          keywords: [{ value: 'quote' }, { value: 'price' }, { value: 'enquiry' }, { value: 'interested' }],
        }),
        step('name', 'ask_question', { text: 'Happy to help! May I know your name?', save_as: 'full_name' }),
        step('email', 'ask_question', {
          text: 'Thanks {{answers.full_name}}! What is your email address?',
          answer_type: 'email',
          save_as: 'email',
          error_text: 'That does not look like an email address, please check and send it again.',
        }),
        step('need', 'ask_question', { text: 'What are you looking for?', save_as: 'requirement' }),
        step('lead', 'create_record', {
          doctype: 'Lead',
          fields: { lead_name: '{{answers.full_name}}', email_id: '{{answers.email}}', mobile_no: '{{phone}}' },
          save_as: 'lead',
        }),
        step('note', 'add_note', { text: 'New lead {{records.lead.name}}: {{answers.requirement}}' }),
        step('thanks', 'send_message', { text: 'Thanks {{answers.full_name}}! Our team will get back to you shortly.' }),
        step('assign', 'assign_agent', { mode: 'round_robin' }),
      ]
      const edges = [
        link('start', 'name'),
        link('name', 'email', 'answered'),
        link('email', 'need', 'answered'),
        link('need', 'lead', 'answered'),
        link('lead', 'note'),
        link('note', 'thanks'),
        link('thanks', 'assign'),
      ]
      return flow(layout(nodes, edges))
    },
  },
  {
    key: 'order_status',
    title: 'Order status',
    description: 'Look up a Sales Order when a customer asks to track their order.',
    icon: 'lucide-package-search',
    category: 'Customer Service',
    needs: 'ERPNext',
    build: () => {
      const nodes = [
        step('start', 'message_received', { match: 'keywords', keywords: [{ value: 'order' }, { value: 'track' }, { value: 'status' }] }),
        step('ask', 'ask_question', { text: 'Please send your order number, for example SAL-ORD-2026-00012.', save_as: 'order_no' }),
        step('find', 'find_record', { doctype: 'Sales Order', field: 'name', value: '{{answers.order_no}}', save_as: 'order' }),
        step('found', 'send_message', {
          text: 'Order *{{records.order.name}}*\nStatus: {{records.order.status}}\nDelivery: {{records.order.delivery_date}}\nTotal: {{records.order.grand_total}}',
        }),
        step('missing', 'send_buttons', {
          text: 'We could not find order {{answers.order_no}}.',
          buttons: [option('retry', 'Try again'), option('human', 'Talk to us')],
        }),
        step('human', 'handover', { text: 'Connecting you to our team.', mode: 'round_robin' }),
      ]
      const edges = [
        link('start', 'ask'),
        link('ask', 'find', 'answered'),
        link('find', 'found', 'found'),
        link('find', 'missing', 'not_found'),
        link('missing', 'ask', 'retry'),
        link('missing', 'human', 'human'),
      ]
      return flow(layout(nodes, edges))
    },
  },
  {
    key: 'payment_reminder',
    title: 'Payment reminders',
    description: 'Every morning, send a reminder template to customers with overdue invoices.',
    icon: 'lucide-receipt',
    category: 'Notifications',
    needs: 'ERPNext',
    build: () => {
      const nodes = [
        step('start', 'scheduled_trigger', { frequency: 'daily', time: '10:00' }),
        step('send', 'send_to_records', {
          doctype: 'Sales Invoice',
          filters: { status: 'Overdue' },
          phone_field: 'contact_mobile',
          parameters: ['{{record.customer_name}}', '{{record.name}}', '{{record.outstanding_amount}}'],
        }),
      ]
      return flow(layout(nodes, [link('start', 'send')]))
    },
  },
  {
    key: 'order_confirmation',
    title: 'Order confirmation',
    description: 'Send a confirmation template when a Sales Order is submitted.',
    icon: 'lucide-badge-check',
    category: 'Notifications',
    needs: 'ERPNext',
    build: () => {
      const nodes = [
        step('start', 'doc_event_trigger', { doctype: 'Sales Order', event: 'on_submit', phone_field: 'contact_mobile' }),
        step('send', 'send_template', { parameters: ['{{doc.customer_name}}', '{{doc.name}}', '{{doc.grand_total}}'] }),
      ]
      return flow(layout(nodes, [link('start', 'send')]))
    },
  },
  {
    key: 'feedback',
    title: 'Ask for feedback',
    description: 'Agents start it after helping someone. Unhappy answers go back to the team.',
    icon: 'lucide-smile',
    category: 'Customer Service',
    build: () => {
      const nodes = [
        step('start', 'manual_trigger'),
        step('rate', 'send_buttons', {
          text: 'How was your experience with us today?',
          buttons: [option('great', 'Great 😀'), option('okay', 'Okay 🙂'), option('bad', 'Not good 😞')],
          save_as: 'rating',
        }),
        step('thanks', 'send_message', { text: 'Thank you for the feedback, {{first_name}}! 🙏' }),
        step('resolve', 'set_status', { status: 'Resolved' }),
        step('why', 'ask_question', { text: 'Sorry to hear that. What went wrong?', save_as: 'feedback' }),
        step('note', 'add_note', { text: 'Unhappy customer: {{answers.feedback}}' }),
        step('handover', 'handover', { text: 'Thanks for telling us. Someone from our team will reach out.' }),
      ]
      const edges = [
        link('start', 'rate'),
        link('rate', 'thanks', 'great'),
        link('rate', 'thanks', 'okay'),
        link('thanks', 'resolve'),
        link('rate', 'why', 'bad'),
        link('why', 'note', 'answered'),
        link('note', 'handover'),
      ]
      return flow(layout(nodes, edges))
    },
  },
]

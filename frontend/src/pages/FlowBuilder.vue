<template>
  <template v-if="compact">
    <AppHeader :title="flow.flow_name || __('Flow builder')" :back="{ name: 'Flows' }" />
    <div class="px-3 pb-10 pt-5">
      <EmptyState
        icon="lucide-monitor-smartphone"
        :title="__('Open on a larger screen to edit flows')"
        :description="__('The flow builder needs room for the canvas. Open OneChat on a laptop or desktop to edit this flow.')"
      >
        <Button variant="subtle" icon-left="lucide-arrow-left" :label="__('Back to flows')" @click="router.push({ name: 'Flows' })" />
      </EmptyState>
    </div>
  </template>

  <div v-else class="flex min-h-0 flex-1 flex-col bg-surface-base">
    <header class="flex h-12 shrink-0 items-center gap-2 border-b border-outline-gray-2 px-3">
      <Tooltip :text="__('Back to flows')">
        <Button variant="ghost" icon="lucide-arrow-left" :label="__('Back to flows')" @click="router.push({ name: 'Flows' })" />
      </Tooltip>
      <FormControl
        type="text"
        v-model="flow.flow_name"
        variant="ghost"
        class="w-64 text-base font-medium"
        :placeholder="__('Flow name')"
        @update:model-value="markDirty"
      />
      <Badge v-if="dirty" :label="__('Unsaved')" theme="amber" />
      <Tooltip v-if="flow.name && flow.is_active" :text="liveTooltip">
        <Badge
          :label="
            hasDraft ? __('Draft · not live') : flow.published_version ? __('Live · v{0}').format(flow.published_version) : __('Live')
          "
          :theme="hasDraft ? 'orange' : 'green'"
          variant="subtle"
        />
      </Tooltip>

      <div class="flex-1" />

      <Switch
        :model-value="!!flow.is_active"
        :label="__('Active')"
        @update:model-value="(value) => changeFlow({ is_active: value ? 1 : 0 })"
      />
      <div class="mx-1 h-5 w-px bg-surface-gray-4" />
      <Dropdown :options="statsMenu" align="end">
        <Button
          :variant="statsDays ? 'solid' : 'subtle'"
          icon-left="lucide-chart-no-axes-column"
          :loading="statsLoading"
          :label="statsDays ? __('Stats · {0}d').format(statsDays) : __('Stats')"
          :disabled="!flow.name"
        />
      </Dropdown>
      <Button variant="subtle" icon-left="lucide-shield-check" :loading="validating" :label="__('Check')" @click="validate" />
      <Button :variant="testing ? 'solid' : 'subtle'" icon-left="lucide-smartphone" :label="__('Test chat')" @click="toggleTestChat" />
      <template v-if="flow.name && savedActive && flow.is_active">
        <Button variant="subtle" icon-left="lucide-save" :loading="saving && !publishing" :label="__('Save draft')" @click="save()" />
        <Button
          variant="solid"
          icon-left="lucide-rocket"
          :loading="publishing"
          :disabled="!hasDraft && !dirty"
          :label="__('Publish')"
          @click="publish"
        />
      </template>
      <Button
        v-else
        variant="solid"
        icon-left="lucide-save"
        :loading="saving"
        :label="flow.is_active && !savedActive ? __('Save & turn on') : __('Save')"
        @click="save()"
      />
      <Dropdown :options="moreMenu" align="end">
        <Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" />
      </Dropdown>
    </header>

    <div class="flex min-h-0 flex-1">
      <NodeLibrary
        :channel="triggerNode?.data?.nodeType === 'comment_received' ? 'Instagram' : triggerNode?.data?.config?.channel || 'WhatsApp'"
        @add="addStep"
      />

      <div ref="canvas" class="relative min-w-0 flex-1" @dragover.prevent="onDragOver" @drop.prevent="onDrop">
        <VueFlow
          :id="FLOW_ID"
          class="onechat-flow"
          :default-edge-options="EDGE_DEFAULTS"
          :snap-to-grid="true"
          :snap-grid="[16, 16]"
          :delete-key-code="['Backspace', 'Delete']"
          :is-valid-connection="isValidConnection"
          :min-zoom="0.2"
          :max-zoom="2"
          @connect="onConnect"
          @node-click="({ node }) => select('node', node.id)"
          @edge-click="({ edge }) => select('edge', edge.id)"
          @pane-click="clearSelection"
          @nodes-change="onNodesChange"
          @edges-change="onEdgesChange"
        >
          <template #node-custom="nodeProps">
            <FlowNode
              :id="nodeProps.id"
              :data="nodeProps.data"
              :selected="nodeProps.selected"
              :status="statuses[nodeProps.id] || ''"
              :stats="nodeStats[nodeProps.id] || null"
            />
          </template>

          <Background :gap="16" :size="1.2" />
          <Controls position="bottom-left" />
          <MiniMap v-if="showMinimap" pannable zoomable position="bottom-right" :node-class-name="miniClass" />
        </VueFlow>

        <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-surface-base">
          <LoadingIndicator class="size-6 text-ink-gray-5" />
        </div>

        <div v-else-if="loadError" class="absolute inset-0 flex items-center justify-center bg-surface-base p-6">
          <EmptyState icon="lucide-circle-alert" :title="__('This flow could not be opened')" :description="loadError">
            <Button variant="subtle" :label="__('Back to flows')" @click="router.push({ name: 'Flows' })" />
          </EmptyState>
        </div>

        <div v-else-if="!nodes.length" class="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
          <div class="pointer-events-auto w-full max-w-md rounded-7 border border-outline-gray-2 bg-surface-elevation-1 p-5 shadow-sm">
            <p class="text-base font-medium text-ink-gray-8">{{ __('When should this flow start?') }}</p>
            <p class="mt-1 text-sm text-ink-gray-5">{{ __('Pick a trigger, then add steps below it. Use Test chat to try it out.') }}</p>
            <div class="mt-4 grid grid-cols-2 gap-2">
              <button
                v-for="item in triggerTypes"
                :key="item.type"
                type="button"
                class="flex items-center gap-2 rounded-4 border border-outline-gray-2 px-2.5 py-2 text-left hover:bg-surface-gray-2"
                @click="addStep(item.type)"
              >
                <span class="flex size-7 shrink-0 items-center justify-center rounded-4" :class="COLORS[item.color].chip">
                  <span :class="item.icon" class="size-3.5" aria-hidden="true" />
                </span>
                <TruncatedText class="truncate text-sm text-ink-gray-8" :text="__(item.label)" />
              </button>
            </div>
            <Button
              v-if="!flow.name"
              class="mt-3 w-full"
              variant="subtle"
              icon-left="lucide-sparkles"
              :label="__('Or start from a recipe')"
              @click="recipesOpen = true"
            />
          </div>
        </div>

        <div
          v-if="lastRun"
          class="absolute left-3 top-3 flex items-center gap-2 rounded-4 border border-outline-gray-2 bg-surface-elevation-1 py-1 pl-2.5 pr-1 shadow-sm"
        >
          <span class="text-sm text-ink-gray-6">{{ __('Last test') }}</span>
          <RunStatusBadge :status="lastRun.status" />
          <span v-if="lastRun.duration" class="text-sm text-ink-gray-5">{{ formatDuration(lastRun.duration) }}</span>
          <Button size="sm" variant="ghost" :label="__('Details')" @click="runDetail = true" />
          <Button size="sm" variant="ghost" icon="lucide-x" :label="__('Clear')" @click="clearRun" />
        </div>
      </div>

      <aside class="shrink-0 border-l border-outline-gray-2 bg-surface-base" :class="testing ? 'w-96' : 'w-80'">
        <TestChat v-if="testing" :graph="graph" @close="closeTestChat" @path="showPath" />
        <NodeInspector
          v-else-if="selectedNode"
          :key="selectedNode.id"
          :node="selectedNode"
          @change="(patch) => changeNode(selectedNode.id, patch)"
          @close="clearSelection"
          @duplicate="duplicateNode(selectedNode)"
          @delete="deleteNode(selectedNode.id)"
        />
        <EdgeInspector
          v-else-if="selectedEdge"
          :key="selectedEdge.id"
          :edge="selectedEdge"
          :source="findNode(selectedEdge.source)"
          :target="findNode(selectedEdge.target)"
          @change="(patch) => changeEdge(selectedEdge.id, patch)"
          @close="clearSelection"
          @delete="deleteEdge(selectedEdge.id)"
        />
        <FlowSettings v-else :flow="flow" :step-count="nodes.length" :edge-count="edges.length" @change="changeFlow" />
      </aside>
    </div>

    <RecipeGallery v-model:open="recipesOpen" @pick="useRecipe" />
    <ValidateDialog v-model:open="validateOpen" :issues="issues" @select="(id) => select('node', id, true)" />
    <TestRunDialog v-model:open="testOpen" :trigger="triggerNode" :running="running" @run="runTest" />
    <ExecutionLogDetail v-model:open="runDetail" :name="lastRun?.name || null" :show-open-flow="false" />
    <VersionHistory
      v-model:open="historyOpen"
      :flow="flow.name"
      :current="flow.published_version || 0"
      :unsaved="dirty || hasDraft"
      @restored="load(flow.name)"
    />
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { MarkerType, VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { Badge, Button, Dropdown, FormControl, LoadingIndicator, Switch, Tooltip, call, toast } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import ExecutionLogDetail from '@/components/Automation/ExecutionLogDetail.vue'
import RunStatusBadge from '@/components/Automation/RunStatusBadge.vue'
import EdgeInspector from '@/components/FlowBuilder/EdgeInspector.vue'
import FlowNode from '@/components/FlowBuilder/FlowNode.vue'
import FlowSettings from '@/components/FlowBuilder/FlowSettings.vue'
import NodeInspector from '@/components/FlowBuilder/NodeInspector.vue'
import NodeLibrary from '@/components/FlowBuilder/NodeLibrary.vue'
import RecipeGallery from '@/components/FlowBuilder/RecipeGallery.vue'
import TestChat from '@/components/FlowBuilder/TestChat.vue'
import TestRunDialog from '@/components/FlowBuilder/TestRunDialog.vue'
import ValidateDialog from '@/components/FlowBuilder/ValidateDialog.vue'
import VersionHistory from '@/components/FlowBuilder/VersionHistory.vue'
import { NO_VALUE_TYPES, doctypeFields, formatDuration } from '@/components/FlowBuilder/api'
import {
  COLORS,
  NODE_TYPES,
  colorOf,
  edgeLabel,
  guessCategory,
  isTrigger,
  makeNode,
  missingFields,
  nodeDef,
  outputsOf,
  readGraph,
  triggerTypeOf,
  writeGraph,
} from '@/components/FlowBuilder/nodeTypes'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  compact: { type: Boolean, default: false },
})

const FLOW_ID = 'onechat-flow-builder'
const EDGE_DEFAULTS = { type: 'smoothstep', markerEnd: MarkerType.ArrowClosed }

const route = useRoute()
const router = useRouter()
const ui = useUI()

const {
  nodes,
  edges,
  addNodes,
  addEdges,
  removeNodes,
  removeEdges,
  setNodes,
  setEdges,
  findNode,
  findEdge,
  updateNodeData,
  updateEdgeData,
  fitView,
  screenToFlowCoordinate,
  addSelectedNodes,
  removeSelectedElements,
  onNodesInitialized,
} = useVueFlow(FLOW_ID)

const canvas = ref(null)
const FAILURE_DEFAULTS = {
  error_message: 'Sorry, something went wrong on our side. A teammate will reply to you shortly.',
  error_handover: 1,
  error_team: '',
  error_notify: 1,
  error_pause: 0,
}

function failureOf(doc = {}) {
  return {
    error_message: doc.error_message ?? FAILURE_DEFAULTS.error_message,
    error_handover: doc.error_handover ?? FAILURE_DEFAULTS.error_handover,
    error_team: doc.error_team || '',
    error_notify: doc.error_notify ?? FAILURE_DEFAULTS.error_notify,
    error_pause: doc.error_pause ?? FAILURE_DEFAULTS.error_pause,
  }
}

const flow = ref(blankFlow())
const dirty = ref(false)
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const validating = ref(false)
const running = ref(false)
const showMinimap = ref(true)
const selection = ref(null)
const issues = ref([])
const validateOpen = ref(false)
const testOpen = ref(false)
const runDetail = ref(false)
const statuses = ref({})
const lastRun = ref(null)
const hasDraft = ref(false)
const savedActive = ref(false)
const publishing = ref(false)
const historyOpen = ref(false)
const statsDays = ref(0)
const statsLoading = ref(false)
const stats = ref(null)
let hydrating = false
let pendingFit = false
let wasFullScreen = false

const triggerTypes = NODE_TYPES.filter((item) => item.category === 'trigger' && !item.hidden)

const selectedNode = computed(() => (selection.value?.kind === 'node' ? findNode(selection.value.id) : null))
const selectedEdge = computed(() => (selection.value?.kind === 'edge' ? findEdge(selection.value.id) : null))
const triggerNode = computed(() => nodes.value.find((node) => isTrigger(node.data?.nodeType)) || null)
const derivedTrigger = computed(() => triggerTypeOf(nodes.value))
const testing = ref(false)
const recipesOpen = ref(false)
const docFields = ref([])
const recordFields = ref({})
const RECORD_STEPS = ['find_record', 'create_record', 'create_from_order', 'create_sales_order', 'make_record', 'save_address']
const SAVED_RECORDS = {
  find_record: { key: 'record', group: 'Found' },
  create_record: { key: 'created', group: 'Created' },
  create_from_order: { key: 'order', group: 'Created', fallback: 'Sales Order' },
  create_sales_order: { key: 'order', group: 'Created', fallback: 'Sales Order' },
  make_record: { key: 'made', group: 'Made' },
  save_address: { key: 'address', group: 'Saved', doctype: 'Address' },
}
const ORDER_VARIABLES = [
  { group: 'Order', label: 'Items (one per line)', token: '{{order.summary}}' },
  { group: 'Order', label: 'Total', token: '{{order.total}}' },
  { group: 'Order', label: 'Number of items', token: '{{order.count}}' },
  { group: 'Order', label: 'Total quantity', token: '{{order.quantity}}' },
  { group: 'Order', label: 'Currency', token: '{{order.currency}}' },
  { group: 'Order', label: 'Customer note', token: '{{order.note}}' },
  { group: 'Order', label: 'Items not in ERPNext', token: '{{order.unknown}}' },
]

function savedRecord(type, config) {
  const saved = SAVED_RECORDS[type]
  return { key: config.save_as || saved.key, group: saved.group, doctype: saved.doctype || config.doctype || saved.fallback }
}

const BASE_VARIABLES = [
  { group: 'Customer', label: 'Name', token: '{{name}}' },
  { group: 'Customer', label: 'First name', token: '{{first_name}}' },
  { group: 'Customer', label: 'Phone', token: '{{phone}}' },
  { group: 'Customer', label: 'Email', token: '{{email}}' },
  { group: 'Customer', label: 'Their last reply', token: '{{last_reply}}' },
  { group: 'Customer', label: 'Linked ERPNext record', token: '{{contact.links.erpnext.name}}' },
  { group: 'Customer', label: 'Linked ERPNext record type', token: '{{contact.links.erpnext.doctype}}' },
  { group: 'Customer', label: 'Linked CRM record', token: '{{contact.links.crm.name}}' },
]

const variables = computed(() => {
  const list = [...BASE_VARIABLES]
  if (triggerNode.value?.data?.nodeType === 'order_placed') list.push(...ORDER_VARIABLES)
  for (const node of nodes.value) {
    const type = node.data?.nodeType
    const config = node.data?.config || {}
    if (['ask_question', 'send_buttons', 'send_list'].includes(type) && config.save_as) {
      list.push({ group: 'Their answers', label: config.save_as.replace(/_/g, ' '), token: `{{answers.${config.save_as}}}` })
    }
    if (type === 'set_variable') {
      for (const name of Object.keys(config.variables || {})) {
        if (name) list.push({ group: 'Saved values', label: name.replace(/_/g, ' '), token: `{{vars.${name}}}` })
      }
    }
    if (type === 'summarize_list') {
      const key = config.save_as || 'summary'
      list.push({ group: 'Summary', label: `${key} text`, token: `{{vars.${key}.text}}` })
      list.push({ group: 'Summary', label: `${key} count`, token: `{{vars.${key}.count}}` })
      list.push({ group: 'Summary', label: `${key} total`, token: `{{vars.${key}.total}}` })
    }
    if (type === 'http_request') {
      list.push({ group: 'API reply', label: 'Reply', token: '{{http.response}}' })
      list.push({ group: 'API reply', label: 'Status code', token: '{{http.status_code}}' })
      if (config.save_as) list.push({ group: 'API reply', label: config.save_as.replace(/_/g, ' '), token: `{{vars.${config.save_as}}}` })
    }
    if (type === 'get_list') {
      list.push({
        group: 'Found records',
        label: `${config.doctype || 'Records'} (list)`,
        token: `{{records.${config.save_as || 'list'}}}`,
      })
    }
    if (RECORD_STEPS.includes(type)) {
      const { key, doctype, group: verb } = savedRecord(type, config)
      const group = `${verb} ${doctype || key}`
      list.push({ group, label: 'ID', token: `{{records.${key}.name}}` })
      for (const field of recordFields.value[doctype] || []) {
        if (NO_VALUE_TYPES.includes(field.fieldtype) || field.fieldname === 'name') continue
        list.push({ group, label: field.label || field.fieldname, token: `{{records.${key}.${field.fieldname}}}` })
      }
    }
  }
  for (const field of docFields.value) {
    if (!NO_VALUE_TYPES.includes(field.fieldtype)) list.push({ group: 'Record', label: field.label, token: `{{doc.${field.fieldname}}}` })
  }

  const seen = new Set()
  return list.filter((row) => !seen.has(row.token) && seen.add(row.token))
})

provide('flowVariables', variables)

watch(
  () =>
    [
      ...new Set(
        nodes.value
          .filter((node) => RECORD_STEPS.includes(node.data?.nodeType))
          .map((node) => savedRecord(node.data.nodeType, node.data.config || {}).doctype)
          .filter(Boolean),
      ),
    ].join('|'),
  async (joined) => {
    for (const doctype of joined ? joined.split('|') : []) {
      if (recordFields.value[doctype]) continue
      try {
        recordFields.value = { ...recordFields.value, [doctype]: (await doctypeFields(doctype)).slice(0, 80) }
      } catch {
        recordFields.value = { ...recordFields.value, [doctype]: [] }
      }
    }
  },
  { immediate: true },
)

watch(
  () => (triggerNode.value?.data?.nodeType === 'doc_event_trigger' ? triggerNode.value.data.config?.doctype || '' : ''),
  async (doctype) => {
    docFields.value = []
    if (!doctype) return
    try {
      docFields.value = (await doctypeFields(doctype)).slice(0, 120)
    } catch {
      docFields.value = []
    }
  },
  { immediate: true },
)

function useRecipe(recipe) {
  if (!recipe) return

  const graph = readGraph(recipe.build())
  flow.value = { ...flow.value, flow_name: __(recipe.title), description: __(recipe.description), category: recipe.category }
  setNodes(graph.nodes)
  setEdges(graph.edges)
  markDirty()
  pendingFit = true
  setTimeout(fitCanvas, 50)
}

function toggleTestChat() {
  if (testing.value) closeTestChat()
  else {
    selection.value = null
    testing.value = true
  }
}

function closeTestChat() {
  testing.value = false
  statuses.value = {}
}

function showPath({ visited, waiting, failed }) {
  const map = {}
  for (const id of visited) map[id] = 'Success'
  if (failed && visited.length) map[visited[visited.length - 1]] = 'Failed'
  if (waiting) map[waiting] = 'Waiting'
  statuses.value = map
}

function blankFlow() {
  return {
    name: null,
    flow_name: __('Untitled flow'),
    description: '',
    trigger_type: '',
    category: '',
    is_active: 0,
    stop_on_agent_reply: 1,
    reply_timeout_hours: 24,
    ...failureOf(),
  }
}

function applyFlow(doc) {
  flow.value = {
    name: doc.name,
    flow_name: doc.flow_name || doc.name,
    description: doc.description || '',
    trigger_type: doc.draft?.trigger_type || doc.trigger_type || '',
    category: doc.category || '',
    is_active: doc.is_active ? 1 : 0,
    stop_on_agent_reply: doc.stop_on_agent_reply ?? 1,
    reply_timeout_hours: doc.reply_timeout_hours || 24,
    published_version: doc.published_version || 0,
    ...failureOf(doc),
  }
  hasDraft.value = !!doc.draft
  savedActive.value = !!doc.is_active
}

function markDirty() {
  if (!hydrating) dirty.value = true
}

function changeFlow(patch) {
  Object.assign(flow.value, patch)
  markDirty()
}

async function load(name) {
  hydrating = true
  loadError.value = ''
  selection.value = null
  statuses.value = {}
  lastRun.value = null

  try {
    hasDraft.value = false
    savedActive.value = false
    stats.value = null
    if (name === 'new') {
      statsDays.value = 0
      flow.value = blankFlow()
      setNodes([])
      setEdges([])
    } else {
      loading.value = true
      const doc = await call('onechat.automation.flows.get_flow', { flow_name: name })
      applyFlow(doc)
      const shown = readGraph(doc.draft?.graph_json ?? doc.graph_json)
      pendingFit = true
      setNodes(shown.nodes)
      setEdges(shown.edges)
      if (statsDays.value) loadStats()
    }
  } catch (err) {
    loadError.value = errorMessage(err)
  } finally {
    loading.value = false
    await nextTick()
    dirty.value = false
    hydrating = false
    if (pendingFit && nodes.value.length) setTimeout(fitCanvas, 50)
  }
}

function fitCanvas() {
  pendingFit = false
  fitView({ padding: 0.25, maxZoom: 1 })
}

onNodesInitialized(() => {
  if (pendingFit) fitCanvas()
})

watch(
  () => route.params.name,
  (name) => {
    if (!name || (name !== 'new' && name === flow.value.name)) return
    load(String(name))
  },
  { immediate: true },
)

watch(derivedTrigger, (value) => {
  if (value && value !== flow.value.trigger_type) {
    flow.value.trigger_type = value
    markDirty()
  }
})

function select(kind, id, focus = false) {
  selection.value = { kind, id }
  if (kind !== 'node') return

  const node = findNode(id)
  if (!node) return
  removeSelectedElements()
  addSelectedNodes([node])
  if (focus) fitView({ nodes: [id], padding: 1.2, maxZoom: 1, duration: 300 })
}

function clearSelection() {
  selection.value = null
}

function onNodesChange(changes) {
  if (changes.some((change) => ['add', 'remove'].includes(change.type) || (change.type === 'position' && change.dragging))) {
    markDirty()
  }
  if (selection.value?.kind === 'node' && changes.some((change) => change.type === 'remove' && change.id === selection.value.id)) {
    clearSelection()
  }
}

function onEdgesChange(changes) {
  if (changes.some((change) => ['add', 'remove'].includes(change.type))) markDirty()
  if (selection.value?.kind === 'edge' && changes.some((change) => change.type === 'remove' && change.id === selection.value.id)) {
    clearSelection()
  }
}

function newEdge(connection) {
  return {
    id: `e-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle || null,
    targetHandle: connection.targetHandle || null,
    label: edgeLabel(connection, findNode(connection.source)),
    data: { condition: '' },
  }
}

function isValidConnection(connection) {
  if (!connection.source || connection.source === connection.target) return false

  const target = findNode(connection.target)
  if (!target || isTrigger(target.data?.nodeType)) return false

  return !edges.value.some(
    (edge) =>
      edge.source === connection.source &&
      edge.target === connection.target &&
      (edge.sourceHandle || null) === (connection.sourceHandle || null),
  )
}

function onConnect(connection) {
  if (!isValidConnection(connection)) return

  addEdges([newEdge(connection)])
  markDirty()
}

function centre() {
  const rect = canvas.value?.getBoundingClientRect()
  if (!rect) return { x: 0, y: 0 }

  const point = screenToFlowCoordinate({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 3 })
  const shift = (nodes.value.length % 6) * 24

  return { x: point.x - 120 + shift, y: point.y - 30 + shift }
}

function addStep(type, position) {
  const anchor = !position && selectedNode.value ? selectedNode.value : null
  const node = makeNode(type, position || (anchor ? { x: anchor.position.x, y: anchor.position.y + 160 } : centre()))

  addNodes([node])

  const anchorOutputs = anchor ? outputsOf(anchor.data.nodeType, anchor.data.config) : null
  if (anchor && !isTrigger(type) && !(anchorOutputs && !anchorOutputs.length)) {
    const handle = anchorOutputs?.[0]?.id || null
    addEdges([newEdge({ source: anchor.id, sourceHandle: handle, target: node.id })])
  }

  markDirty()
  nextTick(() => select('node', node.id))
}

function onDragOver(event) {
  event.dataTransfer.dropEffect = 'move'
}

function onDrop(event) {
  const type = event.dataTransfer.getData('application/onechat-node')
  if (!type) return

  const point = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  addStep(type, { x: point.x - 120, y: point.y - 30 })
}

function changeNode(id, patch) {
  updateNodeData(id, patch)
  markDirty()
}

function changeEdge(id, patch) {
  if ('label' in patch) {
    const edge = findEdge(id)
    if (edge) edge.label = patch.label
  }
  if ('condition' in patch) updateEdgeData(id, { condition: patch.condition })
  markDirty()
}

function duplicateNode(node) {
  const copy = makeNode(node.data.nodeType, { x: node.position.x + 40, y: node.position.y + 40 })
  copy.data.label = node.data.label
  copy.data.config = JSON.parse(JSON.stringify(node.data.config || {}))
  addNodes([copy])
  markDirty()
  nextTick(() => select('node', copy.id))
}

function deleteNode(id) {
  removeNodes([id], true)
  clearSelection()
  markDirty()
}

function deleteEdge(id) {
  removeEdges([id])
  clearSelection()
  markDirty()
}

function miniClass(node) {
  return colorOf(node.data?.nodeType).mini
}

function nodeName(node) {
  const def = nodeDef(node.data.nodeType)

  return node.data.label && node.data.label !== def.label ? node.data.label : __(def.label)
}

function graph() {
  return writeGraph(nodes.value, edges.value)
}

async function save(publishNow = false) {
  const name = String(flow.value.flow_name || '').trim()
  if (!name) {
    toast.error(__('Give the flow a name first'))
    return false
  }

  saving.value = true
  try {
    const saved = await call('onechat.automation.flows.save_flow', {
      flow_name: flow.value.name,
      publish: publishNow ? 1 : 0,
      flow_data: {
        flow_name: name,
        description: flow.value.description || '',
        is_active: flow.value.is_active ? 1 : 0,
        trigger_type: flow.value.trigger_type || derivedTrigger.value || null,
        category: flow.value.category || guessCategory(name, nodes.value) || null,
        stop_on_agent_reply: flow.value.stop_on_agent_reply ? 1 : 0,
        reply_timeout_hours: Number(flow.value.reply_timeout_hours) || 24,
        error_message: flow.value.error_message || '',
        error_handover: flow.value.error_handover ? 1 : 0,
        error_team: flow.value.error_team || null,
        error_notify: flow.value.error_notify ? 1 : 0,
        error_pause: flow.value.error_pause ? 1 : 0,
        graph_json: JSON.stringify(graph(), null, 2),
      },
    })

    applyFlow(saved)
    dirty.value = false
    toast.success(
      publishNow
        ? __('Published version {0}').format(saved.published_version)
        : hasDraft.value
        ? __('Draft saved. The live flow is unchanged until you publish.')
        : __('Flow saved'),
    )

    if (route.params.name !== saved.name) {
      await router.replace({ name: 'FlowBuilder', params: { name: saved.name } })
    }

    return true
  } catch (err) {
    toast.error(errorMessage(err))
    return false
  } finally {
    saving.value = false
  }
}

function clientIssues() {
  const out = []
  const list = nodes.value
  const triggers = list.filter((node) => isTrigger(node.data?.nodeType))
  const targets = new Set(edges.value.map((edge) => edge.target))

  if (!list.length) out.push({ level: 'error', message: __('The canvas is empty.') })
  else if (!triggers.length) out.push({ level: 'error', message: __('Add a trigger so the flow knows when to start.') })
  if (triggers.length > 1) {
    out.push({
      level: 'warning',
      message: __('Only the first trigger, {0}, starts the flow.').format(nodeName(triggers[0])),
      nodeId: triggers[1].id,
    })
  }

  for (const node of list) {
    const missing = missingFields(node.data.nodeType, node.data.config)
    if (missing.length) {
      out.push({
        level: 'error',
        message: __('{0}: fill in {1}.').format(nodeName(node), missing.map((field) => __(field.label)).join(', ')),
        nodeId: node.id,
      })
    }
    if (!isTrigger(node.data.nodeType) && !targets.has(node.id)) {
      out.push({ level: 'warning', message: __('{0} is not connected, so it never runs.').format(nodeName(node)), nodeId: node.id })
    }
    const outputs = outputsOf(node.data.nodeType, node.data.config) || []
    const used = new Set(edges.value.filter((edge) => edge.source === node.id).map((edge) => edge.sourceHandle))
    const loose = outputs.filter((output) => !output.muted && !used.has(output.id))
    if (loose.length) {
      out.push({
        level: 'warning',
        message: __('{0}: {1} does not lead anywhere yet.').format(nodeName(node), loose.map((output) => `"${output.label}"`).join(', ')),
        nodeId: node.id,
      })
    }
    if (nodeDef(node.data.nodeType).runnable === false) {
      out.push({ level: 'warning', message: __('{0} is not run by the server yet.').format(nodeName(node)), nodeId: node.id })
    }
  }

  return out
}

async function validate() {
  validating.value = true
  const out = clientIssues()

  try {
    const result = await call('onechat.automation.flows.validate_flow', { graph_json: JSON.stringify(graph()) })
    const known = out.map((issue) => issue.message)
    for (const message of result.errors || []) {
      if (!/trigger|at least one step/i.test(message) && !known.includes(message)) out.push({ level: 'error', message })
    }
    for (const message of result.warnings || []) {
      if (!known.includes(message)) out.push({ level: 'warning', message })
    }
    for (const row of result.issues || []) {
      if (!known.includes(row.message)) out.push({ level: row.level, message: row.message, nodeId: row.node_id || undefined })
    }
  } catch (err) {
    out.push({ level: 'warning', message: __('The server check could not run: {0}').format(errorMessage(err)) })
  } finally {
    validating.value = false
  }

  issues.value = out.sort((a, b) => (a.level === b.level ? 0 : a.level === 'error' ? -1 : 1))
  validateOpen.value = true
}

async function openTest() {
  if (!triggerNode.value) {
    toast.error(__('Add a trigger before running the flow'))
    return
  }
  if (savedActive.value && (hasDraft.value || dirty.value)) {
    toast.warning(__('Run for real uses the live version. Publish your changes first, or try them with Test chat.'))
    return
  }
  if (!flow.value.name || dirty.value) {
    const ok = await save()
    if (!ok) return
  }

  testOpen.value = true
}

async function runTest(context, contact) {
  running.value = true
  let failure = null

  try {
    const result = await call('onechat.automation.flows.execute_flow', {
      flow_name: flow.value.name,
      context: JSON.stringify(context),
      contact: contact || undefined,
    })
    if (result?.status === 'Waiting') toast.info(__('The flow is waiting for a reply from the contact'))
  } catch (err) {
    failure = err
  }

  await loadLastRun()
  running.value = false
  testOpen.value = false

  if (failure) toast.error(__('Test run failed: {0}').format(errorMessage(failure)))
  else toast.success(__('Test run finished'))
}

async function loadLastRun() {
  try {
    const logs = await call('onechat.automation.flows.get_execution_logs', { flow_name: flow.value.name, limit: 1 })
    if (!logs?.length) return

    const log = await call('onechat.automation.flows.get_execution_log', { log_name: logs[0].name })
    const map = {}
    for (const step of log.execution_steps || []) map[step.node_id] = step.status
    statuses.value = map
    lastRun.value = { name: log.name, status: log.status, duration: log.duration }
  } catch {
    lastRun.value = null
  }
}

function clearRun() {
  lastRun.value = null
  statuses.value = {}
}

function deleteFlow() {
  ui.confirm({
    title: __('Delete {0}?').format(flow.value.flow_name),
    message: __('The flow stops running, and its canvas and run history are removed. This cannot be undone.'),
    action: __('Delete'),
    theme: 'red',
    onConfirm: async () => {
      await call('onechat.automation.flows.delete_flow', { flow_name: flow.value.name })
      dirty.value = false
      toast.success(__('Flow deleted'))
      router.push({ name: 'Flows' })
    },
  })
}

const liveTooltip = computed(() =>
  hasDraft.value
    ? __('Customers still get the live version. Publish to switch them to your draft.')
    : __('Customers are getting this version.'),
)

async function publish() {
  publishing.value = true
  try {
    await save(true)
  } finally {
    publishing.value = false
  }
}

function discardDraft() {
  ui.confirm({
    title: __('Discard draft?'),
    message: __('Your unpublished changes will be lost and the builder will show the live version again.'),
    action: __('Discard'),
    theme: 'red',
    onConfirm: async () => {
      try {
        await call('onechat.automation.flows.discard_draft', { flow_name: flow.value.name })
        await load(flow.value.name)
        toast.success(__('Draft discarded'))
      } catch (err) {
        toast.error(errorMessage(err))
      }
    },
  })
}

async function loadStats() {
  if (!flow.value.name || !statsDays.value) return
  statsLoading.value = true
  try {
    stats.value = await call('onechat.automation.flows.flow_stats', { flow_name: flow.value.name, days: statsDays.value })
  } catch (err) {
    toast.error(errorMessage(err))
    statsDays.value = 0
  } finally {
    statsLoading.value = false
  }
}

function showStats(days) {
  statsDays.value = days
  stats.value = null
  if (days) loadStats()
}

const EMPTY_STATS = { reached: 0, failed: 0, waiting: 0, left: 0 }
const STATS_PERIODS = [7, 30, 90]

const nodeStats = computed(() => {
  if (!statsDays.value || !stats.value) return {}
  const started = stats.value.started || 0
  return Object.fromEntries(
    nodes.value.map((node) => {
      const row = stats.value.nodes?.[node.id] || EMPTY_STATS
      return [node.id, { ...row, share: started ? Math.round((row.reached * 100) / started) : null }]
    }),
  )
})

const statsMenu = computed(() => [
  {
    group: __('Show on steps'),
    options: [
      ...STATS_PERIODS.map((days) => ({
        label: __('Last {0} days').format(days),
        icon: 'lucide-calendar',
        onClick: () => showStats(days),
      })),
      { label: __('Hide stats'), icon: 'lucide-eye-off', condition: () => !!statsDays.value, onClick: () => showStats(0) },
    ],
  },
])

const moreMenu = computed(() => [
  { label: __('Run for real…'), icon: 'lucide-play', onClick: openTest },
  {
    label: __('Version history'),
    icon: 'lucide-history',
    condition: () => !!flow.value.name,
    onClick: () => (historyOpen.value = true),
  },
  {
    label: __('Discard draft'),
    icon: 'lucide-undo-2',
    condition: () => hasDraft.value,
    onClick: discardDraft,
  },
  {
    label: __('View runs'),
    icon: 'lucide-scroll-text',
    condition: () => !!flow.value.name,
    onClick: () => router.push({ name: 'ExecutionLogs', query: { flow: flow.value.name } }),
  },
  { label: __('Fit to screen'), icon: 'lucide-scan', onClick: () => fitView({ padding: 0.25, maxZoom: 1, duration: 300 }) },
  {
    label: showMinimap.value ? __('Hide minimap') : __('Show minimap'),
    icon: 'lucide-map',
    onClick: () => (showMinimap.value = !showMinimap.value),
  },
  {
    label: __('Delete flow'),
    icon: 'lucide-trash-2',
    condition: () => !!flow.value.name,
    onClick: deleteFlow,
  },
])

function guard(to) {
  if (!dirty.value) return true

  ui.confirm({
    title: __('Discard unsaved changes?'),
    message: __('Your changes to this flow have not been saved.'),
    action: __('Discard'),
    theme: 'red',
    onConfirm: () => {
      dirty.value = false
      router.push(to.fullPath)
    },
  })

  return false
}

onBeforeRouteLeave(guard)
onBeforeRouteUpdate(guard)

function onBeforeUnload(event) {
  if (!dirty.value) return

  event.preventDefault()
  event.returnValue = ''
}

function onKeydown(event) {
  if (props.compact || !(event.ctrlKey || event.metaKey) || event.altKey) return
  if ((event.key || '').toLowerCase() !== 's') return

  event.preventDefault()
  if (!saving.value) save()
}

watch(
  () => props.compact,
  (compact) => (ui.fullScreen = !compact),
)

onMounted(() => {
  wasFullScreen = ui.fullScreen
  ui.fullScreen = !props.compact
  window.addEventListener('beforeunload', onBeforeUnload)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  ui.fullScreen = wasFullScreen
  window.removeEventListener('beforeunload', onBeforeUnload)
  document.removeEventListener('keydown', onKeydown)
})
</script>

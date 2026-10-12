import { computed, reactive, toValue } from 'vue'
import { session } from '@/data/session'
import { useSocket } from '@/data/socket'

const DOCTYPE = 'OneChat Contact'
const PING_MS = 3000
const IDLE_MS = 4000
const REFRESH_MS = 10000

const typers = reactive({})
const viewers = reactive({})
const watched = new Map()

let listening = false
let typingFor = null
let lastPing = 0
let idleTimer = null

function listen() {
  if (listening) return
  listening = true

  const socket = useSocket()
  socket.on('onechat_contact_typers', ({ contact, users }) => {
    typers[contact] = (users || []).filter((user) => user !== session.user.name)
  })
  socket.on('doc_viewers', ({ doctype, docname, users }) => {
    if (doctype !== DOCTYPE) return
    viewers[docname] = (users || []).filter((user) => user !== session.user.name)
  })
  socket.on('connect', () => {
    for (const contact of watched.keys()) join(contact)
  })
}

function join(contact) {
  const socket = useSocket()
  socket.emit('doc_open', DOCTYPE, contact)
  socket.emit('onechat_contact_get_typers', contact)
}

export function watchTypers(contact) {
  if (!contact) return () => {}

  listen()
  join(contact)

  const timer = setInterval(() => useSocket().emit('onechat_contact_get_typers', contact), REFRESH_MS)
  watched.set(contact, timer)

  return () => {
    clearInterval(watched.get(contact))
    watched.delete(contact)
    delete typers[contact]
    delete viewers[contact]
    if (typingFor === contact) stopTyping()
    useSocket().emit('doc_close', DOCTYPE, contact)
  }
}

export function notifyTyping(contact) {
  if (!contact) return
  if (typingFor && typingFor !== contact) stopTyping()

  const now = Date.now()
  if (typingFor !== contact || now - lastPing > PING_MS) {
    useSocket().emit('onechat_contact_typing', contact)
    lastPing = now
  }

  typingFor = contact
  clearTimeout(idleTimer)
  idleTimer = setTimeout(stopTyping, IDLE_MS)
}

export function stopTyping() {
  clearTimeout(idleTimer)
  if (!typingFor) return

  useSocket().emit('onechat_contact_typing_stopped', typingFor)
  typingFor = null
  lastPing = 0
}

export function useTypers(contact) {
  return computed(() => typers[toValue(contact)] || [])
}

export function useViewers(contact) {
  return computed(() => viewers[toValue(contact)] || [])
}

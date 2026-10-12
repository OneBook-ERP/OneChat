import { io } from 'socket.io-client'
import { reactive } from 'vue'

export const realtime = reactive({ connected: false, error: null })

let socket = null
const subscribed = new Set()

function address() {
  const { protocol, hostname, port } = window.location
  const site = window.site_name || hostname

  if (!port) return `${protocol}//${hostname}/${site}`

  return `http://${hostname}:${window.socketio_port || 9000}/${site}`
}

export function useSocket() {
  if (socket) return socket

  socket = io(address(), {
    withCredentials: true,
    reconnection: true,
    reconnectionDelayMax: 10000,
  })

  socket.on('connect', () => {
    realtime.connected = true
    realtime.error = null
    subscribed.forEach((doctype) => socket.emit('doctype_subscribe', doctype))
  })

  socket.on('disconnect', () => {
    realtime.connected = false
  })

  socket.on('connect_error', (error) => {
    realtime.connected = false
    realtime.error = error.message
  })

  return socket
}

export function subscribeDoctype(doctype) {
  const current = useSocket()
  if (subscribed.has(doctype)) return

  subscribed.add(doctype)
  if (current.connected) current.emit('doctype_subscribe', doctype)
}

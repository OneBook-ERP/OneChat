function onechat_handlers(socket) {
	socket.on("onechat_ping", () => {
		socket.emit("onechat_pong");
	});

	socket.on("onechat_contact_get_typers", function (contact) {
		socket.has_permission("OneChat Contact", contact).then(() => {
			notify_typing({ socket, contact, toUser: true });
		});
	});

	socket.on("onechat_contact_typing", function (contact) {
		socket.join(contact_typing_room(contact));
		notify_typing({ socket, contact, toUser: false });
	});

	socket.on("onechat_contact_typing_stopped", function (contact) {
		socket.leave(contact_typing_room(contact));
		notify_typing({ socket, contact, toUser: false });
	});
}

function notify_typing(args) {
	if (!(args && args.socket && args.contact)) return;

	const socket = args.socket;
	const contact = args.contact;

	const typers_room = contact_typing_room(contact);
	const clients = Array.from(socket.nsp.adapter.rooms.get(typers_room) || []);
	let users = [];

	socket.nsp.sockets.forEach((sock) => {
		if (clients.includes(sock.id)) {
			users.push(sock.user);
		}
	});

	const contact_room = args.toUser
		? user_room(args.socket.user)
		: open_doc_room("OneChat Contact", contact);

	socket.nsp.to(contact_room).emit("onechat_contact_typers", {
		contact,
		users: Array.from(new Set(users)),
	});
}

const contact_typing_room = (contact) => "onechat_contact_typing:" + contact;
const open_doc_room = (doctype, docname) => "open_doc:" + doctype + "/" + docname;
const user_room = (user) => "user:" + user;

module.exports = onechat_handlers;

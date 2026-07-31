/** One shared WebSocket to /ws, mirroring the sub/unsub protocol in API.md.
 *
 * - Auto-reconnects with a 1s backoff.
 * - Actions sent while the socket is down are queued and flushed on open.
 * - Channel subscriptions are replayed on every (re)connect, so a page that
 *   subscribed before a drop keeps receiving snapshots afterwards.
 *
 * Channels: "lobby" and "game:<id>" map onto the wire sub/unsub protocol.
 * The pseudo-channel "user" is local-only — the server pushes account-level
 * events (gameStart, challenge*, gameFinish, err) to authenticated sockets
 * without any subscription, so we just fan those out to "user" handlers.
 */

type Handler = (msg: any) => void;

const RETRY_MS = 1000;

let socket: WebSocket | null = null;
let queue: any[] = [];
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let started = false;

const channels = new Map<string, Set<Handler>>();
const personal = new Set<Handler>();

function wsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/ws`;
}

function open(): void {
  const ws = new WebSocket(wsUrl());
  socket = ws;
  ws.onopen = () => {
    if (socket !== ws) return;
    // Re-establish subscriptions before flushing queued actions so a queued
    // move never races its own game channel's snapshot.
    for (const ch of channels.keys()) ws.send(JSON.stringify({ t: 'sub', ch }));
    const pending = queue;
    queue = [];
    for (const msg of pending) ws.send(JSON.stringify(msg));
  };
  ws.onmessage = (ev) => {
    let msg: any;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    route(msg);
  };
  ws.onclose = () => {
    if (socket !== ws) return; // superseded by reconnect(); no retry
    socket = null;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      open();
    }, RETRY_MS);
  };
  ws.onerror = () => {
    ws.close();
  };
}

function route(msg: any): void {
  let ch: string | null = null;
  if (msg.t === 'lobby') ch = 'lobby';
  else if (msg.t === 'state' && msg.game) ch = 'game:' + msg.game;
  else if (msg.t === 'gameFull' && msg.id) ch = 'game:' + msg.id;
  if (ch !== null) {
    const set = channels.get(ch);
    if (set) for (const h of [...set]) h(msg);
    return;
  }
  for (const h of [...personal]) h(msg);
}

/** Open the shared socket (idempotent). */
export function connect(): void {
  if (started) return;
  started = true;
  open();
}

/** Force a fresh socket. The server authenticates the socket by session
 *  cookie at handshake time, so login/logout must reconnect. */
export function reconnect(): void {
  started = true;
  if (retryTimer) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
  if (socket) {
    const old = socket;
    socket = null; // onclose guard: this close must not schedule a retry
    old.onclose = null;
    try {
      old.close();
    } catch {
      // already closed
    }
  }
  open();
}

/** Send an action message; queued if the socket is still connecting. */
export function send(msg: any): void {
  connect();
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(msg));
  } else {
    queue.push(msg);
  }
}

/** Register a handler for a channel; returns an unsubscribe function.
 *  The wire sub is sent when the first handler arrives, the unsub when the
 *  last one leaves. */
export function subscribe(channel: string, handler: Handler): () => void {
  connect();
  if (channel === 'user') {
    personal.add(handler);
    return () => {
      personal.delete(handler);
    };
  }
  let set = channels.get(channel);
  if (!set) {
    set = new Set();
    channels.set(channel, set);
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ t: 'sub', ch: channel }));
    }
  }
  set.add(handler);
  return () => {
    const s = channels.get(channel);
    if (!s || !s.delete(handler)) return;
    if (s.size === 0) {
      channels.delete(channel);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ t: 'unsub', ch: channel }));
      }
    }
  };
}

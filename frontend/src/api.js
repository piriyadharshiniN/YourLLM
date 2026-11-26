const json = async (r) => {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
};
const H = { "Content-Type": "application/json" };
const send = (method, url, body) =>
  fetch(url, { method, headers: H, body: body ? JSON.stringify(body) : undefined }).then(json);

export const api = {
  docs: () => fetch("/api/documents").then(json),
  upload: (files, chatId) => {
    const f = new FormData();
    [...files].forEach((x) => f.append("files", x));
    return fetch(`/api/documents${chatId ? `?chat_id=${chatId}` : ""}`, { method: "POST", body: f }).then(json);
  },
  delDoc: (id) => send("DELETE", `/api/documents/${id}`),
  chats: () => fetch("/api/chats").then(json),
  newChat: (body) => send("POST", "/api/chats", body),
  chat: (id) => fetch(`/api/chats/${id}`).then(json),
  patch: (id, body) => send("PATCH", `/api/chats/${id}`, body),
  delChat: (id) => send("DELETE", `/api/chats/${id}`),
};

// The answer arrives as newline-delimited JSON events: sources, token, error, done.
export async function ask(chatId, question, onEvent) {
  const r = await fetch(`/api/chats/${chatId}/ask`, { method: "POST", headers: H, body: JSON.stringify({ question }) });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) onEvent(JSON.parse(line));
    }
  }
}

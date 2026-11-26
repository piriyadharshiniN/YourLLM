import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ask } from "./api";

const Icon = ({ n, size = 20 }) => <img className="ic" src={`/icons/${n}.svg`} width={size} height={size} alt="" />;
const greet = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
};
const fmtDate = (t) => new Date(t * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
const fmtSize = (b) => (b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB");
const SUGGEST = ["Summarize the documents", "Compare the documents", "List the key takeaways"];

function UploadZone({ onFiles, busy, errors }) {
  const input = useRef();
  const [over, setOver] = useState(false);
  return (
    <div
      className={`drop ${over ? "over" : ""}`}
      role="button"
      tabIndex={0}
      onClick={() => input.current.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files); }}
    >
      <input ref={input} type="file" hidden multiple accept=".pdf,.docx,.txt"
        onChange={(e) => { if (e.target.files.length) onFiles(e.target.files); e.target.value = ""; }} />
      <Icon n="upload-cloud" size={48} />
      <h3>Upload your documents</h3>
      <p>{busy ? "Reading and indexing your files…" : "Drag & drop files here or click to browse"}</p>
      <div><span className="pill">PDF</span><span className="pill">DOCX</span><span className="pill">TXT</span></div>
      {errors.map((e, i) => <div className="err" key={i}>{e}</div>)}
    </div>
  );
}

function EditableTitle({ value, onSave, as: Tag = "h2", onClick }) {
  const [edit, setEdit] = useState(false);
  const [text, setText] = useState(value);
  const done = (save) => {
    setEdit(false);
    if (save && text.trim() && text.trim() !== value) onSave(text.trim());
    else setText(value);
  };
  if (edit)
    return (
      <input className="title-input" autoFocus value={text} aria-label="Chat title"
        onChange={(e) => setText(e.target.value)} onBlur={() => done(true)}
        onKeyDown={(e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); }} />
    );
  return (
    <>
      <Tag onClick={onClick}>{value}</Tag>
      <button className="icon-btn" title="Rename chat" aria-label="Rename chat"
        onClick={() => { setText(value); setEdit(true); }}>
        <Icon n="pencil" size={16} />
      </button>
    </>
  );
}

function Sources({ sources }) {
  const best = new Map();
  sources.forEach((s) => {
    const k = `${s.doc_id}-${s.page}`;
    if (!best.has(k) || best.get(k).score < s.score) best.set(k, s);
  });
  return (
    <div className="sources">
      <div className="srow">
        <Icon n="file" size={16} />
        {[...best.values()].map((s) => (
          <a key={`${s.doc_id}-${s.page}`} className="pill" target="_blank" rel="noreferrer"
            href={`/api/documents/${s.doc_id}/file#page=${s.page}`}>
            {s.source} · {Math.round(s.score * 100)}%
          </a>
        ))}
      </div>
      <details>
        <summary>Show retrieved text</summary>
        {sources.map((s, i) => (
          <blockquote key={i}><b>{s.source}</b><br />{s.text}</blockquote>
        ))}
      </details>
    </div>
  );
}

function Message({ m, last, streaming }) {
  const user = m.role === "user";
  const content = m.content.replace(/,\s*p\.\d+(?=\])/gi, "");
  return (
    <div className={`msg ${user ? "user" : "bot"}`}>
      <img className="av" src={`/icons/${user ? "user" : "bot"}.svg`} alt="" />
      <div className={`bubble ${m.error ? "error" : ""}`}>
        {user ? <p>{m.content}</p>
          : content ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          : <span className="dots">{last && streaming ? "Searching your documents…" : ""}</span>}
        {!!m.sources?.length && <Sources sources={m.sources} />}
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState(localStorage.getItem("ka_page") || "home");
  const [docs, setDocs] = useState([]);
  const [chats, setChats] = useState([]);
  const [active, setActive] = useState(null);
  const [draft, setDraft] = useState([]); // ids of files attached to the not-yet-started chat
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [offline, setOffline] = useState(false);
  const [loaded, setLoaded] = useState(false); // persist only after the saved state was read
  const bottom = useRef();
  const attach = useRef();

  // ---- load everything from the server (so refresh / reopen restores it) ----
  useEffect(() => {
    const savedId = localStorage.getItem("ka_active"); // read BEFORE any effect overwrites it
    const savedDraft = JSON.parse(localStorage.getItem("ka_draft") || "[]");
    (async () => {
      try {
        const [d, c] = await Promise.all([api.docs(), api.chats()]);
        setDocs(d);
        setChats(c);
        if (savedId && c.some((x) => x.id === savedId)) setActive(await api.chat(savedId));
        else setDraft(savedDraft.filter((i) => d.some((x) => x.id === i)));
      } catch {
        setOffline(true);
      }
      setLoaded(true);
    })();
  }, []);
  useEffect(() => {
    if (!loaded) return;
    active ? localStorage.setItem("ka_active", active.id) : localStorage.removeItem("ka_active");
  }, [active?.id, loaded]);
  useEffect(() => { if (loaded) localStorage.setItem("ka_draft", JSON.stringify(draft)); }, [draft, loaded]);
  useEffect(() => { localStorage.setItem("ka_page", page); }, [page]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "end" }); }, [active?.messages, page]);

  const byId = (id) => docs.find((d) => d.id === id);
  const attached = (active ? active.doc_ids : draft).map(byId).filter(Boolean);
  const refresh = async () => { setDocs(await api.docs()); setChats(await api.chats()); };

  // ---- actions ----
  function startNew(ids = []) {
    setActive(null); setDraft(ids); setInput(""); setErrors([]); setPage("home");
  }
  async function openChat(id) {
    setActive(await api.chat(id)); setPage("home"); setErrors([]);
  }
  async function uploadFiles(files) {
    setBusy(true); setErrors([]);
    try {
      const r = await api.upload(files, active?.id);
      setErrors(r.errors.map((e) => `${e.name}: ${e.error}`));
      if (active) setActive(await api.chat(active.id));
      else setDraft((d) => [...d, ...r.docs.map((x) => x.id)]);
      await refresh();
    } catch (e) {
      setErrors([String(e.message || e)]);
    } finally {
      setBusy(false);
    }
  }
  async function detach(id) {
    if (active) setActive(await api.patch(active.id, { remove_doc_ids: [id] }));
    else setDraft((d) => d.filter((x) => x !== id));
  }
  async function rename(id, title) {
    const c = await api.patch(id, { title });
    setChats(await api.chats());
    if (active?.id === id) setActive((a) => ({ ...a, title: c.title }));
  }
  async function removeChat(id) {
    if (!window.confirm("Delete this chat?")) return;
    await api.delChat(id);
    setChats(await api.chats());
    if (active?.id === id) startNew();
  }
  async function removeDoc(id) {
    if (!window.confirm("Delete this file everywhere? Chats that use it will lose access to it.")) return;
    await api.delDoc(id);
    setDraft((d) => d.filter((x) => x !== id));
    await refresh();
    if (active) setActive(await api.chat(active.id));
  }
  async function send(text = input) {
    const q = text.trim();
    if (!q || streaming) return;
    setInput(""); setStreaming(true);
    const upd = (fn) => setActive((c) => {
      const msgs = [...c.messages];
      msgs[msgs.length - 1] = fn(msgs[msgs.length - 1]);
      return { ...c, messages: msgs };
    });
    let chat = active;
    try {
      if (!chat) { chat = await api.newChat({ doc_ids: draft }); setDraft([]); }
      setActive({ ...chat, messages: [...chat.messages, { role: "user", content: q }, { role: "assistant", content: "", sources: [] }] });
      await ask(chat.id, q, (ev) => {
        if (ev.type === "sources") upd((m) => ({ ...m, sources: ev.sources }));
        if (ev.type === "token") upd((m) => ({ ...m, content: m.content + ev.text }));
        if (ev.type === "error") upd((m) => ({ ...m, content: m.content || `Error: ${ev.message}`, error: true }));
      });
    } catch (e) {
      if (chat) upd((m) => ({ ...m, content: `Error: ${e.message || e}`, error: true }));
    } finally {
      setStreaming(false);
      if (chat) { setActive(await api.chat(chat.id).catch(() => active)); setChats(await api.chats()); }
    }
  }

  const Nav = ({ id, icon, label }) => (
    <button className={`nav ${page === id ? "on" : ""}`} onClick={() => setPage(id)}>
      <Icon n={icon} />{label}
    </button>
  );
  const chips = (
    <div className="chips">
      {attached.map((d) => (
        <span className="chip" key={d.id}>
          <Icon n="file" size={16} />{d.name}
          <button aria-label={`Remove ${d.name} from this chat`} onClick={() => detach(d.id)}><Icon n="x" size={14} /></button>
        </span>
      ))}
    </div>
  );

  return (
    <div className="app">
      <aside className="side">
        <div className="brand">
          <img src="/icons/logo.svg" alt="" />
          <div><b>YourLLM</b><small>Ask • Learn • Explore</small></div>
        </div>
        <button className="btn" onClick={() => startNew()}><Icon n="plus" /> New chat</button>
        <Nav id="home" icon="home" label="Home" />
        <Nav id="documents" icon="folder" label="Documents" />
        <Nav id="history" icon="history" label="Chat History" />
        <h4>Recent chats</h4>
        {chats.length === 0 && <div className="muted" style={{ padding: "0 8px" }}>Your conversations will appear here.</div>}
        {chats.slice(0, 6).map((c) => (
          <button key={c.id} className={`recent ${active?.id === c.id && page === "home" ? "on" : ""}`} onClick={() => openChat(c.id)}>{c.title}</button>
        ))}
      </aside>

      <main className="main">
        {offline && <div className="banner">Cannot reach the server. Start it with <b>python server.py</b> and refresh.</div>}

        {page === "documents" && (
          <div className="scroll"><div className="col page">
            <h2>Documents</h2>
            <p className="lead">Every file you upload is stored here and is still here after you refresh or reopen the app.</p>
            <button className="btn" onClick={() => attach.current.click()}><Icon n="upload-cloud" /> Upload files</button>
            {errors.map((e, i) => <div className="err" key={i}>{e}</div>)}
            {busy && <p className="muted">Reading and indexing your files…</p>}
            <div style={{ height: 18 }} />
            {docs.length === 0 && <div className="card empty">No documents yet. Upload some to build your document base.</div>}
            {docs.map((d) => (
              <div className="card row" key={d.id}>
                <Icon n="file" size={26} />
                <div className="grow"><b>{d.name}</b>
                  <span className="muted">{d.pages} page{d.pages > 1 ? "s" : ""} · {d.chunks} chunks · {fmtSize(d.size)} · {fmtDate(d.uploaded_at)}</span></div>
                <button className="btn" onClick={() => startNew([d.id])}><Icon n="message" size={18} /> Use in new chat</button>
                <button className="icon-btn" title="Delete file" aria-label={`Delete ${d.name}`} onClick={() => removeDoc(d.id)}><Icon n="trash" size={16} /></button>
              </div>
            ))}
          </div></div>
        )}

        {page === "history" && (
          <div className="scroll"><div className="col page" style={{ maxWidth: 1100 }}>
            <h2>Chat History</h2>
            <p className="lead">Each chat is stored separately with its own files. Rename a chat with the pencil icon.</p>
            {chats.length === 0 && <div className="card empty">No chats yet. Start one from Home.</div>}
            <div className="grid">
              {chats.map((c) => (
                <div className="card blk" key={c.id}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <EditableTitle as="h3" value={c.title} onSave={(t) => rename(c.id, t)} onClick={() => openChat(c.id)} />
                  </div>
                  <span className="muted">{fmtDate(c.updated_at)}</span>
                  <span className="muted">{Math.floor(c.message_count / 2)} questions · {c.doc_ids.length} file{c.doc_ids.length === 1 ? "" : "s"}</span>
                  <div className="acts">
                    <button className="btn" onClick={() => openChat(c.id)}>Open</button>
                    <button className="icon-btn" title="Delete chat" aria-label={`Delete ${c.title}`} onClick={() => removeChat(c.id)}><Icon n="trash" size={16} /></button>
                  </div>
                </div>
              ))}
            </div>
          </div></div>
        )}

        {page === "home" && (
          <>
            <div className="scroll">
              <div className="col">
                {!active || active.messages.length === 0 ? (
                  <div className="hero">
                    <Icon n="sparkles" size={40} />
                    <h1>{greet()}</h1>
                    <p className="sub">Upload files and ask your assistant to summarize or compare your sourced files.</p>
                    <UploadZone onFiles={uploadFiles} busy={busy} errors={errors} />
                    {chips}
                    <div className="suggest">
                      {SUGGEST.map((s) => (
                        <button key={s} className="btn" disabled={!attached.length} onClick={() => send(s)}><Icon n="lightbulb" size={18} />{s}</button>
                      ))}
                    </div>
                    {active && <p className="muted" style={{ marginTop: 18 }}>Chat: {active.title}</p>}
                  </div>
                ) : (
                  <>
                    <div className="chat-head">
                      <EditableTitle value={active.title} onSave={(t) => rename(active.id, t)} />
                    </div>
                    <div className="chips" style={{ justifyContent: "flex-start" }}>{chips.props.children}</div>
                    {errors.map((e, i) => <div className="err" key={i}>{e}</div>)}
                    {active.messages.map((m, i) => (
                      <Message key={i} m={m} last={i === active.messages.length - 1} streaming={streaming} />
                    ))}
                  </>
                )}
                <div ref={bottom} />
              </div>
            </div>
            <div className="composer">
              <div className="col">
                <button className="icon-btn" title="Attach files" aria-label="Attach files" onClick={() => attach.current.click()}><Icon n="paperclip" /></button>
                <textarea rows={1} value={input} aria-label="Ask a question" disabled={streaming}
                  placeholder="Ask anything about your documents..."
                  onChange={(e) => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = e.target.scrollHeight + "px"; }}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
                <button className="icon-btn" title="Send" aria-label="Send" disabled={streaming || !input.trim()} onClick={() => send()}><Icon n="send" /></button>
              </div>
            </div>
          </>
        )}
        <input ref={attach} type="file" hidden multiple accept=".pdf,.docx,.txt"
          onChange={(e) => { if (e.target.files.length) uploadFiles(e.target.files); e.target.value = ""; }} />
      </main>
    </div>
  );
}

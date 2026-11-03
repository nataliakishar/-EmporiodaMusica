"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, clearContext, closeSession, confirmContacts, openSession, sendMessage,
  type ApiResponse, type Contacts, type Session, type Source } from "@/lib/api";
import { ArrowIcon, MusicMark, ShieldIcon } from "./icons";
import { RegistrationForm } from "./registration-form";

type Message = { role: "assistant" | "user"; text: string; sources?: Source[]; protocol?: string };
type Phase = "ready" | "registration" | "active" | "ended" | "expired";
const greeting: Message = { role: "assistant", text: "Olá! Bem-vindo à Empório da Música. Qual som você está procurando hoje?" };
const starters = ["Quais violões custam até R$ 1.000?", "Quanto custa o Takamine GD20?", "Quais são as formas de pagamento?"];

function SourceDetails({ sources }: { sources: Source[] }) {
  const files = new Set<string>();
  function collect(value: unknown, depth = 0) {
    if (depth > 5) return;
    if (typeof value === "string" && /\.(csv|pdf)$/i.test(value)) files.add(value.split(/[\\/]/).pop()!);
    else if (Array.isArray(value)) value.forEach(item => collect(item, depth + 1));
    else if (value && typeof value === "object") Object.values(value).forEach(item => collect(item, depth + 1));
  }
  collect(sources);
  return files.size ? <details className="answer-sources"><summary>Consultar fontes desta resposta</summary><ul>{[...files].map(file => <li key={file}>{file}</li>)}</ul></details> : null;
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([greeting]);
  const [phase, setPhase] = useState<Phase>("ready");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [canRetry, setCanRetry] = useState(false);
  const session = useRef<Session | null>(null);
  const pending = useRef<string | null>(null);
  const busyRef = useRef(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Rolagem restrita ao histórico: não tira o visitante de outra parte da página.
    if (log.current) {
      const form = log.current.querySelector<HTMLElement>(".registration-card");
      log.current.scrollTop = form && phase === "registration" && !busy ? form.offsetTop - 12 : log.current.scrollHeight;
    }
  }, [messages, busy, phase, error]);

  function start() {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(true); setError(null); setCanRetry(false);
    return true;
  }
  function finish() { busyRef.current = false; setBusy(false); }
  function handleError(value: unknown, retryMessage = false) {
    const failure = value instanceof ApiError ? value : new ApiError("unexpected", "Não foi possível concluir esta etapa. Tente novamente.");
    setError(failure);
    if (failure.status === 404 || failure.status === 401) {
      session.current = null; setPhase("expired");
    } else {
      if (failure.registered) {
        setPhase("active");
        if (phase === "registration") setMessages(previous => [...previous, { role: "assistant", text: "Seus contatos foram conferidos. Sua pergunta está guardada; você pode tentar novamente sem repetir o cadastro." }]);
      }
      setCanRetry(failure.code !== "api_not_configured" && (retryMessage || failure.registered));
    }
    return failure;
  }
  function accept(result: ApiResponse) {
    const additions: Message[] = [];
    if (result.registration) additions.push({ role: "assistant", text: result.registration.message, protocol: result.registration.registration_id });
    if (result.answer) {
      additions.push({ role: "assistant", text: result.answer.text, sources: result.answer.sources });
      pending.current = null;
    }
    if (additions.length) setMessages(previous => [...previous, ...additions]);
    setPhase(result.code === "registration_required" ? "registration" : "active");
  }
  async function ask(question: string, retry = false) {
    question = question.trim();
    if (!question || question.length > 4000 || !start()) return;
    pending.current = question;
    if (!retry) { setMessages(previous => [...previous, { role: "user", text: question }]); setDraft(""); }
    try {
      if (!session.current) {
        session.current = await openSession();
        setNotice(session.current.privacy_notice);
      }
      accept(await sendMessage(session.current, question));
    } catch (value) { handleError(value, true); }
    finally { finish(); }
  }
  async function register(contacts: Contacts): Promise<"done" | "retry" | "edit"> {
    if (!session.current || !start()) return "retry";
    try { accept(await confirmContacts(session.current, contacts)); return "done"; }
    catch (value) {
      const failure = handleError(value);
      return ["invalid_registration", "invalid_request"].includes(failure.code) ? "edit" : "retry";
    } finally { finish(); }
  }
  async function clear() {
    if (!session.current || !start()) return;
    try {
      await clearContext(session.current);
      pending.current = null; setMessages([{ ...greeting, text: "Conversa reiniciada. Como posso ajudar? Seus contatos já foram conferidos nesta sessão." }]);
    } catch (value) { handleError(value); }
    finally { finish(); }
  }
  async function close() {
    if (!start()) return;
    try {
      if (session.current) await closeSession(session.current);
      session.current = null; pending.current = null;
      setMessages([greeting, { role: "assistant", text: "Atendimento encerrado. Quando quiser, a gente continua em uma nova conversa." }]);
      setPhase("ended");
    } catch (value) { handleError(value); }
    finally { finish(); }
  }
  function restart() {
    session.current = null; pending.current = null;
    setMessages([greeting]); setPhase("ready"); setError(null); setCanRetry(false); setNotice(""); setDraft("");
    input.current?.focus();
  }
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void ask(draft); }
  const closed = phase === "ended" || phase === "expired";
  const composerDisabled = busy || phase === "registration" || closed || pending.current !== null;

  return <div className="chat-shell" aria-label="Atendimento da Empório da Música">
    <div className="chat-topbar"><div className="chat-identity"><MusicMark/><div><h3>Vamos encontrar seu som.</h3><p>Assistente da Empório da Música</p></div></div><span className="ai-tag">COM IA</span></div>
    <div className="chat-toolbar"><span><i aria-hidden="true"/>{busy ? "Preparando sua resposta" : phase === "registration" ? "Aguardando sua confirmação" : closed ? "Conversa encerrada" : "Um espaço para suas perguntas"}</span>
      <div>{phase === "active" ? <button type="button" disabled={busy} onClick={clear}>Limpar contexto</button> : null}{phase !== "ready" && !closed ? <button type="button" disabled={busy} onClick={close}>Encerrar</button> : null}</div>
    </div>
    <div className="chat-log" ref={log} role="log" aria-label="Histórico da conversa" aria-live="polite" aria-relevant="additions">
      <p className="chat-date">O PRIMEIRO PASSO PODE SER UMA PERGUNTA</p>
      {messages.map((message, index) => <article key={index} className={`message message-${message.role}`}>
        <span className="message-author">{message.role === "assistant" ? "EMPÓRIO" : "VOCÊ"}</span>
        <div className="message-bubble"><p>{message.text}</p>{message.protocol ? <p className="protocol">Protocolo de cadastro: <span>{message.protocol}</span></p> : null}
          {message.sources?.length ? <SourceDetails sources={message.sources}/> : null}</div>
      </article>)}
      {phase === "registration" ? <RegistrationForm notice={notice} busy={busy} onConfirm={register} onCancel={close}/> : null}
      {busy ? <div className="thinking" role="status"><span className="thinking-bars" aria-hidden="true"><i/><i/><i/><i/></span>{phase === "registration" ? "Conferindo seus dados e preparando a resposta…" : "Ouvindo sua pergunta e consultando as fontes…"}</div> : null}
      {error ? <div className="chat-error" role="alert" aria-label="Erro no atendimento"><p>{error.message}{error.retryAfter ? ` Aguarde ${error.retryAfter} segundos antes de tentar.` : ""}</p>
        {canRetry && !closed ? <button type="button" className="text-button" disabled={busy} onClick={() => pending.current && void ask(pending.current, true)}>Tentar novamente</button> : null}</div> : null}
      {closed ? <button className="button-dark new-conversation" type="button" onClick={restart}>Abrir nova conversa<ArrowIcon/></button> : null}
    </div>
    {phase === "ready" && !pending.current ? <div className="starter-questions" aria-label="Sugestões de perguntas">{starters.map(question => <button key={question} type="button" disabled={busy} onClick={() => void ask(question)}>{question}<span aria-hidden="true">↗</span></button>)}</div> : null}
    <form className="chat-composer" onSubmit={submit} aria-label="Enviar pergunta">
      <label className="sr-only" htmlFor="chat-question">Sua pergunta</label>
      <textarea ref={input} id="chat-question" name="message" rows={2} maxLength={4000} disabled={composerDisabled} value={draft} onChange={event => setDraft(event.target.value)} placeholder={phase === "registration" ? "Confirme seus dados acima para continuar…" : closed ? "Abra uma nova conversa para continuar…" : "Conte: qual vai ser o seu próximo som?"} onKeyDown={event => {
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!composerDisabled) void ask(draft); }
      }}/>
      <button type="submit" className="send-button" aria-label="Enviar pergunta" disabled={composerDisabled || !draft.trim()}><ArrowIcon/></button>
    </form>
    <div className="chat-footnote"><ShieldIcon/><p>Seus contatos são conferidos antes da resposta. Preços e estoque refletem a base consultada.</p></div>
  </div>;
}

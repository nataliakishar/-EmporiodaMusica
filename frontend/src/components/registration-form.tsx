"use client";
import { useState, type FormEvent } from "react";
import type { Contacts } from "@/lib/api";
import { ArrowIcon, ShieldIcon } from "./icons";

type Props = {
  notice: string;
  busy: boolean;
  onConfirm: (contacts: Contacts) => Promise<"done" | "retry" | "edit">;
  onCancel: () => void;
};

export function RegistrationForm({ notice, busy, onConfirm, onCancel }: Props) {
  const [contacts, setContacts] = useState<Contacts>({ name: "", phone: "", email: "" });
  const [review, setReview] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [locked, setLocked] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!review) { setReview(true); return; }
    if (!confirmed || busy) return;
    setLocked(true);
    const result = await onConfirm(contacts);
    if (result === "edit") { setLocked(false); setReview(false); setConfirmed(false); }
  }
  return <section className="registration-card" aria-label="Cadastro para continuar">
    <div className="registration-heading"><ShieldIcon/><span>ANTES DO PRÓXIMO ACORDE</span></div>
    <h4>{review ? "Está tudo certinho?" : "Vamos nos conhecer?"}</h4>
    <p className="privacy-notice">{notice}</p>
    <form onSubmit={submit}>
      {review ? <>
        <dl className="contact-review">
          <div><dt>Nome</dt><dd>{contacts.name}</dd></div>
          <div><dt>Telefone</dt><dd>{contacts.phone}</dd></div>
          <div><dt>E-mail</dt><dd>{contacts.email}</dd></div>
        </dl>
        <label className="consent-label"><input type="checkbox" checked={confirmed} disabled={busy || locked} required onChange={event => setConfirmed(event.target.checked)}/><span>Conferi meus dados e confirmo o envio à Empório da Música para este atendimento.</span></label>
        {locked && !busy ? <p className="retry-note">Para conferir a tentativa anterior com segurança, o reenvio usará os mesmos dados.</p> : null}
      </> : <div className="contact-fields">
        <label>Como podemos chamar você?<input name="name" autoComplete="name" value={contacts.name} minLength={2} maxLength={120} required disabled={busy} onChange={event => setContacts({ ...contacts, name: event.target.value })} placeholder="Seu nome"/></label>
        <div className="contact-row"><label>Telefone com DDD<input name="phone" type="tel" autoComplete="tel" value={contacts.phone} maxLength={40} required disabled={busy} onChange={event => setContacts({ ...contacts, phone: event.target.value })} placeholder="(85) 90000-0000"/></label>
        <label>E-mail<input name="email" type="email" autoComplete="email" value={contacts.email} maxLength={254} required disabled={busy} onChange={event => setContacts({ ...contacts, email: event.target.value })} placeholder="voce@exemplo.com"/></label></div>
      </div>}
      <div className="registration-actions">
        <button className="button-dark" type="submit" disabled={busy || (review && !confirmed)}>{busy ? "Conferindo e retomando…" : review ? locked ? "Tentar confirmar novamente" : "Confirmar e continuar" : "Revisar meus dados"}<ArrowIcon/></button>
        {review && !locked ? <button className="text-button" type="button" disabled={busy} onClick={() => { setReview(false); setConfirmed(false); }}>Editar dados</button> : null}
        <button className="text-button muted" type="button" disabled={busy} onClick={onCancel}>Encerrar atendimento</button>
      </div>
    </form>
    <p className="registration-footnote">O cadastro não libera acesso a pedidos nem autoriza publicidade.</p>
  </section>;
}

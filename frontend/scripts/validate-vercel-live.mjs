/** Um único atendimento real em produção. Cria um cadastro sintético.
 * A remoção do cadastro deve ser confirmada administrativamente por ID e marcador.
 * Não executar automaticamente em cada ajuste: consome Groq e grava no Supabase.
 */
import { chromium, expect } from "@playwright/test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const artifacts = path.join(root, "python-agent/.runtime/frontend");
const target = path.join(root, "python-agent/reports/vercel_live_validation.json");
const web = "https://emporio-da-musica-five.vercel.app";
const api = "https://emporio-da-musica-api.vercel.app";
const marker = randomUUID().replaceAll("-", "");
const fixture = { name: "Vercel Integration " + marker, phone: "(85) 90000-0000", email: "vercel-" + marker + "@example.invalid" };
const report = { recorded_at_utc: new Date().toISOString(), passed: false, web, api,
  fixture_name: fixture.name, fixture_email: fixture.email, fixture_removed: false,
  remote_groq_questions: 0, checks: {}, session_cleanup: [] };
const sessions = []; // tokens somente em memória, nunca no relatório
const sessionCaptures = [];
let browser;
await mkdir(artifacts, { recursive: true });
await mkdir(path.dirname(target), { recursive: true });
const save = () => writeFile(target, JSON.stringify(report, null, 2) + "\n");
await save();

async function request(method, endpoint, payload, session) {
  const response = await fetch(api + endpoint, {
    method, headers: { "Content-Type": "application/json", ...(session ? { Authorization: "Bearer " + session.session_token } : {}) },
    body: payload ? JSON.stringify(payload) : undefined, signal: AbortSignal.timeout(240_000),
  });
  return { status: response.status, data: await response.json() };
}

try {
  const health = await request("GET", "/health");
  if (health.status !== 200 || health.data.session_storage !== "supabase") throw new Error("A API de produção não respondeu com sessões compartilhadas.");
  report.checks.api_health = true;
  browser = await chromium.launch({ channel: "msedge", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
  page.setDefaultTimeout(30_000);
  page.setDefaultNavigationTimeout(60_000);
  const failures = [];
  page.on("pageerror", error => failures.push(error.name));
  page.on("response", response => {
    if (response.url() === api + "/sessions" && response.request().method() === "POST") {
      sessionCaptures.push(response.json().then(data => { if (data.session_id && data.session_token) sessions.push(data); }));
    }
  });
  const response = await page.goto(web, { waitUntil: "networkidle" });
  if (response.status() !== 200) throw new Error("O site público não respondeu com sucesso.");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("O seu próximo");
  report.checks.public_frontend = true;
  await page.getByRole("link", { name: "Encontre o seu som" }).click();
  await page.getByLabel("Sua pergunta", { exact: true }).fill("Quanto custa o Takamine GD20?");
  const gate = page.waitForResponse(r => r.url().startsWith(api + "/sessions/") && r.url().endsWith("/messages"));
  await page.getByRole("button", { name: "Enviar pergunta", exact: true }).click();
  if ((await gate).status() !== 202) throw new Error("A pergunta não aguardou o cadastro.");
  const card = page.getByRole("region", { name: "Cadastro para continuar" });
  await expect(card).toContainText("LGPD");
  report.checks.production_cors_and_gate = true;
  await card.getByLabel("Como podemos chamar você?").fill(fixture.name);
  await card.getByLabel("Telefone com DDD").fill(fixture.phone);
  await card.getByLabel("E-mail", { exact: true }).fill(fixture.email);
  await card.getByRole("button", { name: "Revisar meus dados" }).click();
  await card.getByRole("checkbox").check();
  report.remote_groq_questions = 1;
  await save();
  const answered = page.waitForResponse(r => r.url().startsWith(api + "/sessions/") && r.url().endsWith("/registration"), { timeout: 240_000 });
  await card.getByRole("button", { name: "Confirmar e continuar", exact: true }).click();
  const registered = await answered;
  const data = await registered.json();
  if (data.registration?.registration_id) { report.fixture_id = data.registration.registration_id; await save(); }
  if (registered.status() !== 200 || data.code !== "answered") {
    report.safe_api_error_code = data.code;
    throw new Error("A API não concluiu a resposta real. Consulte o código seguro no relatório.");
  }
  if (data.registration?.code !== "registration_saved") throw new Error("Cadastro sintético novo não confirmado.");
  report.checks.new_customer_confirmed = true;
  const csv = await readFile(path.join(root, "data/desafio_tecnico_ai_eng - products.csv"), "utf8");
  const row = csv.split(/\r?\n/).find(line => line.includes("Takamine GD20 Dreadnought Natural"));
  const price = Number(row.split(",")[1].replaceAll('"', ""));
  const expected = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(price).replace(/\s+/g, " ");
  if (!data.answer.text.replace(/\s+/g, " ").includes(expected) || !data.answer.tools.length || !data.answer.sources.length) throw new Error("Preço ou fontes não conferem com o CSV.");
  await expect(page.getByText(data.answer.text, { exact: true })).toBeVisible();
  report.checks.real_llm_answer_matches_csv = true;
  report.answer = data.answer;
  await page.screenshot({ path: path.join(artifacts, "vercel-live-desktop.png"), fullPage: true });
  // Confere retorno cadastral em outra sessão, sem enviar outra pergunta ao LLM.
  const returning = await request("POST", "/sessions");
  if (returning.status !== 201) throw new Error("Não foi possível abrir a sessão de retorno.");
  sessions.push(returning.data);
  const existing = await request("POST", `/sessions/${returning.data.session_id}/registration`, { ...fixture, confirmed: true }, returning.data);
  if (existing.status !== 200 || existing.data.registration?.code !== "registration_existing" || existing.data.registration.registration_id) throw new Error("Retorno cadastral não reconhecido corretamente.");
  report.checks.existing_customer_recognized = true;
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, reducedMotion: "reduce" });
  await mobile.goto(web, { waitUntil: "networkidle" });
  if (!await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth)) throw new Error("Rolagem lateral no celular.");
  await mobile.screenshot({ path: path.join(artifacts, "vercel-live-mobile.png"), fullPage: true });
  report.checks.mobile_layout = true;
  report.checks.no_browser_runtime_errors = failures.length === 0;
  if (failures.length) throw new Error("Erro de execução na interface.");
  report.passed = true;
} catch (error) {
  report.error = error instanceof Error ? error.message : "Falha na integração de produção.";
  process.exitCode = 1;
} finally {
  await Promise.allSettled(sessionCaptures);
  for (const session of sessions) {
    try {
      const closed = await request("DELETE", `/sessions/${session.session_id}`, undefined, session);
      report.session_cleanup.push({ session_id: session.session_id, closed: closed.status === 200 });
    } catch { report.session_cleanup.push({ session_id: session.session_id, closed: false }); }
  }
  if (browser) await browser.close();
  await save();
  console.log(JSON.stringify({ passed: report.passed, checks: report.checks,
    remote_groq_questions: report.remote_groq_questions, fixture_removed: report.fixture_removed,
    safe_api_error_code: report.safe_api_error_code, error: report.error }));
}

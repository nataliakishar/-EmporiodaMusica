/** Verifica somente página + entrada cadastral contra a API local real.
 * Não confirma contatos, não chama o modelo e não grava cadastros.
 * Requer npm run build e a API normal aberta na porta 8000.
 */
import { chromium, expect } from "@playwright/test";
import { spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const artifacts = path.resolve(root, "../python-agent/.runtime/frontend");
await mkdir(artifacts, { recursive: true });
const report = { passed: false, confirmed_registrations: 0, remote_llm_questions: 0, checks: {} };
let server;
let browser;
const log = createWriteStream(path.join(artifacts, "production-server.log"));

try {
  const health = await fetch("http://127.0.0.1:8000/health", { signal: AbortSignal.timeout(4000) });
  if (!health.ok || (await health.json()).session_storage !== "memory") throw new Error("Abra a API deste projeto na porta 8000 antes da verificação.");
  await new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.once("error", () => reject(new Error("A porta 3000 já está em uso; o processo existente foi preservado.")));
    probe.listen(3000, "127.0.0.1", () => probe.close(resolve));
  });
  server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"], {
    cwd: root, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
  });
  server.stdout.pipe(log, { end: false });
  server.stderr.pipe(log, { end: false });
  const deadline = Date.now() + 30000;
  while (true) {
    try {
      const response = await fetch("http://127.0.0.1:3000", { signal: AbortSignal.timeout(2000) });
      if (response.ok) break;
    } catch { /* inicialização do processo próprio */ }
    if (Date.now() > deadline || server.exitCode !== null) throw new Error("O frontend de produção não iniciou.");
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  browser = await chromium.launch({ channel: "msedge", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
  const consoleErrors = [];
  page.on("pageerror", error => consoleErrors.push(error.name));
  await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Ir para o atendimento", exact: true })).toBeFocused();
  report.checks.keyboard_skip_link = true;
  await page.getByRole("heading", { level: 1 }).click();
  await page.screenshot({ path: path.join(artifacts, "desktop.png"), fullPage: true });
  report.checks.production_page = true;
  await page.getByRole("link", { name: "Encontre o seu som" }).click();
  await page.getByLabel("Sua pergunta", { exact: true }).fill("Quanto custa o Takamine GD20?");
  const gateResponse = page.waitForResponse(response => response.url().startsWith("http://127.0.0.1:8000/sessions/") && response.url().endsWith("/messages"));
  await page.getByRole("button", { name: "Enviar pergunta", exact: true }).click();
  if ((await gateResponse).status() !== 202) throw new Error("A API não manteve o bloqueio cadastral esperado.");
  await expect(page.getByRole("region", { name: "Cadastro para continuar" })).toContainText("LGPD");
  await page.screenshot({ path: path.join(artifacts, "registration.png"), fullPage: true });
  report.checks.production_ui_to_real_api_gate = true;
  const closed = page.waitForResponse(response => response.request().method() === "DELETE" && response.url().startsWith("http://127.0.0.1:8000/sessions/"));
  await page.getByRole("button", { name: "Encerrar atendimento", exact: true }).click();
  if ((await closed).status() !== 200) throw new Error("Não foi possível encerrar a sessão sintética.");
  report.checks.real_session_closed_without_registration = true;
  await expect(page.getByRole("button", { name: "Abrir nova conversa" })).toBeVisible();
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: "reduce" });
  await mobile.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
  await mobile.evaluate(() => document.fonts.ready);
  if (!await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth)) throw new Error("Rolagem lateral inesperada no celular.");
  await mobile.screenshot({ path: path.join(artifacts, "mobile.png"), fullPage: true });
  report.checks.mobile_production_layout = true;
  report.checks.no_browser_runtime_errors = consoleErrors.length === 0;
  if (consoleErrors.length) throw new Error("Erro de execução no navegador.");
  report.passed = true;
} catch (error) {
  report.error = error instanceof Error ? error.message : "Falha na verificação local.";
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  if (server && server.exitCode === null) {
    server.kill(); // apenas o servidor Next iniciado por este script; API existente preservada
    await new Promise(resolve => { server.once("exit", resolve); setTimeout(resolve, 5000).unref(); });
  }
  log.end();
  await writeFile(path.join(artifacts, "production-check.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report));
}

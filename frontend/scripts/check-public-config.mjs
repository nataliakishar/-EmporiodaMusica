/** Teste focado do build público sem API configurada; nenhum serviço real é chamado. */
import { chromium, expect } from "@playwright/test";
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const local = "http://127.0.0.1:3200";
const publicOrigin = "https://emporio-publicacao.example.invalid";
const output = path.resolve(root, "../python-agent/.runtime/frontend/vercel-config-check.json");
const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3200"], {
  cwd: root, windowsHide: true, stdio: "ignore", env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
});
let browser;
const report = { passed: false, public_loopback_requests: 0, public_guard: false, local_api_preserved: false };
try {
  const deadline = Date.now() + 30000;
  while (true) {
    if (server.exitCode !== null) throw new Error("Servidor de teste não iniciou; verifique a porta 3200.");
    try { if ((await fetch(local, { signal: AbortSignal.timeout(1000) })).ok) break; } catch { /* iniciando */ }
    if (Date.now() > deadline) throw new Error("Timeout de inicialização.");
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  browser = await chromium.launch({ channel: "msedge", headless: true });
  const page = await browser.newPage();
  page.on("request", request => { if (request.url().startsWith("http://127.0.0.1:8000")) report.public_loopback_requests++; });
  // Origem pública simulada no navegador; HTML/assets continuam no servidor local próprio.
  await page.route(publicOrigin + "/**", async route => {
    const url = new URL(route.request().url());
    await route.fulfill({ response: await route.fetch({ url: local + url.pathname + url.search }) });
  });
  await page.goto(publicOrigin);
  await page.getByLabel("Sua pergunta", { exact: true }).fill("Quanto custa o Takamine GD20?");
  await page.getByRole("button", { name: "Enviar pergunta", exact: true }).click();
  await expect(page.getByRole("alert", { name: "Erro no atendimento" })).toContainText("atendimento online está em preparação");
  await expect(page.getByRole("button", { name: "Tentar novamente", exact: true })).toHaveCount(0);
  if (report.public_loopback_requests !== 0) throw new Error("Site público tentou consultar localhost.");
  report.public_guard = true;
  const localPage = await browser.newPage();
  await localPage.route("http://127.0.0.1:8000/sessions", route => route.fulfill({ status: 503, contentType: "application/json",
    headers: { "Access-Control-Allow-Origin": local }, body: JSON.stringify({ code: "test_fixture", message: "API local de teste alcançada." }) }));
  await localPage.goto(local);
  await localPage.getByLabel("Sua pergunta", { exact: true }).fill("Olá");
  await localPage.getByRole("button", { name: "Enviar pergunta", exact: true }).click();
  await expect(localPage.getByRole("alert", { name: "Erro no atendimento" })).toContainText("API local de teste alcançada");
  report.local_api_preserved = true;
  report.passed = true;
} catch (error) {
  report.error = error instanceof Error ? error.message : "Falha na verificação.";
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  if (server.exitCode === null) {
    server.kill();
    await new Promise(resolve => { server.once("exit", resolve); setTimeout(resolve, 5000).unref(); });
  }
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report));
}

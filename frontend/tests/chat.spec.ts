import { test, expect, type Page } from "@playwright/test";

const question = "Quanto custa o Takamine GD20?";
const testAnswer = (value: string) => "Resposta de teste da interface. Sua pergunta foi: " + value;

async function ask(page: Page, value = question) {
  await page.getByLabel("Sua pergunta", { exact: true }).fill(value);
  await page.getByRole("button", { name: "Enviar pergunta", exact: true }).click();
}
async function register(page: Page, email = `interface-${Date.now()}@example.invalid`) {
  const card = page.getByRole("region", { name: "Cadastro para continuar" });
  await expect(card).toBeVisible();
  await card.getByLabel("Como podemos chamar você?").fill("Pessoa Sintetica Interface");
  await card.getByLabel("Telefone com DDD").fill("(85) 90000-0000");
  await card.getByLabel("E-mail", { exact: true }).fill(email);
  await card.getByRole("button", { name: "Revisar meus dados" }).click();
  await card.getByRole("checkbox").check();
  await card.getByRole("button", { name: "Confirmar e continuar", exact: true }).click();
  await expect(card).toHaveCount(0);
  return email;
}

test("página original, navegação, movimento e ausência de envio ao abrir", async ({ page }) => {
  const errors: string[] = [];
  const apiCalls: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => { if (request.url().startsWith("http://127.0.0.1:8765")) apiCalls.push(request.url()); });
  await page.goto("/");
  await expect(page).toHaveTitle(/Empório da Música/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("O seu próximo");
  await expect(page.getByRole("img", { name: /Composição ilustrada/ })).toBeVisible();
  await page.getByRole("button", { name: "Pausar movimento" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  expect(await page.locator(".floating-guitar").evaluate(element => getComputedStyle(element).animationPlayState)).toBe("paused");
  await page.screenshot({ path: "test-results/desktop.png", fullPage: true });
  await page.getByRole("link", { name: "Encontre o seu som" }).click();
  await expect(page.getByLabel("Sua pergunta", { exact: true })).toBeVisible();
  expect(apiCalls).toEqual([]);
  expect(errors).toEqual([]);
});

test("pergunta → revisão explícita → cadastro → resposta → continuidade e fontes", async ({ page }) => {
  let registrations = 0;
  const contactBodies: unknown[] = [];
  page.on("request", request => {
    if (request.url().endsWith("/registration")) { registrations++; contactBodies.push(request.postDataJSON()); }
  });
  await page.goto("/#atendimento");
  await ask(page);
  const card = page.getByRole("region", { name: "Cadastro para continuar" });
  await expect(card).toContainText("LGPD");
  await expect(page.getByLabel("Sua pergunta", { exact: true })).toBeDisabled();
  await card.getByLabel("Como podemos chamar você?").fill("Pessoa Sintetica Interface");
  await card.getByLabel("Telefone com DDD").fill("(85) 90000-0000");
  await card.getByLabel("E-mail", { exact: true }).fill(`complete-${Date.now()}@example.invalid`);
  await card.getByRole("button", { name: "Revisar meus dados" }).click();
  expect(registrations).toBe(0);
  await expect(card.getByRole("button", { name: "Confirmar e continuar", exact: true })).toBeDisabled();
  await expect(card).toContainText("Pessoa Sintetica Interface");
  await page.screenshot({ path: "test-results/registration-review.png", fullPage: true });
  await card.getByRole("checkbox").check();
  await card.getByRole("button", { name: "Confirmar e continuar", exact: true }).click();
  await expect(page.getByText(testAnswer(question), { exact: true })).toBeVisible();
  expect(registrations).toBe(1);
  expect(contactBodies[0]).toMatchObject({ confirmed: true });
  await expect(page.getByText("Protocolo de cadastro:", { exact: false })).toBeVisible();
  await page.getByText("Consultar fontes desta resposta").click();
  await expect(page.getByText("desafio_tecnico_ai_eng - products.csv", { exact: true })).toBeVisible();
  await ask(page, "Esse modelo está disponível?");
  await expect(page.getByText(testAnswer("Esse modelo está disponível?"), { exact: true })).toBeVisible();
  expect(registrations).toBe(1);
  await expect(card).toHaveCount(0);
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
  await page.getByRole("button", { name: "Limpar contexto", exact: true }).click();
  await expect(page.getByText(/Conversa reiniciada/)).toBeVisible();
  await ask(page, "E ukuleles?");
  await expect(page.getByText(testAnswer("E ukuleles?"), { exact: true })).toBeVisible();
  expect(registrations).toBe(1);
});

test("reconhece contatos existentes em uma nova conversa sem expor protocolo antigo", async ({ page }) => {
  await page.goto("/#atendimento");
  await ask(page);
  const email = await register(page);
  await expect(page.getByText(testAnswer(question), { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Encerrar", exact: true }).click();
  await page.getByRole("button", { name: "Abrir nova conversa" }).click();
  await ask(page);
  await register(page, email);
  await expect(page.getByText(/Obrigado por retornar à Empório da Música/)).toBeVisible();
  await expect(page.getByText("Protocolo de cadastro:", { exact: false })).toHaveCount(0);
});

test("cancelamento antes da confirmação não envia os contatos", async ({ page }) => {
  let registrations = 0;
  page.on("request", request => { if (request.url().endsWith("/registration")) registrations++; });
  await page.goto("/#atendimento");
  await ask(page);
  await page.getByRole("button", { name: "Encerrar atendimento", exact: true }).click();
  await expect(page.getByRole("button", { name: "Abrir nova conversa" })).toBeVisible();
  expect(registrations).toBe(0);
});

test("falha de rede oferece tentativa explícita sem duplicar a pergunta", async ({ page }) => {
  let attempts = 0;
  await page.route("http://127.0.0.1:8765/sessions", route => {
    attempts++;
    return attempts === 1 ? route.abort("failed") : route.continue();
  });
  await page.goto("/#atendimento");
  await ask(page);
  await expect(page.getByRole("alert", { name: "Erro no atendimento" })).toContainText("Nenhum reenvio foi feito automaticamente");
  expect(attempts).toBe(1);
  await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
  await expect(page.getByRole("region", { name: "Cadastro para continuar" })).toBeVisible();
  expect(attempts).toBe(2);
  await expect(page.locator(".message-user")).toHaveCount(1);
});

test("cota do provedor preserva cadastro e permite retomar a pergunta pendente", async ({ page }) => {
  await page.goto("/#atendimento");
  await ask(page);
  await register(page);
  await expect(page.getByText(testAnswer(question), { exact: true })).toBeVisible();
  let attempts = 0;
  await page.route("**/messages", route => {
    attempts++;
    return attempts === 1 ? route.fulfill({ status: 429, contentType: "application/json",
      headers: { "Retry-After": "30", "Access-Control-Allow-Origin": "http://127.0.0.1:3100", "Access-Control-Expose-Headers": "Retry-After" },
      body: JSON.stringify({ code: "provider_rate_limit", message: "O provedor atingiu sua cota.", registration_confirmed: true, pending_message_saved: true }) }) : route.continue();
  });
  await ask(page, "E o estoque?");
  await expect(page.getByRole("alert", { name: "Erro no atendimento" })).toContainText("30 segundos");
  expect(attempts).toBe(1);
  await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
  await expect(page.getByText(testAnswer("E o estoque?"), { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Cadastro para continuar" })).toHaveCount(0);
  expect(attempts).toBe(2);
});

test("sessão expirada oferece reinício sem liberar o cadastro pelo navegador", async ({ page }) => {
  await page.route("**/messages", route => route.fulfill({ status: 404, contentType: "application/json",
    headers: { "Access-Control-Allow-Origin": "http://127.0.0.1:3100" },
    body: JSON.stringify({ code: "session_not_found", message: "Sessão inexistente ou expirada." }) }));
  await page.goto("/#atendimento");
  await ask(page);
  await expect(page.getByRole("alert", { name: "Erro no atendimento" })).toContainText("expirada");
  await page.getByRole("button", { name: "Abrir nova conversa" }).click();
  await expect(page.getByLabel("Sua pergunta", { exact: true })).toBeEnabled();
});

test("recupera envio cadastral incerto e falha de resposta sem cadastrar novamente", async ({ page }) => {
  let attempts = 0;
  const bodies: unknown[] = [];
  await page.route("**/registration", async route => {
    attempts++;
    bodies.push(route.request().postDataJSON());
    if (attempts > 1) await route.fetch(); // aplica a confirmação na API local de teste
    await route.fulfill({ status: 502, contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": "http://127.0.0.1:3100" },
      body: JSON.stringify(attempts === 1
        ? { code: "registration_unavailable", message: "Não foi possível confirmar o cadastro." }
        : { code: "answer_unavailable", message: "Não foi possível responder agora.", registration_confirmed: true, pending_message_saved: true }) });
  });
  await page.goto("/#atendimento");
  await ask(page);
  const card = page.getByRole("region", { name: "Cadastro para continuar" });
  await card.getByLabel("Como podemos chamar você?").fill("Pessoa Sintetica Recuperacao");
  await card.getByLabel("Telefone com DDD").fill("(85) 90000-0000");
  await card.getByLabel("E-mail", { exact: true }).fill(`recovery-${Date.now()}@example.invalid`);
  await card.getByRole("button", { name: "Revisar meus dados" }).click();
  await card.getByRole("checkbox").check();
  await card.getByRole("button", { name: "Confirmar e continuar", exact: true }).click();
  await expect(page.getByRole("alert", { name: "Erro no atendimento" })).toContainText("confirmar o cadastro");
  await expect(page.getByLabel("Sua pergunta", { exact: true })).toBeDisabled();
  await expect(card.getByRole("button", { name: "Editar dados" })).toHaveCount(0);
  expect(attempts).toBe(1);
  await card.getByRole("button", { name: "Tentar confirmar novamente" }).click();
  await expect(page.getByText(/Seus contatos foram conferidos/)).toBeVisible();
  await expect(card).toHaveCount(0);
  await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
  await expect(page.getByText(testAnswer(question), { exact: true })).toBeVisible();
  expect(attempts).toBe(2);
  expect(bodies[0]).toEqual(bodies[1]);
});

test("celular, movimento reduzido e cadastro acessível sem rolagem lateral", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.locator(".floating-guitar").evaluate(element => getComputedStyle(element).animationName)).toBe("none");
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  await page.getByRole("link", { name: "Encontre o seu som" }).click();
  await page.getByRole("button", { name: /Quais violões custam/ }).click();
  await register(page);
  await expect(page.getByText(testAnswer("Quais violões custam até R$ 1.000?"), { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

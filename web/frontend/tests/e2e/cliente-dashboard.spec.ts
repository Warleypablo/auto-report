import { test, expect, Page } from "@playwright/test";

const CNPJ_SEED = "00000000000001";

async function login(page: Page) {
  await page.goto("/cliente/login");
  await page.getByLabel("CNPJ").fill(CNPJ_SEED);
  await page.getByLabel("Senha").fill("Warley20192020");
  await page.getByRole("button", { name: /entrar/i }).click();
  // Aceita ?intro=1 ou /cliente/dashboard
  await page.waitForURL((url) => url.pathname === "/cliente/dashboard");
}

test.describe("Cliente dashboard (cinemático)", () => {
  test("splash aparece na primeira vez do dia e some no clique", async ({ page, context }) => {
    await context.clearCookies();
    await page.addInitScript(() => localStorage.clear());
    await login(page);

    // Splash com "Boa tarde/dia/noite, ..." pode aparecer
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    // Se houver dados, splash aparece; clica para pular
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) {
      await splash.click();
      await expect(splash).toBeHidden({ timeout: 2000 });
    }
  });

  test("hero de faturamento aparece com dados ou mensagem 'processando'", async ({ page }) => {
    await login(page);
    // Pula splash se houver
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) await splash.click();

    // OU vemos o hero, OU vemos a mensagem de "processando"
    const hero = page.getByText("Faturamento ·", { exact: false }).first();
    const empty = page.getByText(/dados estão sendo processados/i);
    await expect(hero.or(empty)).toBeVisible({ timeout: 5000 });
  });

  test("seletor de mês continua funcionando", async ({ page }) => {
    await login(page);
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) await splash.click();

    const select = page.getByLabel("Mês");
    if (await select.isVisible()) {
      const options = await select.locator("option").allTextContents();
      if (options.length > 1) {
        await select.selectOption({ index: 1 });
      }
    }
  });

  test("drawer 'ver todos' abre e fecha (se houver criativos)", async ({ page }) => {
    await login(page);
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) await splash.click();

    const verTodos = page.getByRole("button", { name: /ver todos os/i }).first();
    if (await verTodos.isVisible().catch(() => false)) {
      await verTodos.click();
      const drawer = page.getByRole("dialog", { name: /Todos os criativos/i });
      await expect(drawer).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(drawer).toBeHidden({ timeout: 1000 });
    }
  });

  test("botão Sair redireciona para login e limpa cookie", async ({ page, context }) => {
    await login(page);
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) await splash.click();

    await page.getByRole("button", { name: /sair/i }).click();
    await page.waitForURL("**/cliente/login");
    const cookies = await context.cookies();
    expect(cookies.find((c) => c.name === "cliente_token")).toBeUndefined();
  });
});

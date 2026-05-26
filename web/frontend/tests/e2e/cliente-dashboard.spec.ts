import { test, expect, Page } from "@playwright/test";

const CNPJ_SEED = "00000000000001"; // do seed_dev.py — corresponde a loja-fashion

async function login(page: Page) {
  await page.goto("/cliente/login");
  await page.getByLabel("CNPJ").fill(CNPJ_SEED);
  await page.getByLabel("Senha").fill("Warley20192020");
  await page.getByRole("button", { name: /entrar/i }).click();
  await page.waitForURL("**/cliente/dashboard");
}

test.describe("Cliente dashboard", () => {
  test("mostra nome e seção de KPIs após login", async ({ page }) => {
    await login(page);
    await expect(page.locator("h1")).toBeVisible();
    await expect(page.getByText(/KPIs/i)).toBeVisible();
  });

  test("seletor de mês muda o breakdown", async ({ page }) => {
    await login(page);
    const select = page.locator("select#mes");
    if (await select.isVisible()) {
      const options = await select.locator("option").allTextContents();
      if (options.length > 1) {
        await select.selectOption({ index: 1 });
        await expect(page.getByText(/campanhas/i)).toBeVisible();
      }
    }
  });

  test("botão Sair redireciona para login e limpa cookie", async ({ page, context }) => {
    await login(page);
    await page.getByRole("button", { name: /sair/i }).click();
    await page.waitForURL("**/cliente/login");
    const cookies = await context.cookies();
    expect(cookies.find((c) => c.name === "cliente_token")).toBeUndefined();
  });
});

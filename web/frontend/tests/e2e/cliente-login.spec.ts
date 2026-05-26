import { test, expect } from "@playwright/test";

test.describe("Cliente login", () => {
  test("renderiza form de CNPJ", async ({ page }) => {
    await page.goto("/cliente/login");
    await expect(page.getByLabel("CNPJ")).toBeVisible();
    await expect(page.getByRole("button", { name: /entrar/i })).toBeVisible();
  });

  test("CNPJ inválido mostra mensagem de erro", async ({ page }) => {
    await page.goto("/cliente/login");
    await page.getByLabel("CNPJ").fill("99999999000199");
    await page.getByRole("button", { name: /entrar/i }).click();
    // Filtra pelo paragraph role=alert do form (evita conflito com
    // __next-route-announcer__ que também usa role=alert)
    await expect(page.locator("p[role=alert]")).toContainText(
      /não encontrado|não disponível|inativa|múltiplas/i,
    );
  });

  test("CNPJ válido redireciona para /cliente/dashboard", async ({ page }) => {
    await page.goto("/cliente/login");
    await page.getByLabel("CNPJ").fill("00000000000001");
    await page.getByRole("button", { name: /entrar/i }).click();
    await page.waitForURL("**/cliente/dashboard", { timeout: 5000 });
  });

  test("acessar /cliente/dashboard sem cookie redireciona para login", async ({
    page,
    context,
  }) => {
    await context.clearCookies();
    await page.goto("/cliente/dashboard");
    await page.waitForURL("**/cliente/login", { timeout: 5000 });
  });
});

import { expect, test } from "@playwright/test";

test("visitante navega da home para detalhe de case", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Cases de sucesso" })).toBeVisible();

  // Existe pelo menos um card linkado para /cases/<slug>
  const primeiroCard = page.locator('a[href^="/cases/"]').first();
  await expect(primeiroCard).toBeVisible();
  await primeiroCard.click();

  // Página detalhada tem as seções esperadas
  await expect(page.getByRole("heading", { name: "Métricas do último mês" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Evolução/ })).toBeVisible();
});

test("filtro por categoria gera URL com query string", async ({ page }) => {
  await page.goto("/");

  const selectCategoria = page.locator("select").first();
  await selectCategoria.selectOption("E-commerce");

  await expect(page).toHaveURL(/categoria=E-commerce/);
});

test("slug inexistente devolve 404", async ({ page }) => {
  const response = await page.goto("/cases/nao-existe-em-lugar-nenhum");
  expect(response?.status()).toBe(404);
});

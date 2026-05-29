import { test, expect } from "@playwright/test";

const CLIENTE = {
  id: "00000000-0000-0000-0000-000000000001",
  slug: "acme",
  nome: "Acme",
  categoria: "ECOMMERCE",
  gestor: null,
  id_google_ads: "1",
  id_meta_ads: "1",
  id_ga4: null,
  painel_url: null,
  pasta_url: null,
  cup_task_id: null,
  ativo: true,
  gestor_travado: false,
  cup: null,
};

test("trigger SEMANAL envia semana_inicio (segunda da semana escolhida)", async ({ page, context }) => {
  await context.addCookies([
    {
      name: "gestor_token",
      value: "fake-token-e2e",
      domain: "localhost",
      path: "/",
      httpOnly: false,
      secure: false,
    },
  ]);

  // Mocks de load
  await page.route("**/api/gestor/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ email: "teste@turbopartners.com.br", nome: "Teste", role: "admin" }),
    });
  });
  await page.route("**/api/gestor/clientes", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [CLIENTE] }),
    });
  });
  await page.route("**/api/gestor/gestores", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });
  await page.route("**/api/gestor/metricas/meses-disponiveis", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ meses: [] }),
    });
  });
  await page.route("**/api/gestor/reports", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  // Captura o POST do trigger
  let body: Record<string, unknown> | null = null;
  await page.route("**/api/gestor/reports/trigger", async (route) => {
    body = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ job_id: "j1" }),
    });
  });

  // Navegar para aba de Reportes (AbaClientes)
  await page.goto("/gestor?tab=reportes");

  // Selecionar o cliente Acme (checkbox com aria-label)
  await page.getByRole("button", { name: /selecionar acme/i }).click();

  // Trocar para SEMANAL
  await page.getByRole("button", { name: /^semanal$/i }).click();

  // Preencher a semana (ISO 2026-W24 → segunda = 2026-06-08)
  await page.getByLabel(/semana de referência/i).fill("2026-W24");

  // Clicar em Gerar
  await page.getByRole("button", { name: /gerar/i }).click();

  // Assertar o body do POST
  await expect.poll(() => body?.semana_inicio).toBe("2026-06-08");
  expect(body!.frequencia).toBe("SEMANAL");
});

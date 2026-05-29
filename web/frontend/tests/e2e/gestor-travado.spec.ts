import { test, expect } from "@playwright/test";

const CLIENTE = {
  id: "00000000-0000-0000-0000-000000000001",
  slug: "loja-a",
  nome: "Loja A",
  categoria: "E-commerce",
  gestor: "Gestor X",
  id_google_ads: null,
  id_meta_ads: null,
  id_ga4: null,
  painel_url: null,
  pasta_url: null,
  cup_task_id: null,
  ativo: true,
  gestor_travado: false,
  cup: null,
};

test("toggle travar gestor envia PATCH com gestor_travado", async ({ page, context }) => {
  // A middleware requer gestor_token para acessar /gestor — injetamos um cookie fake.
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

  let patchBody: Record<string, unknown> | null = null;

  // Captura o PATCH de update e responde com gestor_travado=true.
  await page.route("**/api/gestor/clientes/*", async (route) => {
    const req = route.request();
    if (req.method() === "PATCH") {
      patchBody = req.postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...CLIENTE, gestor_travado: true }),
      });
      return;
    }
    await route.continue();
  });

  // Listagem inicial de clientes com um único cliente.
  await page.route("**/api/gestor/clientes", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [CLIENTE] }),
    });
  });

  // Endpoints auxiliares que a página dispara — respostas vazias para não quebrar o load.
  await page.route("**/api/gestor/gestores-cadastrados", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });
  await page.route("**/api/gestor/reports", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  // Endpoints adicionais disparados no load da página.
  await page.route("**/api/gestor/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ email: "teste@turbopartners.com.br", nome: "Teste", role: "admin" }),
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

  // Navegar para a aba "configuracoes" onde a lista de clientes com botão "Editar" fica.
  await page.goto("/gestor?tab=configuracoes");

  // Abrir o modal de edição do cliente.
  await page.getByRole("button", { name: /^editar$/i }).first().click();

  // Marcar o toggle "Travar gestor".
  await page.getByLabel(/travar gestor/i).check();

  // Salvar.
  await page.getByRole("button", { name: /^salvar$/i }).click();

  await expect.poll(() => patchBody).not.toBeNull();
  expect(patchBody).toMatchObject({ gestor_travado: true });
});

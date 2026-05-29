import { test, expect, Page, Route } from "@playwright/test";

type Capturado = { url: string };
const capturados: Capturado[] = [];

function criativoFake(i: number, rede: "meta" | "google") {
  return {
    criativo_id: `id-${rede}-${i}`,
    cliente_slug: "loja-fashion",
    cliente_nome: "Loja Fashion",
    categoria: "E-commerce",
    gestor_nome: "Gabriel Taufner",
    rede,
    ad_id: `ad-${i}`,
    nome: `Criativo ${rede} ${i}`,
    tipo: "video",
    preview_link: `https://example.com/anuncio/${rede}/${i}`,
    thumb_url: i % 2 === 0 ? `/api/gestor/criativos/id-${rede}-${i}/thumb` : null,
    thumb_status: i % 2 === 0 ? "ok" : "sem_imagem",
    investimento: 1000 + i,
    faturamento: 5000 + i * 10,
    roas: 4.5 - i * 0.1,
    ctr: 0.012,
    cpa: 12.3,
    cpl: 8.9,
    impressoes: 100000 - i * 100,
    clicks: 1200,
    conversoes: 100,
    leads: 50,
    hook_rate: rede === "meta" ? 0.21 : null,
    frequency: 1.8,
  };
}

async function setupRoutes(page: Page, totalCriativos: number) {
  capturados.length = 0;

  // Inject the gestor_token cookie so the middleware lets us through.
  await page.context().addCookies([
    {
      name: "gestor_token",
      value: "fake-token-e2e",
      domain: "localhost",
      path: "/",
      httpOnly: false,
      secure: false,
    },
  ]);

  await page.route("**/api/gestor/me", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "u1", email: "claude@turbopartners.com.br", nome: "Claude", is_admin: true }),
    }),
  );

  await page.route("**/api/gestor/clientes", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          { id: "c1", slug: "loja-fashion", nome: "Loja Fashion", categoria: "E-commerce", gestor: "Gabriel Taufner", id_google_ads: null, id_meta_ads: null, id_ga4: null, painel_url: null, pasta_url: null, cup_task_id: null, ativo: true, cup: null },
        ],
      }),
    }),
  );

  await page.route("**/api/gestor/criativos?**", (route: Route) => {
    const url = route.request().url();
    capturados.push({ url });
    const u = new URL(url);
    const offset = Number(u.searchParams.get("offset") ?? "0");
    const limit = Number(u.searchParams.get("limit") ?? "50");
    const items = [];
    for (let i = offset; i < Math.min(offset + limit, totalCriativos); i++) {
      items.push(criativoFake(i, i % 2 === 0 ? "meta" : "google"));
    }
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, total: totalCriativos }),
    });
  });
}

test.describe("Performance · criativos v2", () => {
  test("renderiza a lista a partir do endpoint agregado", async ({ page }) => {
    await setupRoutes(page, 4);
    await page.goto("/gestor/performance");
    await expect(page.getByText("Criativo meta 0")).toBeVisible({ timeout: 5000 });
    // primeira chamada deve incluir de/ate e order_by default
    const first = capturados[0]?.url ?? "";
    expect(first).toContain("order_by=roas");
    expect(first).toContain("de=");
    expect(first).toContain("ate=");
  });

  test("chip 'Lead (ambos)' manda LEAD_COM_SITE + LEAD_SEM_SITE", async ({ page }) => {
    await setupRoutes(page, 4);
    await page.goto("/gestor/performance");
    await expect(page.getByText("Criativo meta 0")).toBeVisible();
    capturados.length = 0;
    await page.getByRole("button", { name: "Lead (ambos)" }).click();
    await expect.poll(() => capturados.length, { timeout: 3000 }).toBeGreaterThan(0);
    const last = capturados[capturados.length - 1].url;
    expect(last).toContain("categoria=LEAD_COM_SITE");
    expect(last).toContain("categoria=LEAD_SEM_SITE");
  });

  test("toggle 'Por cliente' usa cli_fat_min", async ({ page }) => {
    await setupRoutes(page, 4);
    await page.goto("/gestor/performance");
    await expect(page.getByText("Criativo meta 0")).toBeVisible();
    await page.getByRole("button", { name: "Por cliente" }).click();
    capturados.length = 0;
    await page.getByLabel("Faturamento mínimo").fill("1000");
    await expect.poll(() => capturados.some((c) => c.url.includes("cli_fat_min=1000")), { timeout: 3000 }).toBe(true);
    // não deve mandar a chave por-criativo nesse modo
    const last = capturados[capturados.length - 1].url;
    const u = new URL(last);
    expect(u.searchParams.get("fat_min")).toBeNull();
  });

  test("preset 'Mês passado' altera de/ate e refaz a busca", async ({ page }) => {
    await setupRoutes(page, 4);
    await page.goto("/gestor/performance");
    await expect(page.getByText("Criativo meta 0")).toBeVisible();
    capturados.length = 0;
    await page.getByRole("button", { name: "Mês passado" }).click();
    await expect.poll(() => capturados.length, { timeout: 3000 }).toBeGreaterThan(0);
    const last = capturados[capturados.length - 1].url;
    const u = new URL(last);
    // dia 01 do mês passado:
    expect(u.searchParams.get("de")).toMatch(/^\d{4}-\d{2}-01$/);
  });

  test("paginação 'Carregar mais' busca o próximo offset e acumula", async ({ page }) => {
    await setupRoutes(page, 80);
    await page.goto("/gestor/performance");
    await expect(page.getByText("Criativo meta 0")).toBeVisible();
    const carregarMais = page.getByRole("button", { name: /Carregar mais/i });
    await expect(carregarMais).toBeVisible();
    capturados.length = 0;
    await carregarMais.click();
    await expect.poll(() => capturados.some((c) => c.url.includes("offset=50")), { timeout: 3000 }).toBe(true);
    // item da segunda página (índice 50) deve estar presente
    await expect(page.getByText("Criativo meta 50")).toBeVisible({ timeout: 3000 });
  });

  test("botão 'Ver anúncio' aponta para preview_link em nova aba", async ({ page }) => {
    await setupRoutes(page, 4);
    await page.goto("/gestor/performance");
    await expect(page.getByText("Criativo meta 0")).toBeVisible();
    const link = page.getByRole("link", { name: /Ver anúncio/i }).first();
    await expect(link).toHaveAttribute("href", /example\.com\/anuncio/);
    await expect(link).toHaveAttribute("target", "_blank");
  });
});

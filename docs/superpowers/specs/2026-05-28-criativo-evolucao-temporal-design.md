# Design: Evolução Temporal de Criativo

**Data:** 2026-05-28  
**Escopo:** Aba "Evolução" no drawer de criativo na página `/gestor/performance`

---

## Objetivo

Permitir que gestores analisem como um criativo específico performou ao longo dos últimos 6 meses, identificando fadiga de audiência, picos de performance e declínios — tudo dentro do drawer já existente, sem navegação adicional.

---

## Localização na UI

O drawer de criativo (aberto ao clicar numa linha da tabela ou num card do pódio) ganha um sistema de abas no topo:

```
[ Métricas ]  [ Evolução ]
```

- **Métricas** — conteúdo atual do drawer, sem alterações
- **Evolução** — nova aba com gráfico histórico + badge de diagnóstico

Estado local `drawerTab: "metricas" | "evolucao"`. O drawer abre sempre em "Métricas". O fetch dos dados históricos é **lazy**: só dispara na primeira vez que a aba "Evolução" é selecionada.

---

## Dados

### Fonte
`gestorApi.metricasBreakdown(clienteSlug, mes)` — já disponível, retorna `{ meta_ads: MetaAd[], google_ads: GoogleAd[] }`.

### Estratégia de fetch
Ao abrir a aba Evolução pela primeira vez, disparar 6 chamadas paralelas:

```typescript
const meses = Array.from({ length: 6 }, (_, i) => deslocarMes(mes, -i)).reverse();
const results = await Promise.all(
  meses.map(m => gestorApi.metricasBreakdown(clienteSlug, m).catch(() => null))
);
```

### Identificação do criativo entre meses
Criativo identificado por `ad.nome === selectedAd.nome` dentro do array correto (meta_ads ou google_ads, conforme tipo do criativo selecionado).

### Tipo de dado histórico
```typescript
type HistoryPoint = {
  mes: string;          // "2025-12", "2026-01", etc.
  mesLabel: string;     // "Dez", "Jan", etc. — derivado de mes.slice(5,7) via MES_ABBR map
  roas: number | null;
  cpm: number | null;
  investimento: number | null;
  faturamento: number | null;
};

const MES_ABBR: Record<string, string> = {
  "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
  "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
  "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
};
```

Meses onde o criativo não aparece nos dados → todos os campos `null`. O gráfico trata `null` como gap nativo (recharts `connectNulls={false}`).

---

## Gráfico — ComposedChart

Biblioteca: **recharts** (já instalada, v3.8.1).

### Estrutura
- Eixo X: `mes` (labels abreviados: "Dez", "Jan", etc.)
- **Eixo Y esquerdo** (`yAxisId="ratio"`): ROAS e CPM
- **Eixo Y direito** (`yAxisId="reais"`): Faturamento e Investimento (R$)

### Séries
| Série | Tipo | Cor | Eixo |
|---|---|---|---|
| Faturamento | Bar (fundo) | `var(--forest)` 35% opacidade | direito |
| Investimento | Bar (fundo) | `var(--muted)` 25% opacidade | direito |
| ROAS | Line (frente) | `var(--forest)` sólido | esquerdo |
| CPM | Line (frente) | âmbar `#f59e0b` tracejado | esquerdo |

Barras renderizam primeiro (atrás), linhas por cima — dão contexto de volume sem poluir tendência.

### Tooltip personalizado
Ao hover num mês: mostra todos os 4 valores formatados (ROAS: `2.8×`, CPM: `R$ 18,40`, Faturamento: `R$ 42.000`, Investimento: `R$ 15.000`).

---

## Detecção de Fadiga

Analisar os últimos 2 meses que têm dados (`roas !== null`):

Algoritmo: filtrar `history.filter(p => p.roas !== null)`, pegar os 2 últimos. Se menos de 2 pontos com dados → sem badge.

| Condição (prev = penúltimo ponto com dados, last = último) | Badge |
|---|---|
| `last.cpm > prev.cpm * 1.15` **E** `last.roas < prev.roas * 0.85` | `⚠️ Fadiga detectada` (âmbar) |
| `last.roas < prev.roas * 0.80` (independente de CPM) | `↘ Performance em queda` (vermelho suave) |
| Menos de 2 pontos com dados | nenhum badge |
| Caso contrário | `✓ Saudável` (verde) |

Badge aparece no topo da aba, acima do gráfico.

---

## Estados da aba Evolução

| Estado | UI |
|---|---|
| Carregando | 3 barras horizontais animadas (`animate-pulse`) onde ficaria o gráfico |
| Criativo com 1 único mês de dados | Gráfico com 1 ponto, sem badge de diagnóstico |
| Criativo sem dados em nenhum mês | Mensagem: "Sem histórico disponível para este criativo" |
| Erro parcial em algum mês | Mês vira `null` silenciosamente — não quebra o gráfico |

---

## Escopo e Restrições

- Aplica-se a criativos **Meta Ads e Google Ads** (mesmo drawer, mesma lógica)
- Janela fixa de **6 meses** — sem seletor de período nesta versão
- Identificação por nome do criativo: se o nome mudar entre meses, o histórico quebra (limitação conhecida da API atual)
- Sem persistência de cache: cada abertura da aba re-fetcha os 6 meses

---

## Arquivos Afetados

- **Modificar:** `web/frontend/app/gestor/performance/page.tsx`
  - Adicionar estado `drawerTab`
  - Adicionar componente `EvolucaoTab`
  - Adicionar lógica de fetch histórico
  - Adicionar `HistoryPoint` type e função `detectFadiga`
  - Adicionar tab strip ao drawer existente

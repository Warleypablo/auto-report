# Configurações de Clientes — Design Spec

**Goal:** Permitir que usuários logados editem os campos operacionais dos clientes (gestor, IDs de plataforma, links) e os desativem (soft delete) diretamente na aba Configurações do painel gestor, sem precisar acessar a planilha central.

**Architecture:** DB passa a ser a fonte de verdade para campos editáveis. A planilha central continua sendo usada para importar novos clientes, mas não sobrescreve campos já definidos no DB. O frontend usa tabela + modal para edição, com soft delete via flag `ativo`.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), Next.js 14 App Router + TypeScript (frontend), PostgreSQL

---

## 1. Banco de Dados

### Novos campos em `clientes`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id_google_ads` | `String, nullable` | `NULL` | ID da conta Google Ads |
| `id_meta_ads` | `String, nullable` | `NULL` | ID da conta Meta Ads |
| `id_ga4` | `String, nullable` | `NULL` | ID da propriedade GA4 |
| `painel_url` | `String, nullable` | `NULL` | Link painel de controle |
| `pasta_url` | `String, nullable` | `NULL` | Link pasta de arquivos |
| `ativo` | `Boolean, not null` | `True` | False = soft-deleted |

### Migration Alembic

Uma única migration adiciona as 6 colunas. Clientes existentes ficam com `ativo=True` e os campos de ID/URL como `NULL` (serão preenchidos na próxima sincronização com a planilha).

### Regra de sincronização

- **INSERT** (cliente novo): popula todos os campos, incluindo os novos.
- **UPDATE** (cliente existente): atualiza `nome` e `categoria` apenas. Os campos `gestor`, `id_google_ads`, `id_meta_ads`, `id_ga4`, `painel_url`, `pasta_url` **não são sobrescritos** — o DB é autoritativo.
- Clientes com `ativo=False` são ignorados em todos os endpoints de listagem.

---

## 2. API (backend)

### Novos endpoints

#### `PATCH /gestor/clientes/{cliente_id}`

Atualiza campos editáveis de um cliente.

**Autorização:**
- Admin: pode editar qualquer cliente.
- Gestor comum: só pode editar clientes atribuídos via `UsuarioCliente`.

**Request body** (`ClienteEditRequest`):
```json
{
  "nome": "string | null",
  "categoria": "E-commerce | Lead Com Site | Lead Sem Site | null",
  "gestor": "string | null",
  "id_google_ads": "string | null",
  "id_meta_ads": "string | null",
  "id_ga4": "string | null",
  "painel_url": "string | null",
  "pasta_url": "string | null"
}
```
Todos os campos são opcionais — apenas os campos enviados com valor não-`None` são atualizados.

**Response:** `ClienteDetalheItem` com todos os campos (200 OK).

**Erros:**
- `404` se o cliente não existir ou não estiver no escopo do usuário.
- `403` se gestor comum tentar editar cliente fora do seu escopo.

#### `DELETE /gestor/clientes/{cliente_id}`

Soft delete — seta `ativo=False`.

**Autorização:** mesmas regras do PATCH.

**Response:** `204 No Content`.

**Erros:**
- `404` se não encontrado ou fora do escopo.

### Schemas novos

**`ClienteEditRequest`** (body do PATCH):
```python
class ClienteEditRequest(BaseModel):
    nome: str | None = None
    categoria: Categoria | None = None
    gestor: str | None = None
    id_google_ads: str | None = None
    id_meta_ads: str | None = None
    id_ga4: str | None = None
    painel_url: str | None = None
    pasta_url: str | None = None
```

**`ClienteDetalheItem`** (response do PATCH e do GET /clientes):
```python
class ClienteDetalheItem(BaseModel):
    id: uuid.UUID
    slug: str
    nome: str
    categoria: str
    gestor: str | None
    id_google_ads: str | None
    id_meta_ads: str | None
    id_ga4: str | None
    painel_url: str | None
    pasta_url: str | None
    ativo: bool
```

### Endpoints existentes atualizados

- `GET /gestor/clientes` — passa a filtrar `ativo=True` e retorna `ClienteDetalheItem` (com os novos campos).
- `GET /gestor/gestores` — filtra `ativo=True`.

---

## 3. Frontend

### Aba Configurações (`page.tsx` — `AbaConfiguracoes`)

Substitui o placeholder atual. Estrutura:

1. **Barra de busca** — filtra por nome (igual à aba Clientes).
2. **Tabela de clientes** — colunas: Nome, Categoria, Gestor, ID Google, ID Meta, ID GA4, Ações.
   - O filtro de gestor da barra superior (já existente) se aplica aqui.
   - Linhas clicam em "Editar" (lápis) ou "Desativar" (×).
3. **Modal de edição** — abre ao clicar em "Editar":
   - Campos: Nome, Categoria (select), Gestor, ID Google Ads, ID Meta Ads, ID GA4, Link Painel, Link Pasta.
   - "Salvar" chama `PATCH`, atualiza a linha localmente (sem reload), fecha o modal.
   - "Cancelar" fecha sem salvar.
4. **Confirmação de desativação** — dialog nativo (`<dialog>`) com o nome do cliente:
   - "Desativar" chama `DELETE`, remove a linha da lista local.
   - "Cancelar" fecha o dialog.

### Tipos TypeScript

`ClienteGestor` (em `api-gestor.ts`) ganha os novos campos:
```typescript
export type ClienteGestor = {
  id: string;
  slug: string;
  nome: string;
  categoria: string;
  gestor: string | null;
  id_google_ads: string | null;
  id_meta_ads: string | null;
  id_ga4: string | null;
  painel_url: string | null;
  pasta_url: string | null;
  ativo: boolean;
};
```

### Novos métodos em `gestorApi`

```typescript
updateCliente: (id: string, data: Partial<ClienteEditData>) =>
  apiCall<ClienteGestor>(`clientes/${id}`, "PATCH", data),

deleteCliente: (id: string) =>
  apiCall<void>(`clientes/${id}`, "DELETE"),
```

---

## 4. Fluxo de dados resumido

```
Planilha Central
      │ sync (INSERT novos, sem sobrescrever editáveis)
      ▼
  DB (clientes)
      │ PATCH /gestor/clientes/{id}
      │ DELETE /gestor/clientes/{id}
      ▼
  Painel Gestor → aba Configurações → Modal → Tabela atualizada
```

---

## 5. O que não entra neste escopo (YAGNI)

- Escrever de volta na planilha Google Sheets via API
- Campo GERAR? (ativa/desativa ETL por cliente) — separado
- Campo SQUAD — não utilizado pelo sistema atualmente
- Reativar clientes desativados via UI (pode ser feito direto no DB por admin)
- Histórico de auditoria de edições

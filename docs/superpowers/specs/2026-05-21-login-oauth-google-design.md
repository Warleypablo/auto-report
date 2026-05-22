# Login Google OAuth — Painel Gestor

**Data:** 2026-05-21  
**Escopo:** Substituição do formulário email+senha por autenticação Google OAuth 2.0, restrita aos endpoints `/gestor`.

---

## Contexto

O painel de gestores em `/gestor` usa atualmente autenticação própria: formulário email+senha → JWT armazenado como cookie `gestor_token` (httpOnly, 8h). O objetivo é substituir esse fluxo por Google OAuth mantendo o mesmo mecanismo de sessão (cookie JWT), sem expor o backend FastAPI à internet para o dance OAuth.

---

## Decisões de design

- **Substituição total** do login email+senha — sem fallback de senha.
- **Allow-list por e-mail**: apenas usuários já cadastrados na tabela `usuarios` (campo `email`, `ativo=true`) podem entrar. Nenhuma conta Google nova é criada automaticamente.
- **OAuth gerenciado pelo Next.js** (Opção A): as rotas de API do Next.js conduzem o dance OAuth; o FastAPI recebe apenas o e-mail já validado pelo Google e emite o JWT.

---

## Fluxo completo

```
Browser → GET /api/auth/google/start
  └─ gera state (UUID aleatório)
  └─ seta cookie gestor_oauth_state (httpOnly, sameSite:lax, 5min)
  └─ 302 → accounts.google.com/o/oauth2/auth?
        client_id=&redirect_uri=&scope=openid email profile&state=<uuid>&response_type=code

Google → GET /api/auth/google/callback?code=&state=
  └─ valida state contra cookie gestor_oauth_state (anti-CSRF)
  └─ POST accounts.google.com/o/oauth2/token → access_token
  └─ GET oauth2.googleapis.com/userinfo → { email, name }
  └─ POST /auth/google-login no FastAPI → { token, usuario }
       FastAPI: busca usuario por email, valida ativo=true, emite JWT
       401 se não encontrado ou inativo
  └─ apaga cookie gestor_oauth_state
  └─ seta cookie gestor_token (httpOnly, sameSite:lax, 8h)
  └─ 302 → /gestor

Qualquer erro → 302 → /gestor/login?erro=<motivo>
```

---

## Variáveis de ambiente

**Frontend (`.env` do Next.js):**
```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:3000/api/auth/google/callback
```

**Backend:** sem mudanças — JWT_SECRET, JWT_ALGORITHM e JWT_EXPIRY_HOURS já existem.

---

## Arquivos

### Novos (frontend)

| Arquivo | Responsabilidade |
|---|---|
| `web/frontend/app/api/auth/google/start/route.ts` | Gera URL de autorização, seta cookie CSRF, redireciona para o Google |
| `web/frontend/app/api/auth/google/callback/route.ts` | Troca `code` por token, obtém userinfo, chama FastAPI, seta `gestor_token` |

### Modificados (frontend)

| Arquivo | Mudança |
|---|---|
| `web/frontend/app/gestor/login/page.tsx` | Remove form email+senha; exibe botão "Entrar com Google" + mensagem de erro condicional |
| `web/frontend/app/api/gestor/login/route.ts` | Removido — substituído pelo fluxo OAuth |

### Novos (backend)

| Arquivo | Mudança |
|---|---|
| `web/backend/api/auth.py` | Novo endpoint `POST /auth/google-login`: recebe `{email, nome}`, valida usuário ativo, retorna JWT |

### Sem mudança

- `app/api/gestor/logout/route.ts` — já limpa `gestor_token`, funciona igual
- `app/api/gestor/[...path]/route.ts` — proxy lê `gestor_token`, sem alteração
- `app_settings.py` — configurações JWT já existem

---

## Tela de login

Remove o formulário atual. Exibe apenas:

- Logotipo "CASES / Painel de Gestores" (igual ao atual)
- Botão "Entrar com Google" seguindo o Google Sign-In Button design kit (fundo branco, borda cinza, ícone SVG oficial, texto "Entrar com Google")
- Mensagem de erro contextual se `?erro=` presente na URL:
  - `nao_autorizado` → "Acesso restrito. Solicite cadastro ao administrador."
  - `state_invalido` → "Sessão expirada. Tente novamente."
  - `falha_google` → "Erro ao autenticar com o Google. Tente novamente."

---

## Segurança

| Medida | Implementação |
|---|---|
| Anti-CSRF | Cookie `gestor_oauth_state` (httpOnly, 5 min) com UUID; validado no callback antes de qualquer ação |
| Scope mínimo | `openid email profile` — sem acesso a dados do Google |
| Validação server-side | E-mail vem do userinfo do Google (não do browser); FastAPI valida `ativo=true` |
| Token Google descartado | `access_token` do Google não é armazenado; usado apenas para obter o e-mail e descartado |
| Sessão final | `gestor_token` httpOnly, `sameSite:lax`, 8h — mesmo padrão atual |

---

## Fora de escopo

- Middleware Next.js para proteção de rota (o padrão existente de `gestorApi.me()` no `useEffect` já cobre)
- Auto-criação de usuários via Google
- Suporte a múltiplos providers OAuth
- Refresh token / renovação automática de sessão

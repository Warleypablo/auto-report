# Deploy — Render + GCP Cloud SQL

## Pré-requisitos

- Conta no [Render](https://render.com)
- Instância PostgreSQL no GCP Cloud SQL criada e com IP público habilitado
- Repositório no GitHub (ou GitLab)

---

## 1. Banco de dados (GCP Cloud SQL)

### Criar o banco
```sql
CREATE DATABASE vitrine;
CREATE USER vitrine WITH PASSWORD 'senha-forte-aqui';
GRANT ALL PRIVILEGES ON DATABASE vitrine TO vitrine;
```

### Liberar acesso do Render
No console GCP → Cloud SQL → Sua instância → Conexões → Redes autorizadas:
- Adicione os IPs de saída do Render: https://render.com/docs/static-outbound-ip-addresses
- Ou use `0.0.0.0/0` com SSL obrigatório (menos seguro, mais simples)

### String de conexão
```
DATABASE_URL=postgresql+psycopg://vitrine:senha-forte-aqui@<IP-CLOUD-SQL>:5432/vitrine
```

---

## 2. Preparar credenciais Google

Na raiz do repo, rode:
```bash
bash scripts/encode-credentials.sh
```

Copie os valores de `GOOGLE_SERVICE_ACCOUNT_JSON_B64` e `GOOGLE_ADS_YAML_B64` — serão colados no Render.

---

## 3. Deploy no Render

### Opção A — Blueprint (recomendado)
1. Faça push do repo para o GitHub
2. No Render: New → Blueprint → conecte o repo
3. O `render.yaml` detecta os dois serviços automaticamente
4. Preencha as env vars marcadas com `sync: false` no dashboard

### Opção B — Manual
Crie dois serviços:

**Backend:**
- Type: Web Service | Runtime: Python | Region: Oregon
- Root directory: `.` (raiz do repo)
- Build: `pip install -r web/backend/requirements.txt -r requirements.txt`
- Start: `bash scripts/start-backend.sh`
- Env vars: ver `render.yaml`

**Frontend:**
- Type: Web Service | Runtime: Node | Region: Oregon
- Root directory: `web/frontend`
- Build: `npm ci && npm run build`
- Start: `npm start`
- Env var: `INTERNAL_API_URL=http://<nome-backend>.onrender.com` (ou URL interna)

---

## 4. Env vars obrigatórias (backend)

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Connection string do Cloud SQL |
| `JWT_SECRET` | Segredo para tokens JWT (gerado pelo Render) |
| `ETL_TRIGGER_TOKEN` | Token para disparar ETL via API |
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | base64 do service account JSON |
| `GOOGLE_ADS_YAML_B64` | base64 do google-ads.yaml |
| `CENTRAL_SHEET_URL` | URL da planilha central |
| `TEMPLATE_RELATORIO_ID` | ID do template de slides |
| `RELATORIO_FOLDER_ID` | ID da pasta do Drive |
| `TEMPLATE_ECOMMERCE` | ID do template E-commerce |
| `TEMPLATE_LEAD_SEM_SITE` | ID do template Lead Sem Site |
| `TEMPLATE_LEAD_COM_SITE` | ID do template Lead Com Site |
| `ACCESS_TOKEN_META_SYSTEM` | Token sistema Meta Ads |
| `BUSINESS_ID_META` | Business ID Meta |
| `APP_ID_META` | App ID Meta |
| `CORS_ORIGINS` | `["https://seu-frontend.onrender.com"]` |

---

## 5. Primeiro acesso

Após o deploy, crie o usuário admin:
```bash
# No shell do serviço backend no Render (Dashboard → Shell)
cd web/backend
python scripts/seed_admin.py --email admin@suaagencia.com --nome "Admin" --senha "senha-segura"
```

---

## 6. Domínio personalizado (opcional)

Render → seu serviço → Settings → Custom Domains → adicione o domínio.
Atualize `CORS_ORIGINS` no backend com o domínio real do frontend.

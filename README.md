# Sistema IA de Recomendação de Filmes e Séries (Azure)

Aplicação fullstack funcional com:
- **Backend** em FastAPI (recomendação com Azure OpenAI + fallback local).
- **Frontend** em HTML/JS simples (sem build step).
- **Catálogo local** para garantir funcionamento mesmo sem API paga.

## 1) Como rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edite `.env` com suas credenciais Azure OpenAI.

### Subir backend
```bash
source .venv/bin/activate
set -a; source .env; set +a
uvicorn backend.main:app --reload --port 8000
```

### Subir frontend
Em outro terminal:
```bash
python -m http.server 5500 -d frontend
```

Abra: `http://localhost:5500`

## 2) Endpoint principal

`POST /recommend`

Payload:

```json
{
  "prompt": "Quero uma série curta e engraçada para ver em família",
  "max_results": 5
}
```

## 3) Controle de custos no limite de R$100/mês

Recomendação prática para não estourar orçamento:

1. Use deployment econômico no Azure OpenAI (ex.: GPT-4o-mini).
2. Mantenha `max_tokens` baixo (no projeto está em 350).
3. Use prompt curto e catálogos compactos.
4. Configure **Budget + Alertas** no Azure Cost Management:
   - alerta em **R$ 60** (aviso)
   - alerta em **R$ 85** (ação preventiva)
   - hard-stop manual em **R$ 100**
5. Monitorar consumo semanal e ajustar `max_results`, `max_tokens` e tamanho do catálogo enviado ao modelo.

### Exemplo de estimativa

Se cada requisição consumir em média 1.500 tokens (entrada + saída), você consegue alto volume mensal dentro de R$100 em modelos mini.

> Se Azure OpenAI estiver indisponível, o sistema usa fallback local por palavras-chave sem custo de inferência.

## 4) Estrutura

- `backend/main.py` - API e lógica de recomendação.
- `frontend/index.html` - UI web.
- `data/catalog.json` - base inicial de filmes/séries.
- `.env.example` - variáveis Azure.

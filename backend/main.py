import json
import os
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = BASE_DIR / "data" / "catalog.json"

app = FastAPI(title="Recomendador de Filmes e Séries")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendationRequest(BaseModel):
    prompt: str
    max_results: int = 5


class RecommendationResponse(BaseModel):
    strategy: str
    recommendations: list[dict[str, Any]]


def load_catalog() -> list[dict[str, Any]]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def keyword_match_recommendations(prompt: str, catalog: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    prompt_l = prompt.lower()
    scored: list[tuple[int, dict[str, Any]]] = []

    for item in catalog:
        score = 0
        for g in item["genres"]:
            if g.lower() in prompt_l:
                score += 3
        if item["type"].lower() in prompt_l:
            score += 2
        for kw in item.get("keywords", []):
            if kw.lower() in prompt_l:
                score += 2
        if any(token in prompt_l for token in ["leve", "engra", "comédia", "happy"]) and "Comédia" in item["genres"]:
            score += 1
        if any(token in prompt_l for token in ["suspense", "tenso", "mistério"]) and "Suspense" in item["genres"]:
            score += 1
        if any(token in prompt_l for token in ["família", "criança"]) and item.get("family_friendly"):
            score += 2

        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [item for score, item in scored if score > 0][:max_results]
    if top:
        return top
    return catalog[:max_results]


def azure_openai_recommendations(prompt: str, catalog: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    if not (endpoint and api_key and deployment):
        raise RuntimeError("Azure OpenAI não configurado")

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    catalog_compact = [
        {
            "title": item["title"],
            "type": item["type"],
            "genres": item["genres"],
            "year": item["year"],
        }
        for item in catalog
    ]

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um recomendador de filmes e séries. "
                    "Escolha SOMENTE títulos existentes no catálogo fornecido e retorne JSON no formato: "
                    '{"titles": ["..."], "reason": "..."}'
                ),
            },
            {
                "role": "user",
                "content": f"Preferência do usuário: {prompt}\nCatálogo: {json.dumps(catalog_compact, ensure_ascii=False)}\nMáximo de resultados: {max_results}",
            },
        ],
        "temperature": 0.3,
        "max_tokens": 350,
        "response_format": {"type": "json_object"},
    }

    headers = {"api-key": api_key, "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    if response.status_code >= 400:
        raise RuntimeError(f"Erro Azure OpenAI: {response.text}")

    content = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    selected_titles = set(parsed.get("titles", []))

    result = [item for item in catalog if item["title"] in selected_titles][:max_results]
    if not result:
        raise RuntimeError("Modelo não retornou títulos válidos")
    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/recommend", response_model=RecommendationResponse)
def recommend(req: RecommendationRequest) -> RecommendationResponse:
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt não pode ser vazio")

    catalog = load_catalog()

    try:
        recs = azure_openai_recommendations(req.prompt, catalog, req.max_results)
        strategy = "azure_openai"
    except Exception:
        recs = keyword_match_recommendations(req.prompt, catalog, req.max_results)
        strategy = "fallback_local"

    return RecommendationResponse(strategy=strategy, recommendations=recs)

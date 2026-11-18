# DarGlobal + Wasalt chatbot

RAG chatbot over scraped public data from DarGlobal and Wasalt. FastAPI, BM25 retrieval, free model via OpenRouter, Docker.

- `data/wasalt.md`: scraped from wasalt.sa/en (listing totals, sample listings, company info). Scraped through a real browser session because the site sits behind Cloudflare.
- `data/darglobal.md`: darglobal.co.uk blocks automated access (Imperva), so this file is built from public press coverage. The file says so and the bot is told to admit gaps.
- `app/main.py`: sections are chunked, ranked with BM25, and the top 4 go to the model as context. If OpenRouter fails, the bot falls back through other free models, then to retrieval-only answers.

## Run
```
cp .env.example .env   # set OPENROUTER_API_KEY
docker build -t chatbot . && docker run -p 8000:8000 --env-file .env chatbot
```
Open http://localhost:8000. Health check: /health.

## Deploy
`render.yaml` deploys it on Render as a Docker web service. Set `OPENROUTER_API_KEY` in the dashboard.

# DarGlobal + Wasalt chatbot

Retrieval-augmented chatbot over public data scraped from **darglobal.co.uk** and **wasalt.sa**. FastAPI + BM25 retrieval + a free OpenRouter model, containerised with Docker and deployed on Render.

Live: https://darglobal-wasalt-chatbot-088i.onrender.com (free tier: first request after idle takes about 50 seconds)

## How it works
1. **Scrape** (`scraper/browser_scrape.js`): both sites are behind bot protection (Cloudflare, Imperva), so plain HTTP clients get blocked. The pages render server-side, so the scraper runs inside a real browser session on each site and reads the public pages politely, one at a time. 
2. **Knowledge base** (`data/*.md`): the text is cleaned into titled sections. Each file states its source. 
   - DarGlobal: about, investor profile, full project list, residency and tax info, FAQ, hospitality, tokenization, One of One collection, AIDA (Oman), Trump Organization partnership, and all recent press releases (HY 2026 results, Jeddah SAR 1bn development, Qatar villas, Dubai tower, Fendi Casa Oman, Capital Partners). 
   - Wasalt: company info, listing totals and sample listings for sale, rent and land across 7 cities, blog titles. 
3. **Retrieval** (`app/main.py`): sections are split into chunks of at most about 1,100 characters, indexed with BM25 (written from scratch, no external vector service), and the top 5 chunks go to the model as context.
4. **Generation**: OpenRouter free models, tried in order (`OPENROUTER_MODEL`, comma separated) so one rate-limited model does not break the bot. If every model fails the bot returns the retrieved passages instead of an error.
5. **Grounding**: the system prompt tells the model to answer only from context and say when it does not know. Every reply shows which model answered and which sources were used.

## Run locally
```
cp .env.example .env   # set OPENROUTER_API_KEY
docker build -t chatbot . && docker run -p 8000:8000 --env-file .env chatbot
```
Open http://localhost:8000. Health check: `/health`. API: `POST /api/chat` with `{"message": "...", "history": []}`.

## Deploy
`render.yaml` is a Render Blueprint (Docker web service, free plan). Set `OPENROUTER_API_KEY` in the dashboard.

## Limits
- The Wasalt data is a snapshot sample (hundreds of listings exist per city; the knowledge base holds listing totals and a sample per city), not a live feed.
- Listing totals and prices are as shown on the day of scraping.
- Free models can be slow or rate limited.

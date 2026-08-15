# Shadow AI 3.0

A general-purpose AI chat APK with a lightweight Railway agent, optional multi-source research, direct OpenAI + Anthropic model backends, and a separate memory service.

## Architecture

```text
Shadow AI APK
     |
     v
Railway Backend (backend/)
  |       |       |
  |       |       +--> OpenAI Responses API
  |       +----------> Anthropic Messages API
  +------------------> multi-source research + safe terminal diagnostics
  |
  +--> Backend 2 (backend2/)
          |
          +--> MongoDB Atlas (optional)
          +--> SQLite fallback
```

The APK never receives provider API keys. They stay in Railway environment variables.

## What changed in 3.0

### APK
- Anime-inspired neon/glow visual system.
- Proper message bubbles with role labels, wrapping and sizing.
- Keyboard-safe layout using Android resize behavior.
- Composer grows up to four lines instead of hiding typed text behind the keyboard.
- No automatic keyboard popup at launch.
- Thinking animation.
- Better HTTP/network error messages.
- Deep-research toggle.
- Persistent anonymous local user ID for memory service.
- Optional `intro.mp4` startup video.
- Your `background.jpg` remains the chat background.
- `666(LINDO)` activates Royal Mode.

### Railway backend
- `/chat` now accepts `message`, `history`, `deep_search`, `royal_mode`, `memory_context`, and `user_id`.
- No local Qwen model is loaded, so the old 500 MB-class model is not consuming the free Railway RAM budget.
- Direct OpenAI Responses API integration.
- Direct Anthropic Messages API integration.
- Complex/research requests can run GPT and Claude in parallel, then use a final synthesis pass.
- Multi-source research engine using public web sources plus specialized sources when relevant.
- Safe terminal diagnostics: curl, wget, dig, host, whois, python3.
- Domain DNS/WHOIS enrichment when a domain is present.
- Code blocks are syntax-checked without executing them.

### Backend 2
- Lightweight memory service in its own folder.
- MongoDB Atlas support through `MONGO_URI`.
- SQLite fallback if MongoDB is not configured.
- Long-term memory endpoints.
- Conversation archive endpoints.
- Optional shared API key.
- No LLM, llama.cpp, or heavy model package.

## Railway environment variables

Required for the AI team:

```text
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

Model names are configurable because provider model names can change:

```text
OPENAI_MODEL=gpt-5
ANTHROPIC_MODEL=claude-sonnet-4-5
AI_TIMEOUT_SECONDS=45
```

Optional memory connection:

```text
MEMORY_BACKEND_URL=https://YOUR-BACKEND2-DOMAIN
MEMORY_API_KEY=your-shared-secret
MEMORY_TIMEOUT_SECONDS=8
```

The official OpenAI API and Anthropic API are called directly. This project does not use an OpenAI-compatible proxy.

## Backend 2 environment variables

For MongoDB Atlas:

```text
MONGO_URI=mongodb+srv://...
MONGO_DB=shadow_ai
MEMORY_API_KEY=the-same-secret-used-by-Railway
```

If `MONGO_URI` is absent, Backend 2 uses SQLite at:

```text
/data/shadow_memory.db
```

For a free host with persistent storage, mount/use the host's persistent volume for `/data` if available.

## Backend deployment

Deploy `backend/` as its own Railway service. Railway should detect the Dockerfile.

Health check:

```text
GET /health
```

Chat:

```text
POST /chat
```

Example request:

```json
{
  "message": "Research the best option and compare them.",
  "history": [
    {"role": "user", "content": "I need a GPU for rendering."},
    {"role": "assistant", "content": "Tell me your budget."}
  ],
  "deep_search": true,
  "royal_mode": false,
  "user_id": "android-example"
}
```

## Backend 2 deployment

Deploy the `backend2/` folder separately. It is intentionally tiny and has no model download.

Then set its public URL as `MEMORY_BACKEND_URL` on the main Railway backend.

## APK

Put these files in `frontend/`:

```text
main.py
buildozer.spec
background.jpg
intro.mp4       # optional
```

The APK expects the Railway base URL in `frontend/main.py`:

```python
BACKEND_URL = "https://your-railway-domain.up.railway.app"
```

Do **not** add `/chat` to `BACKEND_URL`. The app adds `/chat` itself.

### GitHub Actions

Push the repository and run the `Build Shadow AI APK` workflow. The workflow caches Buildozer downloads and retries the Android build for transient download failures such as HTTP 503 responses.

### UserLAnd

```bash
bash scripts/setup_userland.sh
bash scripts/build_apk.sh
```

The builder expects the frontend at:

```text
/sdcard/Download/shadow-ai/frontend
```

## Important design choice

The main Railway service no longer tries to load Qwen locally. That was the wrong fit for a small free RAM budget. GPT/Claude are remote brains, research is handled by lightweight HTTP/terminal tools, and memory is moved to Backend 2.

That separation makes the project much easier to scale later.

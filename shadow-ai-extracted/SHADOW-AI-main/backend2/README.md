# Shadow AI Backend 2 - Memory Service

Lightweight memory API. It does **not** run an LLM.

- `MONGO_URI` present: MongoDB Atlas storage.
- Otherwise: SQLite at `/data/shadow_memory.db`.
- Optional `MEMORY_API_KEY` protects the API.

Endpoints: `/health`, `/memory/save`, `/memory/search`, `/conversation/message`, `/conversation/recent`.

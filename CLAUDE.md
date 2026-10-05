# HW5 — Campus Customs multi-agent operations

- Work one problem at a time, only after the user describes it. Do not work ahead.
- When the user gives a new problem, add their prompt to `AI_prompts.md` (number + title, prompt in their own words, at most one follow-up plus one sentence on what was lacking). No extra evidence sections.
- Never modify `data/campus_customs.db` (SHA-256 `23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a`). All reads/writes go to the working copy `data/campus_customs_new.db`.
- AI model calls: only `gpt-6-luna` via `PORTKEY_API_KEY` (from the Coding root `.env`). This overrides the parent AGENTS.md default model. Use `OpenAIResponsesModel`: gpt-6-luna rejects function tools on chat completions.
- Test agents/tools against scratch DB copies (`CAMPUS_CUSTOMS_DB`, `CAMPUS_CUSTOMS_STATE_DIR`, `AUDIT_TRAIL_PATH` env vars), not `campus_customs_new.db`, unless the user is running a real problem step.
- Eventual system: a boss agent plus inventory, accounting, facilities, and customer service agents. Don't build it until asked.

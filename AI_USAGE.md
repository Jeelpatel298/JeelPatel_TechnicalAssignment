# AI Usage

**Tool used** — OpenAI Codex.

**Usage** — Codex read the assignment brief and generated the application, schema, standalone SQL, tests, documentation, and Git commits. Codex also exercised the local app in Chromium, captured the walkthrough, and generated narration using macOS text-to-speech.

**Example prompt** — “make properly this assignment”, with the technical assignment PDF attached.

**Review** — Codex ran the pricing and debugging tests and the full integration suite using MySQL 8.4.11. Integration coverage includes simultaneous confirmation attempts for the same stock, rollback on a shortage, order ownership, and atomic import. The recorded browser scenarios checked the live totals, stock changes, role restrictions, reports, and CSV feedback against the running local app.

**Corrections** — The initial MySQL schema used column-level CHECK constraints for rules involving multiple columns. MySQL rejected those definitions, so they were moved to table-level CHECK constraints. The first implementation also relied on Werkzeug's default scrypt hash, which was unavailable in the system Python build used for verification. It now selects salted PBKDF2-SHA256 explicitly. Order dates and movement timestamps were switched to ISO strings so browser date fields receive the expected format.

A second review added regression tests for malformed CSV line numbers and invalid prices, and moved the report queries into one consistent MySQL snapshot to keep concurrent updates from producing contradictory sections.

A further review added regression tests for a cancellation immediately after confirmation and for stock adjustments close to the database limit. The application now captures mutation responses inside the transaction and keeps enough capacity for confirmed orders to return stock. The browser review also caught a catalog editor that could be dismissed during a save. Its close controls now wait for the request to finish.

The final pass used a fresh extraction and a clean environment installed from the documented requirements. Additional API checks found that unsupported methods lost the Allow header and invalid Unicode text could produce a server error. Both cases now have regression coverage.

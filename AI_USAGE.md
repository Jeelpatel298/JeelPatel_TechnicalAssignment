# AI Usage

## Tools and scope

I used OpenAI Codex for implementation, testing, and documentation across the Flask app and MySQL database. I supplied the assignment brief, requested follow-up checks, and selected changes from a Claude review for Codex to apply. Codex captured the demo and used macOS text-to-speech for narration.

## Representative requests

- Build the application to match the assignment brief.
- Recheck the extracted submission and fix reproducible issues.
- Apply the review feedback on order numbers, access responses, sample SQL, and test dependencies.

## Verification and corrections

Codex ran 42 tests on MySQL 8.4.11 and walked through both roles in Chromium. The checks covered concurrent order confirmations, stock restoration, order access, and CSV rollback.

The review found that a malformed CSV record could report the wrong line and that a concurrent order update could make report sections disagree. The fixes report the record's starting line and use one database snapshot for the report. Both fixes have regression tests.

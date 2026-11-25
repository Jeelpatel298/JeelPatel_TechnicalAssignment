# AI Usage

I used OpenAI Codex to implement the assignment from the supplied brief. Codex drafted and refined the Flask application, MySQL schema, SQL reports, tests, and documentation. I requested follow-up reviews, shared suggestions from a Claude review, and supplied the Git author details. Codex recorded the browser demo and used macOS text-to-speech for the narration.

## Representative requests

- Build the application from the attached assignment brief.
- Review the submission again and fix any issues found.
- Apply the suggestions on order numbers, access responses, sample SQL, and dependency setup.

## Verification and corrections

Codex ran 42 automated tests against MySQL 8.4.11 and checked both user roles in Chromium. The checks covered simultaneous order confirmations, stock restoration, ownership, and CSV rollback. The SQL-only catalog setup and the archived Git history were also verified.

The review corrected line numbers for malformed CSV records and made the sales reports read from a single database snapshot. The follow-up changes gave orders readable identifiers and made inaccessible orders return the same 404 response as missing orders.

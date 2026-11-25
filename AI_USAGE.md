# AI Usage

## Tools and scope

I used Codex to implement and test the application. I directed the follow-up reviews and chose which changes to incorporate, including readable order IDs and clearer access handling. The final submission was verified with 42 automated tests and a browser walkthrough.

I shared suggestions from a Claude review. Codex captured the demo and used macOS text-to-speech for narration.

## Representative requests

- Build the application to match the assignment brief.
- Recheck the extracted submission and fix reproducible issues.
- Apply the review feedback on order numbers, access responses, sample SQL, and test dependencies.

## Verification and corrections

The tests ran on MySQL 8.4.11 and covered concurrent order confirmations, stock restoration, order access, and CSV rollback. The Chromium walkthrough covered both user roles.

The review found that a malformed CSV record could report the wrong line and that a concurrent order update could make report sections disagree. The fixes report the record's starting line and use one database snapshot for the report. Both fixes have regression tests.

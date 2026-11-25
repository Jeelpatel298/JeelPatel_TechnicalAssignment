# AI Usage

## Tools and scope

I used OpenAI Codex to implement and test the application. Its work covered the Flask backend, browser interface, MySQL schema, reporting queries, and setup documentation. I provided the assignment brief, directed follow-up reviews, and selected changes to incorporate from a Claude review. Those changes included readable order numbers, clearer access responses, standalone sample SQL, and separate test dependencies. Codex also recorded the application walkthrough and used macOS text-to-speech for the narration.

## Representative requests

- Build the sales and inventory application from the assignment brief and package it with setup instructions.
- Verify the extracted submission and fix reproducible issues in the application or setup.
- Apply the review feedback and verify the updated submission.

## Verification

Codex ran 42 automated tests against MySQL 8.4.11. The tests covered pricing and discounts, simultaneous order confirmations, stock restoration, access restrictions, and CSV rollback. The Chromium walkthrough exercised both user roles, including order creation and cancellation, stock adjustments, reporting, and CSV uploads. Codex also checked the standalone sample SQL and verified the Git history in the extracted submission archive.

## Corrections from review

- **CSV validation** now identifies the starting line of a malformed record, even when a quoted value spans multiple lines.
- **Sales reporting** now reads all report sections from the same database snapshot, so a concurrent order update cannot make the sections disagree.
- **Order access** now returns the same `404` response for missing orders and orders outside a Sales User’s access.

These cases have regression tests in the submission.

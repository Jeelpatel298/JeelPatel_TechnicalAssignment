# AI Usage

## Tools

I used OpenAI Codex to develop and verify the submission. I also shared feedback from a separate Claude review.

## Project steps

1. **Build the application.** I shared the assignment brief with Codex. It drafted the Flask app, MySQL schema, SQL reports, tests, and setup instructions.
2. **Test and refine.** I asked for follow-up reviews and fixes. Codex tested order totals, stock updates, permissions, and CSV imports, then corrected the issues those checks uncovered.
3. **Apply reviewer feedback.** I shared Claude's suggestions and asked Codex to apply them. The updates included readable order numbers, a 404 response for inaccessible orders, sample catalog SQL, and separate test dependencies.
4. **Prepare the submission.** I supplied my Git email. Codex verified the extracted archive and recorded and narrated the browser demo.

## Representative requests

- Build the project from the attached assignment brief.
- Check the submission again and fix any mistakes found.
- Apply the review suggestions to the submission.

## Verification and corrections

Codex ran 42 tests on MySQL 8.4.11 and exercised both user roles in Chromium. The checks included simultaneous order confirmations, cancellation, and CSV rollback. Two fixes from the review were reporting the correct line for a malformed CSV record and running report queries against a single database snapshot.

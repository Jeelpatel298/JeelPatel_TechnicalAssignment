# AI Usage

## Tools and workflow

I used OpenAI Codex to help build this assignment from the supplied brief. Codex generated the initial Flask application, MySQL schema and queries, tests, and documentation. I requested several rounds of checking and fixes. I then shared suggestions from a separate Claude review and supplied my email for the submission’s Git history. Codex applied the revisions and recorded and narrated the updated demo.

## Representative requests

- Build the assignment from the attached brief.
- Check the submission again and fix any mistakes found.
- Apply the review suggestions for readable order numbers, order privacy, SQL sample data, Git attribution, and separate test dependencies.

## Verification

Codex verified the extracted submission with a clean dependency install, ran the test suite against MySQL 8.4.11, and exercised the application in Chromium. The checks covered order totals, user permissions, concurrent stock updates, failed-import rollback, the standalone SQL queries, and the reviewer setup steps.

## Changes made after review

- CSV import now rejects malformed prices and reports the correct starting line for malformed records.
- Report queries now share one database snapshot. Order actions capture their response before committing, so a later action cannot change the response to the first request.
- The review suggestions led to readable order numbers, a 404 response for inaccessible orders, an optional SQL catalog load, and a separate file for test dependencies.

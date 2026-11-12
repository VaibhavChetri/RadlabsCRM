# PRD — Radlabs CRM, Phase 1

Status: Draft · Date: 12 Nov 2026 · Owner: Radlabs · Source: grill-me session (19 decisions)

## Problem Statement

Radlabs runs cold-call outreach to B2B leads. Leads come from many places: Apollo exports, LinkedIn, referrals, events, and hand-made Excel sheets. Today the team has no single place to keep them.

- Leads sit in scattered spreadsheets. The same person shows up in several files.
- There is no record of who called whom, how many times, or when to call back.
- Follow-ups get missed because nobody sees "who do I call today".
- Managers cannot see the pipeline: how many leads are Interested, how many meetings were booked, how many deals were won, and who on the team is doing the calls.
- The current app was built as a lead inbox for a client's website contact form. Its model does not fit an internal sales CRM.
- Paid CRMs cost money per seat. Radlabs wants a robust tool that costs nothing to run.

## Solution

Rebuild the existing app into an internal Radlabs CRM for the sales team.

- Each team member has their own login. Everyone sees all leads, and each lead has an Owner (the assigned caller).
- Leads are imported from any source by uploading an Excel or CSV file. A mapping screen matches file columns to CRM fields. Saved presets mean an Apollo export maps automatically. A manual "Add lead" form covers one-off leads.
- Imports never create duplicates. A person who already exists is matched by email, phone or LinkedIn URL. Only their missing information is filled in. Their status, owner, notes and call history are never changed by an import.
- Each lead has a 10-stage cold-call pipeline, a +1 Call button, a Last called time, a Next follow-up date, a Priority (Hot / Warm / Cold), and a Notes thread: each saved note is kept with its author and time, newest first, so whoever takes over the lead has the full story.
- The home screen is "My call list today": overdue and today's follow-ups first, then the caller's new leads with Hot ones first.
- An analytics strip with visual charts sits on top. It shows the pipeline funnel, calls per day, leads added per day, and leads by source. It can show "Me" or "Team", and This week / This month / Custom dates.
- A Team stats page compares team members. An Admin page lets the admin add users, deactivate them, and reset passwords.
- "Submitted" becomes "Added to CRM".
- Phase 1 runs locally at no cost. It is configured through environment variables so it can move to a server later with no code changes.

## User Stories

### Access and team

1. As a team member, I want to log in with my own email and password, so that my calls and edits are recorded under my name.
2. As a team member, I want to stay logged in during my working session, so that I do not have to log in again all the time.
3. As a team member, I want to log out, so that nobody else can use my session on a shared machine.
4. As a team member, I want to see all leads in the CRM, not only mine, so that I can help colleagues and avoid calling a lead someone else already owns.
5. As the admin, I want to add a new team member with a name, email and temporary password, so that they can start calling the same day.
6. As the admin, I want to deactivate a team member who has left, so that they can no longer log in.
7. As the admin, I want the leads of a deactivated member to stay in the CRM, so that no data is lost.
8. As the admin, I want to reassign a deactivated member's leads to someone else, so that their follow-ups are not dropped.
9. As the admin, I want to reset a team member's password, so that they can get back in if they forget it.
10. As a team member, I want to be blocked from the admin Team page, so that only the admin manages accounts.
11. As a team member, I want a clear error when my login is wrong, so that I know to retry or ask the admin.
12. As a deactivated user, I want to be refused at login, so that access is really removed.

### Adding leads

13. As a team member, I want to upload an .xlsx or .csv file of leads, so that I can bring in leads from any tool without retyping them.
14. As a team member, I want to choose the Source of an upload (Apollo, LinkedIn, Referral, Event, Cold list, Other), so that we know where each lead came from.
15. As a team member, I want the CRM to suggest which file column matches which CRM field, so that mapping is quick.
16. As a team member, I want to change any suggested column match, or skip a column, so that wrong or useless columns are not imported.
17. As a team member, I want to save a column mapping as a named preset, so that the next file from the same tool maps automatically.
18. As a team member, I want a built-in Apollo preset, so that Apollo exports work with no setup.
19. As a team member, I want to preview the first rows as they will look in the CRM before importing, so that I can catch mapping mistakes.
20. As a team member, I want to choose "Assign to" on upload (one person, split evenly across the active team, or unassigned), so that new leads land with the right callers.
21. As a team member, I want an existing lead in the file to be recognised by email, phone or LinkedIn URL, so that the same person is never added twice.
22. As a team member, I want a recognised lead to only get its empty fields filled from the file, so that newer data is added without damaging what we already have.
23. As a team member, I want imports to never change a lead's Status, Owner, Notes, or call fields, so that our sales work is never overwritten by a file.
24. As a team member, I want rows with no email, no phone and no LinkedIn URL to be skipped, so that leads we cannot contact do not clutter the CRM.
25. As a team member, I want duplicate rows inside the same file to be merged, so that one file cannot create two copies of one person.
26. As a team member, I want emails and phone numbers cleaned (case, spaces, symbols) before matching, so that "Ravi@Acme.com" and "ravi@acme.com" count as the same person.
27. As a team member, I want a report after each import (added, updated, skipped, and why), so that I know what happened.
28. As a team member, I want to download the import report, so that I can fix and re-upload skipped rows.
29. As a team member, I want an import to either fully succeed or change nothing, so that a broken file never leaves half-imported data.
30. As a team member, I want a clear error for a wrong file type or a file that is too large, so that I know what to fix.
31. As a team member, I want to add a single lead with a form, so that a referral or a lead from a call can be entered straight away.
32. As a team member, I want the manual form to warn me if the lead already exists, so that I open the existing lead instead of making a copy.
33. As the admin, I want a list of past imports (who, when, file, source, counts), so that I can trace where leads came from.

### Working a lead

34. As a team member, I want a lead detail page with every field, so that I have the full picture before I call.
35. As a team member, I want to edit any field of a lead, so that I can correct and complete information during a call.
36. As a team member, I want to see first name, last name, job title, email, phone, second phone, LinkedIn URL, company, website, industry, company size, city and country, so that I know who I am calling and what their business is.
37. As a team member, I want to tap a phone number to call it, so that I do not have to dial by hand.
38. As a team member, I want a WhatsApp link next to the phone number, so that I can message a lead quickly.
39. As a team member, I want to open the lead's LinkedIn profile and website from the lead page, so that I can research them before calling.
40. As a team member, I want to press "+1 Call" each time I call a lead, so that the call is counted and Last called is set automatically.
41. As a team member, I want to see how many times a lead has been called, so that I know when to stop trying.
42. As a team member, I want to set a Next follow-up date, so that the lead comes back to me on the right day.
43. As a team member, I want to change a lead's status through the 10-stage pipeline (New, Attempted, Connected, Interested, Meeting booked, Proposal sent, Won, Lost, Not interested, Do not call), so that everyone sees where the lead stands.
44. As a team member, I want every status change saved with who changed it and when, so that the team stats are correct.
45. As a team member, I want to set Priority (Hot, Warm, Cold), so that the best leads are called first.
46. As a team member, I want to change a lead's Owner, so that leads can be handed over.
47. As a team member, I want to write a note and save it to the lead's Notes thread, so that I can record anything I learn on a call.
48. As a team member, I want each saved note to show my name and the date and time automatically, so that others can see who wrote what and when.
49. As a team member, I want to see every note on a lead below the write box, newest first, and I want notes never to be edited or deleted (they go only with the lead), so that a colleague who takes over the lead has the whole conversation.
50. As a team member, I want to see when a lead was added to the CRM and by whom, so that I know how old the lead is.
51. As a team member, I want to see when a lead was last updated, so that I can spot leads nobody is working.
52. As a team member, I want to delete a lead that is junk, so that the list stays clean.
53. As a team member, I want to be asked to confirm before a delete, so that I do not delete a lead by mistake.
54. As a team member, I want "Do not call" leads to be clearly marked, so that nobody calls them again.

### Daily call list (home)

55. As a caller, I want my home screen to show my overdue follow-ups first, so that I fix missed calls before anything else.
56. As a caller, I want to see today's follow-ups next, so that I keep my promises to leads.
57. As a caller, I want to see my New leads after that, Hot first, so that I spend fresh calling time on the best leads.
58. As a caller, I want +1 Call and a status dropdown right in the list, so that I can log a call without opening the lead.
59. As a caller, I want overdue follow-ups shown in red, so that they stand out.
60. As a caller, I want to open any lead from the list in one click, so that I can read notes before calling.
61. As a caller, I want leads in exit states (Won, Lost, Not interested, Do not call) kept out of my call list, so that I only see leads I should call.

### All leads table

62. As a team member, I want a table of all leads, so that I can browse the whole CRM.
63. As a team member, I want to search by name, company, email or phone, so that I can find a lead fast while they are on the phone.
64. As a team member, I want to filter by status, owner, source, priority and date added, so that I can build focused call lists.
65. As a team member, I want to filter "Unassigned", so that I can pick up leads nobody owns.
66. As a team member, I want to sort by date added, last called, next follow-up, priority and company, so that I can order the list the way I work.
67. As a team member, I want the "Added to CRM" date as a column, so that I can see the newest leads.
68. As a team member, I want the table split into pages, so that it loads fast with thousands of leads.
69. As a team member, I want to select many leads and change their status, owner or priority at once, so that bulk updates take seconds.
70. As a team member, I want to select many leads and delete them after a confirmation, so that I can clean up a bad import.
71. As a team member, I want to export the current filtered list to Excel, so that I can share or analyse it outside the CRM.
72. As a team member, I want the export to include the "Added to CRM" date, status, owner and notes, so that the file is complete.

### Analytics

73. As a team member, I want an analytics strip at the top of the home screen, so that I see our numbers every day.
74. As a team member, I want to switch the strip between "Me" and "Team", so that I can see my own work or the whole team's.
75. As a team member, I want to pick This week, This month or custom dates, so that I can look at any period.
76. As a team member, I want cards for Total leads, Leads added, Calls, Follow-ups due, Meetings booked, Won, and Conversion %, so that I see the key numbers at a glance.
77. As a team member, I want a pipeline funnel across all 10 stages, so that I can see where leads get stuck.
78. As a team member, I want a calls-per-day bar chart, so that I can see calling activity over time.
79. As a team member, I want a leads-added-per-day bar chart, so that I can see how fast the CRM is filling.
80. As a team member, I want a leads-by-source chart, so that I know which source gives the most leads.
81. As a manager, I want "Meetings booked" and "Won" to count status changes made in the chosen period, so that the numbers match what happened in that period.
82. As a manager, I want Conversion % to be Won ÷ leads added in the period, so that the rate is easy to explain.
83. As a manager, I want a Team stats page with one row per person (calls, leads by status, meetings booked, won) for the chosen period, so that I can compare activity and results.
84. As a manager, I want deactivated users still shown in past-period stats, so that history stays correct.

### Migration and cleanup

85. As the admin, I want the old website-enquiry leads exported to an Excel backup before the rebuild, so that nothing is lost.
86. As the admin, I want the CRM to start empty except for my admin account, so that test data does not mix with real leads.
87. As the admin, I want Radlabs@leads.com to keep working as the admin login, so that I do not need a new account.
88. As the admin, I want the old public website-form endpoint and new-lead email alert removed, so that nothing outside can write into the CRM.
89. As the admin, I want the SMTP settings kept in configuration, so that Phase 2 bulk email can use them.

## Implementation Decisions

### Modules

Deep modules (most of the logic behind a small, stable interface; tested alone):

- **Import engine.** Input: an uploaded file, a column mapping, a source, an "assign to" rule, and access to existing leads. Output: an import plan (rows to create, rows to update with exactly which fields, rows skipped with a reason) plus a summary report. Steps inside: read .xlsx/.csv → normalise headers → apply mapping → clean values → drop rows with no contact info → merge duplicates inside the file → ask the Lead matcher about each row → assign owners → build the plan. Applying the plan runs in one database transaction. Also suggests a mapping from header names and stores/loads named presets. Ships with a built-in Apollo preset.
- **Lead matcher / merger.** Input: a candidate lead (cleaned fields). Output: the matching existing lead, if any, and the merged field set. Match order: email (lowercase), then phone (digits only, compared on the last 10 digits), then LinkedIn URL (lowercase, no trailing slash or query). Merge rule: fill empty fields only. Protected fields that are never set by a merge: status, owner, notes, call attempts, last called, next follow-up, priority. Used by both the import engine and the manual "Add lead" form.
- **Stats engine.** Input: scope (one user or the whole team) and a date range. Output: all card values, the 10-stage funnel (current status counts), calls per day, leads added per day, leads by source, and the per-person team table. "Calls" come from the call log. "Meetings booked" and "Won" come from status-change history inside the range. Conversion % = Won in range ÷ leads added in range. Days with no data return zero so charts have no gaps.
- **Lead service.** All writes to a lead go through it: edit fields, +1 call (adds 1 to attempts, sets last called, writes a call-log row), change status (writes a status-change row with from/to/user/time), change owner, and add a note to the thread (signed with the author and time; notes are never edited). Bulk actions call the same service per lead so history is always written.

Thin modules (glue):

- **Auth and Users.** JWT login against the users table. The token holds the user's public id and role. A "require admin" guard protects the Team endpoints. Inactive users cannot log in, and their tokens are rejected.
- **Lead query.** Builds the list query from search text, filters (status, owner incl. unassigned, source, priority, date-added range), sort, and page. Returns rows plus a total count. Also builds the "today" list for the home screen.
- **Excel export.** Turns the current lead query into an .xlsx file.
- **Frontend.** React screens: Login, Home (analytics strip + call list), All leads, Lead detail, Import wizard, Team stats, Team admin. Shared API client with the token. Charts stay as CSS bars (no chart library), extending the current funnel and trend visuals.

### Schema

The old `clients` and `leads` tables are replaced.

- **users** — internal id, public uuid, name, email (unique), password hash, role (admin / member), is_active, created_at.
- **statuses** — id, name, sort order, is_exit flag. Seeded with the 10 stages. Exit stages: Won, Lost, Not interested, Do not call. Stages live in a table so they can be renamed or added later without a code change.
- **leads** — internal id, public uuid; first name, last name, job title, email, phone, second phone, LinkedIn URL, company, website, industry, company size, city, country; source; priority (hot / warm / cold); status (FK); owner (FK, nullable); call attempts (default 0), last called at, next follow-up (date); created by, created at ("Added to CRM"), updated at. Indexed on: email, phone, LinkedIn URL, status, owner, next follow-up, created at.
- **calls** — id, lead (FK, delete with the lead), user (FK), called at. One row per +1 Call.
- **lead_notes** — id, lead (FK, delete with the lead), user (author), body (long text), created at. One row per saved note; never edited.
- **status_changes** — id, lead (FK, delete with the lead), from status, to status, user, changed at. A new lead writes a first row (no "from" → New) so "added" and status history line up.
- **import_presets** — id, name (unique), mapping (JSON: file header → CRM field), is_builtin.
- **imports** — id, user, file name, source, added count, updated count, skipped count, created at.

Source is a fixed list in code: Apollo, LinkedIn, Referral, Event, Cold list, Other.

### API contract (all routes need a valid login except login itself)

- Auth: log in → token; "me" → current user with role.
- Users (admin only): list, add, update (name, role, active), reset password.
- Statuses: list in pipeline order.
- Leads: list (search, filters, sort, page → rows + total); create (runs the matcher; returns 409 with the existing lead's id when a duplicate is found); get one; update any editable fields; delete; +1 call; bulk update (status / owner / priority) and bulk delete by list of ids; today list for the current user; export to .xlsx using the same filters as list.
- Imports: preview (upload → headers, first 5 rows, suggested mapping, matched preset); run (file + mapping + source + assign-to → report); history; presets list / save.
- Stats: summary (scope = me | team, from, to) → cards and charts; team table (from, to).
- Leads are addressed by public uuid in all URLs. Internal integer ids never leave the API.

### Other decisions

- Limits: .xlsx and .csv only; 5 MB and 5,000 data rows per file.
- "Split evenly" assigns round-robin across active users, in a stable order.
- Times are stored in UTC and shown in the browser's local time (IST for the team). "Today" and date ranges use the user's local date.
- The admin account is the existing Radlabs@leads.com login, moved into the users table with role admin.
- Old data: a one-time script exports the old leads and client list to Excel, then the migration drops the old tables and creates the new ones.
- The public website-form endpoint and the new-lead email alert are removed. SMTP variables stay in the environment file, unused.
- Configuration (database URL, JWT secret, allowed frontend origin, API base URL for the frontend) comes from environment variables, so the app can be hosted later with no code change.
- Database: MySQL 9.7 (Homebrew `mysql@9.7`), database `leadsdb`.

### Testing decisions

Good tests here check what a module does from outside (inputs → outputs, or HTTP request → response and database state). They do not check private helpers or how the code is written inside. Tests use pytest and a separate test MySQL database that is created fresh for the test run. No mocks for the database. There are no existing automated tests; the Postman collection is the only prior art and will be updated or retired.

Modules with tests:

- **Import engine + Lead matcher.** Sample files: a real-shaped Apollo export, a messy hand-made Excel (odd headers, blank rows, mixed phone formats), a CSV. Cases: header suggestion and preset use; email / phone / LinkedIn matching and their order; fill-blanks-only merge; protected fields never change; duplicates inside one file; rows without contact info skipped with the right reason; assign-to modes including split evenly; report counts; all-or-nothing on failure; file type and size limits.
- **Stats engine.** Seeded users, leads, calls and status changes over several weeks. Cases: Me vs Team; week, month and custom ranges; zero-filled days; meetings booked and won counted by change date, not current status; conversion %; per-person table including deactivated users.
- **Lead service.** +1 call updates attempts, last called and writes a call row; status change writes history with the right from/to; adding a note keeps author and time, empty note refused; bulk actions write history for every lead.
- **API end-to-end.** Login, wrong password, inactive user refused; member blocked from admin routes; leads CRUD by uuid; duplicate on manual create returns 409; filters, sort and paging; export returns a valid .xlsx; import preview and run over HTTP; stats endpoints return the expected shape.

## Out of Scope

- Bulk email or any sending of email (Phase 2, will reuse the SMTP setup).
- Apollo API integration, Google Sheet sync, or any automatic lead feed.
- Public website-form intake.
- Custom fields defined from the UI.
- A UI to edit pipeline stages (stages live in a table but are changed by a developer for now).
- Kanban / drag-and-drop pipeline board.
- A per-call log with outcomes, or a full activity timeline (calls and status changes are logged, but only the Notes thread is shown as a thread).
- Role-based visibility (callers seeing only their own leads).
- Hosting, domains, HTTPS, backups in the cloud.
- Mobile app. The web app should still work on a phone browser for click-to-call.

## Further Notes

- MySQL was moved from 9.6 to 9.7 on 12 Nov 2026 to fix a broken Homebrew library. A copy of the 9.6 data folder is at `/opt/homebrew/var/mysql_backup_9.6_20261112`. The Homebrew `mysql` package (now v26) is installed but not used; run `mysql@9.7`.
- The frontend entry file was missing and was recreated on 12 Nov 2026.
- The original code is already preserved in another repository by the owner.
- Apollo's free plan allows CSV export, so the file-upload path keeps lead intake at $0 and does not depend on Apollo's API terms.
- Volume assumption: up to tens of thousands of leads and a team of under 20 people. Simple indexed queries are enough. No caching or background jobs in Phase 1.

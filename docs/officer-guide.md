# Officer guide (one page)

**Sign in** at `#/officer` with your email and password. (At the expo, "Use the expo PIN instead" signs you in as
"Duty officer".) Everything you do is shown on the public report page with your name, except the full internal history.

## Work queue
- Top to bottom is the order to work in: urgency first, then the nearest deadline, then severity, then how many
  citizens reported the spot. Red-edged rows are past their deadline.
- Filter by ward, urgency, code, or "Past deadline only". Switch to **Map** to see where they are.
- Tick several rows to change their status together.

## On a report (right-hand panel)
1. **Confirm** the AI: check the photo; correct the problem type or severity if needed. Corrections are counted in
   "AI agreement" on the Analytics tab. Urgency always follows the rules (an open manhole is always Critical).
2. **Assign** to a crew or person (type a new name or pick one). The citizen gets an email if they left one.
3. **Add an official update** for the public, e.g. "Crew reaching by 4 pm".
4. When the work is done, **Upload repair photo** from the site. The AI checks it:
   - no damage left → the report becomes **Resolved** and the public page shows before and after;
   - damage still visible → it is **reopened** and assigned again, with what the AI still sees.
5. **Dismiss** only with a reason; the reason is public (e.g. "Private road, not maintained by the city").
6. **Merge** a duplicate into the main report code; **Separate** if that was a mistake.

## Needs a check
Photos the AI was unsure about, and reports sent while the AI was busy. They are **not public** until you confirm
the problem and severity, or dismiss them (screenshots, non-road photos).

## Work orders
Pick a crew to get its open reports in a short driving order (nearest next stop), with deadlines and the repair
method. **Print** it for the crew.

## Analytics
Reported vs resolved per day, average days to fix by urgency and ward, share fixed within the deadline, most common
problems, and how often officers change the AI's answer.

## Officers (administrators only)
Add officers (password at least 10 characters), deactivate leavers, reset passwords, export all data as CSV
(includes citizen notes; never their email or device).

## Deadlines
| Urgency | Fix within |
|---|---|
| Critical | 24 hours |
| High | 48 hours |
| Medium | 7 days |
| Low | next quarterly round |

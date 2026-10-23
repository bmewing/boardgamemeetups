# Board Game Group App — Build Plan

A web app for organizing board game meetups. Users log in, import their game collections (matched to BoardGameGeek IDs), rate games, say which player counts they think work best, and keep a wishlist. They add friends, form persistent groups (with a recurring schedule) or create one-off meetups. Invitees RSVP and pick a "mood". The meetup page recommends games from the attendees' combined libraries; the group votes, and whoever owns the winning game is tagged to bring it.

## Decisions

- **Stack:** FastAPI (Python) backend + React (Vite + TypeScript) SPA
- **Auth:** Kinde (React SDK in the browser; FastAPI checks Kinde JWTs against Kinde's JWKS)
- **DB:** Free external Postgres (Neon free tier). SQLAlchemy 2 + Alembic.
- **Hosting:** DigitalOcean App Platform, personal account. One app with two components:
  - React build as a **static site** (free tier) at `/`
  - FastAPI as a **web service** (~$5/mo basic instance) at `/api`, so they share an origin and there's no CORS to deal with
  - Expected cost is about **$5/mo**
- **Groups:** both persistent groups (with a recurring schedule; each occurrence editable on its own) and ad-hoc meetups

## Considerations beyond the core features

These are folded into the checklist below.

- **BGG API access needs registration.** BGG's XML API2 requires a registered app plus a bearer token, and BGG requires "Powered by BGG" attribution. Sign up early because approval can take a while.
- **Easiest import path:** BGG's own collection CSV export already includes `objectid`, so matching is free. Also support importing by BGG username, plus a generic CSV/text list of names that needs fuzzy matching and a review screen.
- **Inviting people who don't have an account yet.** An invite link or email invite. Without it, nobody can bootstrap a group.
- **Notifications:** emails for invites, RSVP reminders, the final game pick, and "you're bringing X". Resend's free tier covers this.
- **Host role and permissions:** who can edit, cancel, lock the vote, or reassign who brings what. Optional co-hosts.
- **Capacity:** the host's max seats, plus-ones/guests, and a waitlist.
- **Game length vs. meetup length:** a 4-hour game shouldn't be recommended for a 2-hour evening.
- **Big groups:** with 9 people, the recommendation should be "two tables", not one game. This is v2, but the data model should allow it.
- **Expansions:** treat them as attached to their base game, not as separate recommendations.
- **Close the loop:** log what was actually played after a meetup. That feeds "recently played" into future recommendations.
- **Privacy:** the address is shown only to invitees, and users control who can see their collection (friends vs. public).
- **Time zones and calendar export** (.ics file / "add to calendar").
- **Mobile-first UI:** most RSVPs and votes will happen on phones.
- **Account deletion and data export:** basic hygiene.

---

## Checklist

### Phase 0 — Accounts & setup
- [x] Create GitHub repo (`bmewing/boardgamemeetups`)
- [ ] Protect `main` (require CI to pass)
- [ ] Register app with BGG XML API; store bearer token
- [ ] Kinde: create business/app (React SPA type), set callback/logout URLs for localhost + prod, define an API audience for FastAPI
- [ ] Neon: create project + database; grab pooled + direct connection strings
- [ ] DigitalOcean (personal account): confirm billing, decide on domain (or use `*.ondigitalocean.app` initially)
- [ ] Resend (or Postmark) account for transactional email; verify sending domain

### Phase 1 — Project scaffolding
- [x] Monorepo layout: `backend/` (FastAPI) and `frontend/` (Vite + React + TS)
- [x] Backend: FastAPI, SQLAlchemy 2 (async), Alembic, pydantic-settings, `uv` for deps
- [x] Frontend: Vite, React Router, TanStack Query, Mantine, API client generated from FastAPI's OpenAPI schema
- [x] `docker-compose.yml` with local Postgres for dev
- [x] Lint/format: ruff + mypy (backend), oxlint + prettier (frontend)
- [x] Tests: pytest + httpx test client (backend), vitest (frontend)
- [x] GitHub Actions CI: lint + test both halves on PR
- [x] `.env.example` for both halves; README with local run steps
- **Done when:** `docker compose up` + `uv run fastapi dev` + `npm run dev` gives a hello-world page calling `/api/health`

### Phase 2 — Auth & users
- [ ] Frontend: Kinde React SDK login/logout, protected routes
- [ ] Backend: dependency that verifies Kinde access token (JWKS, audience, issuer) and returns current user
- [ ] `users` table; upsert on first authenticated request (kinde_id, email, display name, avatar)
- [ ] Profile page: display name, time zone, BGG username (optional), collection visibility
- [ ] Account deletion endpoint
- **Done when:** can log in on localhost, see your profile, and an unauthenticated API call returns 401

### Phase 3 — Game catalog & BGG integration
- [ ] BGG client: bearer token, polite rate limiting (queue + backoff on 202/429), batch `thing` lookups (up to 20 IDs)
- [ ] `games` table caching BGG data: id, name, year, image/thumbnail, min/max players, min/max playtime, weight, categories, mechanics, BGG suggested-player-count poll results, is_expansion + base game link, `fetched_at`
- [ ] Refresh policy (re-fetch if stale > N days, lazily)
- [ ] Game search endpoint (local cache first, fall back to BGG search)
- [ ] "Powered by BGG" attribution in footer/game pages
- **Done when:** searching "Wingspan" returns the right game with player counts and image

### Phase 4 — Collection import & matching
- [ ] `collection_items` (user, game, owned, notes, added_at)
- [ ] Import by BGG username (collection API, owned flag)
- [ ] Upload BGG CSV export → match by `objectid` directly
- [ ] Upload generic CSV/TXT of names → exact match, then fuzzy (BGG search + rapidfuzz on name/year) → confidence score
- [ ] Import review screen: auto-matched, needs-review (pick from candidates), unmatched (manual search)
- [ ] Manual add/remove single game
- [ ] Collection page (grid/list, filters by player count/weight/length)
- **Done when:** a BGG CSV and a messy plain list both end up as a fully matched collection

### Phase 5 — Ratings, player-count opinions, wishlist
- [ ] `game_ratings` (user, game, rating 1–10)
- [ ] `player_count_opinions` (user, game, count, verdict: best / good / bad) — UI as a row of tappable counts per game
- [ ] `wishlist_items` (user, game, priority, note): "want to play", any game in the catalog, not just owned
- [ ] Show BGG's community best-count alongside the user's own opinion
- **Done when:** can rate, set player-count opinions, and wishlist games from both the collection and search

### Phase 6 — Friends & invites
- [ ] `friendships` (requester, addressee, status: pending/accepted/blocked)
- [ ] Find friends by email / display name; send/accept/decline/remove
- [ ] Shareable invite link (signed token) that creates the friendship after the new user signs up
- [ ] Friend profile: view their collection/wishlist (respecting visibility)
- **Done when:** two test accounts can befriend each other via search and via invite link

### Phase 7 — Groups (persistent + recurring)
- [ ] `groups` (name, description, owner) + `group_members` (role: owner/admin/member)
- [ ] Add/remove members (from friends or invite link)
- [ ] Recurrence on group: RRULE (weekly / every N weeks / monthly nth weekday), default start time, duration, location, time zone. Use `python-dateutil`
- [ ] Occurrences materialized as `meetups` rows for a rolling window (e.g. next 8 weeks), generated lazily when the group is viewed and when the schedule changes
- [ ] Each occurrence editable on its own (date/time/place/notes, or cancelled); flag `is_overridden` so schedule changes regenerate only untouched future occurrences
- [ ] Group page: members, upcoming occurrences, schedule editor
- **Done when:** a weekly group shows the next 8 dates; moving one date leaves the others alone; changing the rule to biweekly updates only untouched future dates

### Phase 8 — Meetups, RSVP & mood
- [ ] `meetups` (title, host, optional group_id, start, end/duration, time zone, location name + address, max seats, notes, status: scheduled/cancelled/done)
- [ ] Ad-hoc meetup creation: pick friends and/or a group's members
- [ ] `meetup_invites` (meetup, user, status: invited/yes/no/maybe, plus_ones, mood, rsvp_at)
- [ ] Mood taxonomy (seeded table, each with tag weights used by recs), e.g. *Light & quick, Party/social, Strategic/heavy, Co-op, Cutthroat, Thematic/adventure, Something new, Old favorite, No preference*
- [ ] RSVP UI: one tap yes/no/maybe + mood picker; can change until the vote locks
- [ ] Headcount summary (confirmed + plus-ones vs. max seats; waitlist if over)
- [ ] Address only visible to invitees; .ics download
- **Done when:** host creates a meetup, 3 test users RSVP with moods, headcount is correct

### Phase 9 — Recommendations
- [ ] Candidate pool = games owned by confirmed attendees (expansions folded into base)
- [ ] Hard filters: player count fits the confirmed headcount; playtime fits the meetup duration
- [ ] Scoring (weighted, tunable in one config module):
  - player-count fit (attendees' own best/good/bad opinions, falling back to the BGG poll)
  - mood match (mood tag weights vs. game categories/mechanics/weight)
  - attendees' average rating (unrated = neutral)
  - wishlist hits among attendees (strong boost)
  - novelty ("something new" mood boosts games few attendees have rated or played)
  - recently played penalty (from Phase 10 play logs)
- [ ] "Why this game" explanation chips (e.g. "3 want to play · best at 5 · matches Strategic")
- [ ] Recompute on RSVP change; show top ~10
- [ ] Unit tests with fixture attendees/libraries for scoring edge cases
- **Done when:** recs change sensibly as people RSVP and switch moods, and each rec explains itself

### Phase 10 — Voting, bring assignment & play log
- [ ] `meetup_nominations` (from recs or any attendee-owned game) + `meetup_votes` (approval voting: vote for any number)
- [ ] Live tally; host "locks" the pick(s), and more than one pick is allowed
- [ ] Bring assignment: default to the attending owner (if several, the host picks or the first volunteer claims it); `bring_assignments` table
- [ ] After the meetup: "what did we play?" log → `plays` table (feeds recently-played)
- **Done when:** a full meetup cycle runs: RSVP → recs → vote → lock → owner tagged → play logged

### Phase 11 — Notifications
- [ ] Email service wrapper (Resend) with templates
- [ ] Triggers: invited, friend request, RSVP reminder (X days before), pick locked, "you're bringing X", meetup changed/cancelled
- [ ] Per-user notification preferences
- [ ] Scheduled reminders: a DO App Platform scheduled job if available on the plan, otherwise a lightweight cron (GitHub Actions schedule hitting a protected endpoint)
- **Done when:** each trigger sends a real email in staging

### Phase 12 — Deploy to DigitalOcean
- [ ] Dockerfile for backend (uvicorn/gunicorn), health check at `/api/health`
- [ ] `.do/app.yaml` spec: static site (frontend build) + web service (backend) with route `/api`, plus a pre-deploy job running `alembic upgrade head`
- [ ] Env vars/secrets in DO: DB URL (Neon, `sslmode=require`), Kinde domain/audience, BGG token, Resend key
- [ ] Kinde prod callback URLs; custom domain + TLS (optional)
- [ ] Auto-deploy from `main`
- [ ] Neon branch for staging, or just a second Neon DB
- **Done when:** production URL works end-to-end with a real login

### Phase 13 — Post-MVP / nice-to-haves
- [ ] Multi-table splitting for big groups (recommend 2 games that together seat everyone)
- [ ] PWA install + push notifications
- [ ] Ranked-choice voting option
- [ ] Group stats (most played, H-index, who brings what most)
- [ ] Periodic BGG collection re-sync
- [ ] "Teach" flag: who knows the rules for each game

---

## Verification

- Every phase has a **Done when** line. Don't tick a phase until that scenario passes manually on localhost and its tests pass in CI.
- Keep a seed script (`backend/scripts/seed.py`) that creates 4–5 test users with collections, ratings, wishlists, friendships, a recurring group, and a meetup, so the full flow can be clicked through quickly after any change.
- After Phase 12, rerun the Phase 10 end-to-end scenario against production.

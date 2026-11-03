# Board Game Group App — Build Plan

A web app for organizing board game meetups. Users log in, import their game collections (matched to BoardGameGeek IDs), rate games, say which player counts they think work best, and keep a wishlist. They add friends, form persistent groups (with a recurring schedule) or create one-off meetups. Invitees RSVP and pick a "mood". The meetup page recommends games from the attendees' combined libraries; the group votes, and whoever owns the winning game is tagged to bring it.

## Decisions

- **Stack:** FastAPI (Python) backend + React (Vite + TypeScript) SPA
- **Auth:** Kinde (React SDK in the browser; FastAPI checks Kinde JWTs against Kinde's JWKS)
- **DB:** Free external Postgres (Supabase free tier, used as plain Postgres via its transaction pooler, which suits serverless). Local dev uses a locally installed Postgres. SQLAlchemy 2 + Alembic.
- **Hosting:** DigitalOcean App Platform, personal account (b.mark@ewingsonline.com). One app, `boardgamemeetups`, with two components on one origin (no CORS):
  - React build as a **static site** at `/`
  - The FastAPI app as **one DigitalOcean function** (`core/app`, Python 3.13) behind `/api`, via an adapter (`backend/app/serverless.py`)
  - Expected cost is about **$3/mo**: the account's 3 free static-site apps are already used, and Functions usage should stay in its free allowance
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
- **Supabase free tier pauses after a week without activity.** Fine while people use the app. Functions get no platform health checks, so if usage is sparse, add a weekly GitHub Actions ping of `/api/health`.
- **Privacy:** the address is shown only to invitees, and users control who can see their collection (friends vs. public). Joining a group (invited, then confirmed) shares all of your game data with that group's members under your name, whatever your collection visibility says.
- **Time zones and calendar export** (.ics file / "add to calendar").
- **Mobile-first UI:** most RSVPs and votes will happen on phones.
- **Account deletion and data export:** basic hygiene.

---

## Checklist

### Phase 0 — Accounts & setup
- [x] Create GitHub repo (`bmewing/boardgamemeetups`)
- [ ] Protect `main` (require CI to pass)
- [x] Register app with BGG XML API; store bearer token
- [x] Kinde: create business/app (React SPA type), set callback/logout URLs for localhost + prod, define an API audience for FastAPI
- [x] Supabase: create project; grab the **transaction pooler** connection string (port 6543; the direct connection is IPv6-only on the free tier)
- [x] DigitalOcean (personal account): confirm billing, decide on domain (or use `*.ondigitalocean.app` initially)
- [ ] Resend (or Postmark) account for transactional email; verify sending domain

### Phase 1 — Project scaffolding ✅
- [x] Monorepo layout: `backend/` (FastAPI) and `frontend/` (Vite + React + TS)
- [x] Backend: FastAPI, SQLAlchemy 2 (async), Alembic, pydantic-settings, `uv` for deps
- [x] Frontend: Vite, React Router, TanStack Query, Mantine, API client generated from FastAPI's OpenAPI schema
- [x] Local Postgres for dev (installed locally, no Docker)
- [x] Lint/format: ruff + mypy (backend), oxlint + prettier (frontend)
- [x] Tests: pytest + httpx test client (backend), vitest (frontend)
- [x] GitHub Actions CI: lint + test both halves on PR
- [x] `.env.example` for both halves; README with local run steps
- **Done when:** local Postgres + `uv run fastapi dev` + `npm run dev` gives a hello-world page calling `/api/health`

### Phase 2 — Auth & users ✅
- [x] Frontend: Kinde React SDK login/logout, protected routes
- [x] Backend: dependency that verifies Kinde access token (JWKS, audience, issuer) and returns current user
- [x] `users` table; upsert on first authenticated request (kinde_id, email, display name, avatar)
- [x] Profile page: display name, time zone, BGG username (optional), collection visibility
- [x] Account deletion endpoint
- **Done when:** can log in on localhost, see your profile, and an unauthenticated API call returns 401

### Phase 3 — Game catalog & BGG integration ✅
- [x] BGG client: bearer token, polite rate limiting (queue + backoff on 202/429), batch `thing` lookups (up to 20 IDs)
- [x] `games` table caching BGG data: id, name, year, image/thumbnail, min/max players, min/max playtime, weight, categories, mechanics, BGG suggested-player-count poll results, is_expansion + base game link, `fetched_at`
- [x] Refresh policy (re-fetch if stale > N days, lazily)
- [x] Game search endpoint (local cache first, fall back to BGG search)
- [x] "Powered by BGG" attribution in footer/game pages
- [x] Load BGG's ranks CSV (all game names/ranks) with `app.import_bgg_ranks` (182,688 games locally; the download needs a logged-in BGG session, not the app token)
- [x] Load the ranks CSV into Supabase (182,688 games, 60 MB of the 500 MB free tier)
- [ ] Refresh the ranks CSV now and then (manual download while logged in to BGG)
- **Done when:** searching "Wingspan" returns the right game with player counts and image

### Phase 4 — Collection import & matching

Per-user game data lives in one row per user per game, so a user can rate or tag any game, owned or not, and one import can fill every field. Blank always means "no opinion"; the UI may show a default (e.g. "just right") without storing it, so group results only count real answers.

- [x] `moods` (seeded list; the tag weights for the fallback guess from categories/mechanics/weight come with Phase 9), e.g. *Light & quick, Party/social, Laughs, Chill, Brain-burner, Cutthroat, Thematic/story, Family-friendly*. Used both to tag games and to pick an RSVP mood. Meetup-only moods that describe the group's history (*Something new, Old favorite, No preference*) can't be tagged on a game
- [x] `user_games` (user, game, plus):
  - ownership: `owned` / `previously_owned` / `preordered` / none
  - `wishlist_priority` (1–5, blank = not wishlisted), `want_to_play`
  - `rating` (decimal 1–10, BGG's scale and labels)
  - `weight_vote` (1–5, BGG's Light … Heavy scale)
  - `playtime_feel` (shorter / just right / longer vs. the listed time)
  - `can_teach`, and `teach_minutes`, required when `can_teach` is set
  - `plays` (count; imported from BGG `numplays`, then added to by the Phase 10 play log)
  - `will_bring` (owned copies only, default yes; no for a copy that's lent out or stays home)
  - `notes`, `source` (bgg / file / manual), timestamps; the last applied pull is `users.bgg_pulled_at`
- [x] `user_game_player_counts` (user, game, count, vote: best / recommended / not recommended), the same answers as BGG's poll so group votes add straight onto `games.player_count_votes`
- [x] `user_game_moods` (user, game, mood)
- [ ] Expansions are owned games of their own; an owned expansion's player range widens its base game's range
- [x] **Pull from BGG** (`/collection/pull`: `POST /api/me/games/bgg-pull` previews, `POST /api/me/games/import` applies the kept changes) (by BGG username, collection API): fetch, compute the diff against our data, show a preview before anything is written (new games, blanks that would be filled, values that would be **overwritten**, games owned here but not on BGG), then apply on confirm. BGG doesn't expose a user's own weight or player-count votes, so those only come from our UI or a file
- [x] Upload BGG CSV export → match by `objectid` directly, then the same diff preview as a pull (untested with a real export: BGG's column names are assumed)
- [x] Upload any Excel/CSV/text list (`/collection/import`): the user says what each column holds (guessed from headers; several columns can feed notes), and where the whole file goes (owned / wishlist / neither) when no column says. A template is at `/game-list-template.csv`
- [ ] Player-count votes and moods as file columns
- [x] "Find missing base games" on My games: base games of owned expansions that aren't owned, grouped by base game; an expansion that fits several base games is offered once with its best-known options. "Not interested" is remembered (`removed_games`)
- [x] Name matching for files without BGG IDs → exact match ignoring punctuation and a trailing ", The", year when given, the far-better-known game among same-named ones, "X" for a base game named "X: Subtitle", then `pg_trgm` candidates for review (134-row example: 115 matched, ~6 s locally)
- [x] Import review screen: rows needing a look (one-click candidates), matched rows, and an inline Search BGG box on every row; then the diff preview
- [x] Manual add/remove single game (the "My games" panel on a game's page)
- [x] Remove from the My games list too, optionally with the game's expansions; removed games are remembered (`removed_games`) so later imports offer them unticked, until the user adds them back
- [x] Collection page (grid/list, filters by player count/weight/length); fetches BGG details for pulled games a batch at a time while open
- **Done when:** a BGG pull, a BGG CSV and a messy plain list each end up as a fully matched collection, and a second pull shows an accurate overwrite preview

**Phase 4 notes: BGG is pull-only.** BGG's XML API is read-only. Writing back would mean driving BGG's website with the user's own BGG login, which means holding their BGG password and likely breaks the terms of our registered app. So data only flows from BGG to us, never back, and every pull or file import is previewed as a diff and applied only on confirm.

### Phase 5 — Editing your game data
- [ ] Game page and collection rows: edit every `user_games` field from either the collection or search
- [ ] Player counts as a row of tappable counts per game (tap cycles best → recommended → not recommended → blank), with a one-tap "best at N" shortcut
- [ ] "Can teach" asks for teach time before it saves
- [ ] Mood tags as chips from the `moods` list
- [ ] Show BGG's community values (rating, weight, best count, playing time) alongside the user's own
- **Done when:** can set every field from both the collection and search, and BGG's values show beside your own

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
- [ ] Group library: every member's games with the group's combined view and each member's answers by name (see "Group roll-ups" under Phase 9)
- **Done when:** a weekly group shows the next 8 dates; moving one date leaves the others alone; changing the rule to biweekly updates only untouched future dates

### Phase 8 — Meetups, RSVP & mood
- [ ] `meetups` (title, host, optional group_id, start, end/duration, time zone, location name + address, max seats, notes, status: scheduled/cancelled/done)
- [ ] Ad-hoc meetup creation: pick friends and/or a group's members
- [ ] `meetup_invites` (meetup, user, status: invited/yes/no/maybe, plus_ones, mood, rsvp_at)
- [ ] RSVP moods come from the Phase 4 `moods` list, plus the meetup-only *Something new, Old favorite, No preference*
- [ ] RSVP UI: one tap yes/no/maybe + mood picker; can change until the vote locks
- [ ] Headcount summary (confirmed + plus-ones vs. max seats; waitlist if over)
- [ ] Address only visible to invitees; .ics download
- **Done when:** host creates a meetup, 3 test users RSVP with moods, headcount is correct

### Phase 9 — Recommendations
- [ ] Candidate pool = games owned by confirmed attendees and marked "will bring" (expansions folded into base, widening its player range)
- [ ] Hard filters: player count fits the confirmed headcount; playtime (plus teach time when someone attending is new to it) fits the meetup duration
- [ ] Group roll-ups, computed per query over the people in scope (group members for the library, confirmed attendees for a meetup); groups are small, so nothing is stored:
  - rating: average pulled toward BGG's rating when few have rated, `(sum + 2 × bgg_rating) / (n + 2)`; also show the lowest rating, and treat 3 or below as a soft veto
  - player count: group votes added onto BGG's poll counts, group votes weighted higher; read off at the headcount
  - weight: group average blended with BGG's weight the same way as rating
  - playtime: BGG's time adjusted by the net shorter/longer votes; replaced by the median logged duration once Phase 10 plays exist
  - mood: share of people who tagged each mood; fall back to the guess from categories/mechanics/weight for untagged games
  - teaching: who's new to it (`plays` = 0 and not previously owned), who can teach, and their teach time
  - owners willing to bring it; wishlist and want-to-play counts
- [ ] Scoring (weighted, tunable in one config module):
  - player-count fit (from the roll-up above)
  - mood match (roll-up mood shares vs. attendees' RSVP moods)
  - attendees' rating (roll-up above; unrated = neutral), with a penalty for soft vetoes
  - wishlist and want-to-play hits among attendees (strong boost)
  - novelty ("something new" mood boosts games few attendees have played)
  - teach cost (new players with no teacher attending is a penalty; with one, teach time counts against the meetup length)
  - recently played penalty (from Phase 10 play logs)
- [ ] "Why this game" explanation chips (e.g. "3 want to play · best at 5 · matches Brain-burner · Sam can teach (15 min)")
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
- [ ] Scheduled reminders: a GitHub Actions cron hitting a protected endpoint (Functions on App Platform can't be scheduled yet)
- **Done when:** each trigger sends a real email in staging

### Phase 12 — Deploy to DigitalOcean
- [x] Run the API as a DigitalOcean function: Python 3.13, `web: raw` adapter, no connection pool, pooler-safe statements, BGG throttle shared through Postgres
- [x] `functions/` project (vendors `backend/app`, builds deps in DO's Python 3.13 container; bundle ~19 MB zipped of the 48 MB limit)
- [x] `.do/app.yaml` spec: static site + functions component, `/api` routed to the function
- [x] Migrations applied to Supabase (`uv run --env-file .env.production alembic upgrade head`; rerun before deploying new migrations, since Functions-only apps have no pre-deploy job)
- [x] Env vars/secrets in DO: DB URL (Supabase transaction pooler, `sslmode=require`), BGG token
- [ ] Resend key (Phase 11)
- [x] First deploy: https://boardgamemeetups-i59h7.ondigitalocean.app (auto-deploys on push to `main`)
- [x] Kinde prod callback URLs
- [ ] Own OAuth credentials for Google, Facebook and Discord in Kinde (dev currently uses Kinde's shared keys, so consent screens name Kinde, not this app)
- [ ] Kinde custom domain (e.g. `auth.<your-domain>`) so sign-ins survive page reloads without keeping the refresh token in localStorage (only allowed in local dev)
- [ ] App custom domain + TLS (optional)
- [x] Auto-deploy from `main`
- [ ] Staging database: a second Supabase project (free tier allows two)
- **Done when:** production URL works end-to-end with a real login (met 2026-11-03; the open items above can follow later)

### Phase 13 — Post-MVP / nice-to-haves
- [ ] Multi-table splitting for big groups (recommend 2 games that together seat everyone)
- [ ] PWA install + push notifications
- [ ] Ranked-choice voting option
- [ ] Group stats (most played, H-index, who brings what most)
- [ ] Reminder to pull from BGG when the last pull is old (still previewed and confirmed by the user, never silent)

---

## Verification

- Every phase has a **Done when** line. Don't tick a phase until that scenario passes manually on localhost and its tests pass in CI.
- Keep a seed script (`backend/scripts/seed.py`) that creates 4–5 test users with collections, ratings, wishlists, friendships, a recurring group, and a meetup, so the full flow can be clicked through quickly after any change.
- After Phase 12, rerun the Phase 10 end-to-end scenario against production.

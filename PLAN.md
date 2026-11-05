# Board Game Group App — Build Plan

A web app for organizing board game meetups. Users log in, import their game collections (matched to BoardGameGeek IDs), rate games, say which player counts they think work best, and keep a wishlist. They add friends and form groups, which meet on a recurring schedule, on dates added one at a time, or both. Members RSVP and pick a "mood". The meetup page recommends games from the attendees' combined libraries; the group votes, and whoever owns the winning game is tagged to bring it.

## Decisions

- **Stack:** FastAPI (Python) backend + React (Vite + TypeScript) SPA
- **Auth:** Kinde (React SDK in the browser; FastAPI checks Kinde JWTs against Kinde's JWKS)
- **DB:** Free external Postgres (Supabase free tier, used as plain Postgres via its transaction pooler, which suits serverless). Local dev uses a locally installed Postgres. SQLAlchemy 2 + Alembic.
- **Hosting:** DigitalOcean App Platform, personal account (b.mark@ewingsonline.com). One app, `boardgamemeetups`, with two components on one origin (no CORS):
  - React build as a **static site** at `/`
  - The FastAPI app as **one DigitalOcean function** (`core/app`, Python 3.13) behind `/api`, via an adapter (`backend/app/serverless.py`)
  - Expected cost is about **$3/mo**: the account's 3 free static-site apps are already used, and Functions usage should stay in its free allowance
- **Groups:** every meetup belongs to a group. A group can have a recurring schedule (each date editable on its own) and one-off dates

## Considerations beyond the core features

These are folded into the checklist below.

- **BGG API access needs registration.** BGG's XML API2 requires a registered app plus a bearer token, and BGG requires "Powered by BGG" attribution. Sign up early because approval can take a while.
- **Easiest import path:** BGG's own collection CSV export already includes `objectid`, so matching is free. Also support importing by BGG username, plus a generic CSV/text list of names that needs fuzzy matching and a review screen.
- **Inviting people who don't have an account yet.** An invite link or email invite. Without it, nobody can bootstrap a group.
- **Notifications:** emails for invites, RSVP reminders, the final game pick, and "you're bringing X". Resend's free tier covers this.
- **Host role and permissions:** who can edit, cancel, lock the vote, or reassign who brings what. Optional co-hosts.
- **Capacity:** plus-ones/guests now (Phase 8); max seats and a waitlist later (Phase 13).
- **Game length vs. meetup length:** a 4-hour game shouldn't be recommended for a 2-hour evening.
- **Big groups:** with 9 people, the recommendation should be "two tables", not one game. This is v2, but the data model should allow it.
- **Expansions:** treat them as attached to their base game, not as separate recommendations.
- **Close the loop:** log what was actually played after a meetup. That feeds "recently played" into future recommendations.
- **Supabase free tier pauses after a week without activity.** Fine while people use the app. Functions get no platform health checks, so if usage is sparse, add a weekly GitHub Actions ping of `/api/health`.
- **Privacy:** the address is shown only to group members, and users control who can see their collection (friends vs. public). Joining a group (invited, then confirmed) shares all of your game data except notes with that group's members under your name, whatever your collection visibility says. Notes stay private to you.
- **Time zones and calendar export** (.ics file / "add to calendar").
- **Mobile-first UI:** most RSVPs and votes will happen on phones.
- **Account deletion and data export:** basic hygiene.

---

## Checklist

### Phase 0 — Accounts & setup
- [x] Create GitHub repo (`bmewing/boardgamemeetups`)
- [x] Protect `main` (require the `backend` and `frontend` CI checks; no force pushes or deletions, admins included)
- [x] Register app with BGG XML API; store bearer token
- [x] Kinde: create business/app (React SPA type), set callback/logout URLs for localhost + prod, define an API audience for FastAPI
- [x] Supabase: create project; grab the **transaction pooler** connection string (port 6543; the direct connection is IPv6-only on the free tier)
- [x] DigitalOcean (personal account): confirm billing, decide on domain (or use `*.ondigitalocean.app` initially)
- [x] Resend account for transactional email; `bggroup.app` verified as the sending domain, and a sending-only key for it set on the app as `RESEND_API_KEY` (2026-11-04)

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

- [x] `moods` (seeded list; Phase 9 decided against guessing moods from BGG's categories and mechanics), e.g. *Light & quick, Party/social, Laughs, Chill, Brain-burner, Cutthroat, Thematic/story, Family-friendly*. Used both to tag games and to pick an RSVP mood. Meetup-only moods that describe the group's history (*Something new, Old favorite, No preference*) can't be tagged on a game
- [x] `user_games` (user, game, plus):
  - ownership: `owned` / `previously_owned` / `preordered` / none
  - `wishlist_priority` (1–5, blank = not wishlisted), `want_to_play`
  - `rating` (decimal 1–10, BGG's scale and labels)
  - `weight_vote` (1–5, BGG's Light … Heavy scale)
  - `playtime_feel` (shorter / just right / longer vs. the listed time)
  - `can_teach`, and `teach_minutes`, required when `can_teach` is set
  - `plays` (count; imported from BGG `numplays`, then added to by the Phase 10 play log, one per logged play)
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

### Phase 5 — Editing your game data ✅
- [x] "My games" moves from the header to the account menu; the header keeps shared things (Search now, later Groups and Meetups)
- [x] `PUT /api/me/games/{id}` takes `player_counts` and `moods`, each replacing the whole list (only taggable moods)
- [x] One editor (`GameAnswersEditor`), each change saving on its own and in order:
  - My games list rows: player counts, rating, weight, length, can teach + teach time, want to play, will bring (owned only), moods
  - Game page: all of those plus ownership, wishlist priority, plays and notes; any answer adds a game that isn't in your list
  - Search results: one-tap "I own it", "On my wishlist", "Want to play"; the rest via the game page
- [x] Player counts as a row of tappable counts (tap cycles best → recommended → not recommended → blank; the first tap is the "best at N" shortcut)
- [x] "Can teach" asks for teach time before it saves; entering a teach time ticks it, clearing it unticks it
- [x] Moods picked from the taggable `moods` list
- [x] BGG's values beside your own: rating and weight as hints in your boxes, the listed time in the length box, BGG's best counts as a dot on the player-count buttons (plus the "Best at N" badge)
- **Done when:** can set every field from both the collection and search, and BGG's values show beside your own (met 2026-11-03: search sets the status fields directly and links to the game page for the rest)

### Phase 6 — Friends & invites ✅
- [x] `friendships`: one row per pair, stored as (smaller user id, larger user id) so two crossing requests can't make two rows, plus the requester and status (pending / accepted)
- [x] Find friends by **exact email only** (any case), not display name, so nobody can list everyone on the app. No match offers an invite link instead (Phase 7 replaced this with username suggestions as you type)
- [x] Send, accept, decline, cancel, remove. Declining deletes the request quietly; the sender isn't told
- [x] `user_blocks` (blocker, blocked): hides you from their email search, drops their requests, and ends any friendship. Unblock from the Friends page
- [x] Invite links as stored rows (`invite_links`: random token, owner, expiry, turned-off time, use count), not signed tokens, so a link that gets passed around can be turned off. Phase 7 adds a group to the same table
- [x] Opening `/invite/:token` keeps the token in sessionStorage through Kinde sign-up or sign-in, then offers to become friends (`POST /api/invites/{token}/accept`)
- [x] Friends page (account menu, with a count of incoming requests): add by email, requests, friends, invite links, blocked
- [x] Person page: their collection and wishlist, read only, as their visibility allows: *private* = only you, *friends* = friends, *public* = anyone signed in. **Notes are never shown to anyone else**
- **Done when:** two test accounts can befriend each other via search and via invite link (met 2026-11-03, in production)

### Phase 7 — Groups, schedules, meetups & RSVP ✅
Every meetup belongs to a group, so meetups and RSVPs move here from Phase 8.

- [x] `groups` (name, description, owner, time zone, willing to split into tables, schedule and its default time/length/place) + `group_members` (role: owner / admin / member). Whoever creates a group owns it
- [x] Join only by accepting an invite. Owners and admins invite anyone by email (`group_invites`); an email nobody uses yet waits until someone signs up with it (the owner sends them the app's address themselves until Phase 11 emails). Someone who has blocked you is never shown your invite. Joining shares your games (not notes) with the members
- [x] Roles: the owner can do everything, including making members admins (and back), handing over ownership, and deleting the group. Admins can do everything else: edit the group and its schedule, add, edit or cancel dates, invite, and remove members (not other admins). Members see everything, RSVP and can leave. The owner can't leave without handing the group over; deleting your account hands it to the longest-serving admin, then member
- [x] Time zone: the owner's at creation (changeable when making the group), stored on the group. New accounts start in the browser's time zone instead of UTC. Dates are kept as the local date and time there, so a 7 pm meetup stays 7 pm across daylight saving
- [x] Schedules (optional): every N weeks on a weekday, the Nth (or last) weekday of each month, or day X of each month (months without that day are skipped). Built with `python-dateutil`'s rrule
- [x] The next 8 scheduled dates exist as `meetups` rows, topped up whenever the group page opens and when the schedule changes. Each row remembers the rule date it came from (`slot_date`). When the schedule changes, untouched future dates that still fit take the new time and place, ones that no longer fit go, and new ones are added; dates edited by hand, cancelled dates and past dates are never touched
- [x] One-off dates can be added any time, with or without a schedule
- [x] `meetups` (group, date, start time, length, place, notes, status: scheduled / cancelled; `slot_date`, `is_overridden`)
- [x] `meetup_rsvps` (meetup, member, yes / no / maybe), changeable any time for now
- [x] Games that fit a meetup: games owned and marked "will bring" by the members who said yes. With C confirmed, a group that plays one game together sees games that seat exactly C. A group willing to split also sees games that seat a table of 2 to C−2, so nobody is left alone (5 confirmed: tables of 2, 3 or 5, not 4)
- [x] Group library: every member's owned games with who owns them, expansions under their base game, and each member's answers by name. The combined numbers come with Phase 9
- [x] Display names are unique usernames (ignoring case; existing clashes become "Name 2"; first sign-in picks a free one). Adding a friend or inviting to a group takes a username picked from suggestions as you type, or any email. Suggestions match the start of a name or of a word in it, from 2 letters, up to 8, friends first. An email only matches when typed in full, and admins see invitees' names, never their emails. People who have blocked you, or whom you've blocked, never appear
- [x] Pages: Groups (yours, invites waiting for you), a group (dates, members, library, settings), a meetup (RSVP, who's coming, games that fit). Groups goes in the header
- **Done when:** a weekly group shows the next 8 dates; moving one date leaves the others alone; changing the rule to biweekly updates only untouched future dates; members RSVP and the games shown follow the confirmed count and the split setting (met 2026-11-04, in production)

### Phase 8 — Moods, plus-ones & calendar
Max seats and a waitlist are on the back burner (Phase 13): whoever runs a group only invites as many people as can be seated.

- [x] RSVP moods (`meetup_rsvp_moods`: meetup, user, mood, like `user_game_moods`), asked only with a yes or maybe. Any number from the whole `moods` list, including the moods that can't be tagged on a game (*Something new, Old favorite*, the co-op ones from BGG's mechanics); *No preference* rules out the others
- [x] Plus-ones: a guest count on each RSVP (yes or maybe only), up to the group's `plus_one_limit`, set by the owner and admins (0 by default, so guests are off until allowed). Lowering the limit trims existing RSVPs down to it. Guests aren't users, so they count toward the headcount but have no games or answers for Phase 9 to score
- [x] Headcount = members who said yes + their guests. The games that fit a meetup (Phase 7) follow the headcount, not just the yes count
- [x] Address only visible to members: already true (meetups and group details need membership; the invites waiting for you leave the location out). Add a test that keeps it so
- [x] One meetup to your calendar: an .ics download (fetched with the sign-in token, then saved, since a plain link can't carry it) and an "Add to Google Calendar" link
- [x] Calendar feed, self-hosted (no third party holds members' addresses): one feed per person covering all their groups, at `GET /api/calendar/{token}.ics`, which needs no sign-in
  - `calendar_feeds` (user, random token, created, turned-off time), stored rows like `invite_links`, so a leaked link can be turned off and replaced
  - Shows the dates the person might go to: unanswered, maybe and yes; a no drops the date. Upcoming dates plus the last 30 days. Cancelled dates stay in, marked `STATUS:CANCELLED`, so calendars remove or strike them
  - Each event's `UID` is the meetup id, with a `SEQUENCE` taken from `updated_at` so it goes up when the date changes; times in UTC from `starts_at`
  - Fetching the feed also tops up each group's next 8 dates, since otherwise that only happens when someone opens the group page
  - Calendar apps refresh slowly (Google can take hours, sometimes a day), so the meetup page stays the source of truth and Phase 11's "meetup changed" email covers urgent changes. Their polling also keeps Supabase from pausing
- **Done when:** 3 test users RSVP with moods and plus-ones, the headcount and the games that fit follow along, the plus-one limit is enforced, and a subscribed calendar shows each user's yes, maybe and unanswered dates but not their no's (not yet met by hand: deployed 2026-11-04 and covered by automated tests; one user has RSVPed with a guest and moods and added a date to their calendar in production)

### Phase 9 — Recommendations
Decided 2026-11-04: only yes answers count, game length is shown but never filters or sorts, and moods come only from what people say (nothing guessed from BGG).

- [x] Candidate pool = games owned by members who said yes and marked "will bring" (expansions folded into their base game, widening its player range); Phase 7 already filters it by headcount and the split setting. Length never filters
- [x] People in scope: members who said yes at a meetup, every member for the group's library. Maybes only count toward one thing: a game that would still fit if they (and their guests) came too gets a boost and a "Fits the maybes too" chip. Guests count toward the headcount only
- [x] Group roll-ups, computed per query over the people in scope; groups are small, so nothing is stored:
  - rating: average pulled toward BGG's rating when few have rated, `(sum + 2 × bgg_rating) / (n + 2)`; also show the lowest rating, and treat 3 or below as a soft veto
  - player count: group votes added onto BGG's poll counts, group votes weighted higher; read off at the headcount
  - weight: group average blended with BGG's weight the same way as rating (shown only)
  - length (shown only, to inform the vote): BGG's playing time adjusted by the net shorter/longer answers, plus teach time when someone new is coming (Phase 10 doesn't record play length, so this stays the estimate)
  - moods: who tagged the game with which mood (members' own tags only)
  - teaching: who's new to it (doesn't own it and never did, `plays` = 0, and hasn't rated it, since a rating means they've played), who can teach, and their teach time. Owners count as able to teach until they untick it (`can_teach` is null until answered; existing "no" answers were reset to unanswered)
  - owners willing to bring it; wishlist and want-to-play counts
- [x] Scoring (weighted, tunable in one config module):
  - player-count fit at the headcount (from the roll-up above)
  - fits the maybes too (boost)
  - attendees' rating (roll-up above; unrated = neutral), with a penalty for soft vetoes
  - wishlist and want-to-play hits among attendees (strong boost)
  - mood match: a boost only when attendees tagged the game with a mood someone picked for this date, shown as a chip. Otherwise RSVP moods are just shown to inform the vote. *Co-op* has no tags (it was meant to come from BGG), so it's display-only
  - teach cost: new players with nobody attending who can teach is a penalty (teach time is shown, never counted against the meetup length)
  - recently played penalty (from Phase 10 play logs)
- [x] "Why this game" explanation chips (e.g. "3 want to play · best at 5 · matches Brain-burner · Sam can teach (15 min)")
- [x] Meetup page: the games that fit, ranked, top 10 with "Show all"; attendees' RSVP moods shown above. Recompute on RSVP change
- [x] Group's Games tab: the combined numbers (group rating and lowest, best player counts, moods, who can teach)
- [x] Unit tests with fixture attendees/libraries for scoring edge cases
- **Done when:** recs change sensibly as people RSVP and switch moods, and each rec explains itself (not yet met by hand: deployed 2026-11-04 and covered by automated tests; checked in production with one person going)

### Phase 10 — Voting, bring assignment & play log
Decided 2026-11-04: owners and admins lock the pick and log what was played; RSVPs stay open after the lock; the play log records who played and who won, never scores or length.

- [x] `meetup_nominations` + `meetup_votes` (approval voting: vote for any number). Members who said yes nominate and vote. A game can be nominated from the recommendations or from anything someone going owns, including games they marked "won't bring"
- [x] Live tally, refreshed every few seconds while the page is open (the API is a function, so it can't push updates)
- [x] Owners and admins lock the pick(s), and more than one pick is allowed. Locking stops voting and new nominations; they can unlock it. RSVPs stay open both ways after the lock. If the headcount changes so a picked game no longer fits, the page says so
- [x] Bring assignment (`bring_assignments`): one owner going is tagged automatically; with several, the first to tap "I'll bring it" claims it, and owners and admins can reassign it. If whoever's bringing it drops out, the tag clears and the game is flagged for someone else to claim
- [x] Play log (`plays` + `play_players`), filled in by an owner or admin once the date has passed:
  - which games were actually played (one or more), and who actually came to the meetup
  - for each game, who played it and the result: who won (one or more people, for ties) for a competitive game, or won/lost for a co-op game. Co-op is preset from BGG's "Cooperative Game" mechanic, and whoever logs it can change it. No scores and no play length
  - each player's `user_games.plays` goes up by one (a row is added for a game they hadn't recorded)
- [x] Unlogged dates: a week after a date with a locked pick and no log, it counts as played as picked, by the members who said yes, with no result. This is filled in the next time the group is looked at (like topping up the schedule), since nothing runs on a timer until Phase 11. A date with no locked pick and no log records nothing
- [x] Recently played: a game played at either of the group's last two meetups moves down the recommendations, with a "Played last time" chip (`RECENTLY_PLAYED` in `app/recommend_config.py`)
- **Done when:** a full meetup cycle runs: RSVP → recs → vote → lock → owner tagged → play logged (and an unlogged date fills itself in after a week)

### Phase 11 — Notifications
Decided 2026-11-04: RSVP reminders go out the day before, to members who haven't answered or said maybe; the reminder endpoint is open, since it only sends what's due and never twice; one on/off switch per kind of email; a change to a group's repeating schedule sends one summary email.

- [x] Email wrapper over Resend's API (`RESEND_API_KEY`, sending access only, from `notifications@bggroup.app`, replies to `admin@bggroup.app`, which forwards to Mark). Each recipient gets their own email (batched up to 100 a call); sending happens after the change is saved and a failure is logged, never shown to whoever made the change. With no key (local dev, tests) emails are logged instead of sent
- [x] Plain text and simple HTML templates; dates in the group's local time, naming the group's time zone when it differs from the reader's; every email links to the page it's about
- [x] Triggers (never to whoever caused it):
  - **Friend request:** to the person asked, when a new request is made (not when it accepts theirs)
  - **Group invite:** to the email invited, when the invite is new. Someone not on the app yet gets it too, saying to sign up with that address. Someone who has blocked the inviter gets nothing
  - **RSVP reminder:** the day before (within 24 hours of the start), to members who haven't answered or said maybe, once per date
  - **Pick locked:** to members who said yes or maybe: the picked games and who's bringing each. Anyone tagged to bring one is told in the same email
  - **You're bringing X:** when an owner or admin hands a game to someone (claiming one yourself sends nothing)
  - **Date changed or cancelled:** a hand edit of an upcoming date's day, time or place, cancelling or restoring it, or removing a one-off date, to members who haven't said no. Notes and length don't count. A moved date gets its reminder again
  - **Schedule changed:** one summary email per change to the group's schedule, start time, place or time zone, listing the upcoming dates added, dropped or moved, to every member
- [x] Preferences: `users.email_opt_outs` (the kinds turned off; empty = all on), switches on the profile page. Every email to a user has an unsubscribe link for that kind (or all) that works without signing in, via a random `users.email_token`, plus `List-Unsubscribe` one-click headers. The unsubscribe page asks for a click, so mail scanners that open links don't unsubscribe anyone
- [x] Reminders: `meetups.reminder_sent_at`, claimed before sending (so two runs can't both send) and released if the send fails. `POST /api/notifications/run` sends whatever is due, after topping up every group's scheduled dates and filling in unlogged plays; `.github/workflows/scheduled-emails.yml` calls it every hour (Functions on App Platform can't be scheduled yet), which also keeps Supabase from pausing
- **Done when:** each kind of email arrives for real from production, and turning a kind off (on the profile page or from an email's link) stops it

### Phase 12 — Deploy to DigitalOcean
- [x] Run the API as a DigitalOcean function: Python 3.13, `web: raw` adapter, no connection pool, pooler-safe statements, BGG throttle shared through Postgres
- [x] `functions/` project (vendors `backend/app`, builds deps in DO's Python 3.13 container; bundle ~19 MB zipped of the 48 MB limit)
- [x] `.do/app.yaml` spec: static site + functions component, `/api` routed to the function
- [x] Migrations applied to Supabase (`uv run --env-file .env.production alembic upgrade head`; rerun before deploying new migrations, since Functions-only apps have no pre-deploy job)
- [x] Env vars/secrets in DO: DB URL (Supabase transaction pooler, `sslmode=require`), BGG token
- [x] Resend key (Phase 11)
- [x] First deploy: https://boardgamemeetups-i59h7.ondigitalocean.app (auto-deploys on push to `main`)
- [x] Kinde prod callback URLs
- [x] Own OAuth credentials for Google, Facebook and Discord in Kinde, so consent screens name this app rather than Kinde (Discord links to `/terms` and `/privacy`)
- [x] Kinde custom domain `auth.bggroup.app`, so sign-ins survive page reloads with the refresh token in a secure cookie rather than localStorage (localStorage stays for local dev, which signs in through `boardgamegroup.kinde.com`). Production's `VITE_KINDE_DOMAIN` and `KINDE_DOMAIN` (the token issuer) both point at it
- [x] App custom domain + TLS: `bggroup.app` (primary) and `boardgames.ewingsonline.com`
- [x] Auto-deploy from `main`
- [x] Staging database: a second Supabase project, `boardgamemeetups-staging` (us-east-1, Data API off). Settings in the gitignored `backend/.env.staging`; migrated to head 2026-11-04
- **Done when:** production URL works end-to-end with a real login (met 2026-11-03; the open items above can follow later)

### Phase 13 — Post-MVP / nice-to-haves
- [ ] Multi-table splitting for big groups (recommend 2 games that together seat everyone)
- [ ] Max seats and a waitlist (moved from Phase 8). Open questions: who sets the seats (an optional host per meetup, or the owner and admins); whether a party that doesn't fully fit waits as a whole or takes the seats left; whether someone later in line can take a free seat ahead of a bigger party. Order the line by when each person first said yes (`responded_at` changes on every edit, so it can't be used)
- [ ] PWA install + push notifications
- [ ] Ranked-choice voting option
- [ ] Group stats (most played, H-index, who brings what most)
- [ ] Reminder to pull from BGG when the last pull is old (still previewed and confirmed by the user, never silent)

---

## Verification

- Every phase has a **Done when** line. Don't tick a phase until that scenario passes manually on localhost and its tests pass in CI.
- Keep a seed script (`backend/scripts/seed.py`) that creates 4–5 test users with collections, ratings, wishlists, friendships, a recurring group, and a meetup, so the full flow can be clicked through quickly after any change.
- After Phase 12, rerun the Phase 10 end-to-end scenario against production.

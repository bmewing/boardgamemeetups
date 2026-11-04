import uuid
from typing import Any

from app.models import Game, Ownership, PlayerCountVote, PlaytimeFeel
from app.recommend import Answer, Person, Rollup, rollup, score

BEST, REC, NOT = PlayerCountVote.BEST, PlayerCountVote.RECOMMENDED, PlayerCountVote.NOT_RECOMMENDED
ANN, BEN, CAT, DEE = (Person(uuid.uuid4(), name) for name in ("Ann", "Ben", "Cat", "Dee"))
MOOD_NAMES = {"chill": "Chill", "brain": "Brain-burner", "no_preference": "No preference"}


def game(**fields: Any) -> Game:
    defaults: dict[str, Any] = {"id": 1, "name": "Test", "min_players": 2, "max_players": 5}
    return Game(**{**defaults, **fields})


def answers(*given: Answer) -> dict[uuid.UUID, Answer]:
    return {a.person.id: a for a in given}


def reasons_for(roll: Rollup, players: int = 3, **options: Any) -> list[str]:
    options = {"fits_maybes": False, "tonight_moods": [], "mood_names": MOOD_NAMES, **options}
    return [r.text for r in score(roll, players=players, **options)[1]]


def test_new_to_it_means_never_owned_unplayed_and_unrated() -> None:
    assert Answer(ANN).is_new
    assert Answer(ANN, ownership=Ownership.PREORDERED).is_new
    assert not Answer(ANN, ownership=Ownership.OWNED).is_new
    assert not Answer(ANN, ownership=Ownership.PREVIOUSLY_OWNED).is_new
    assert not Answer(ANN, plays=1).is_new
    assert not Answer(ANN, rating=7).is_new  # rating it means you've played it


def test_people_without_answers_are_new_to_it() -> None:
    roll = rollup(game(), [ANN, BEN], answers(Answer(ANN, ownership=Ownership.OWNED)))

    assert roll.new_to_it == [BEN]


def test_ratings_lean_on_bgg_until_a_few_have_rated() -> None:
    roll = rollup(
        game(bgg_rating=7.0), [ANN, BEN, CAT], answers(Answer(ANN, rating=9), Answer(BEN, rating=5))
    )

    assert roll.rating == 7.0  # (9 + 5 + 2 x 7) / (2 + 2)
    assert (roll.rated_by, roll.lowest_rating) == (2, 5)
    assert rollup(game(bgg_rating=7.0), [ANN], {}).rating is None  # nobody in scope rated it


def test_the_groups_player_count_votes_soon_outweigh_bggs() -> None:
    bgg = {"4": {"best": 900, "recommended": 90, "not_recommended": 10}}
    players = [ANN, BEN, CAT, DEE]

    bgg_only = rollup(game(player_count_votes=bgg), players, {}, players=4)
    disagree = rollup(
        game(player_count_votes=bgg),
        players,
        answers(*(Answer(p, player_counts={4: NOT}) for p in players)),
        players=4,
    )

    assert (bgg_only.fit_vote, bgg_only.best_at) == (BEST, [4])
    assert bgg_only.fit is not None and bgg_only.fit > 0.9
    assert (disagree.fit_vote, disagree.best_at) == (NOT, [])
    assert disagree.fit is not None and disagree.fit < 0.5


def test_counts_past_bggs_list_read_its_plus_entry() -> None:
    votes = {"4": {"best": 10, "recommended": 0, "not_recommended": 0}}
    votes["4+"] = {"best": 0, "recommended": 0, "not_recommended": 10}

    roll = rollup(game(player_count_votes=votes), [ANN], {}, players=6)

    assert roll.fit_vote == NOT


def test_length_follows_how_long_it_feels_and_teaching_is_extra() -> None:
    roll = rollup(
        game(playing_time=60),
        [ANN, BEN, CAT, DEE],
        answers(
            Answer(ANN, ownership=Ownership.OWNED, playtime_feel=PlaytimeFeel.LONGER),
            Answer(
                BEN, plays=2, playtime_feel=PlaytimeFeel.LONGER, can_teach=True, teach_minutes=20
            ),
            Answer(
                CAT,
                plays=1,
                playtime_feel=PlaytimeFeel.JUST_RIGHT,
                can_teach=True,
                teach_minutes=15,
            ),
        ),
    )

    assert roll.length_minutes == 70  # 60 x (1 + 0.25 x 2/3)
    assert roll.new_to_it == [DEE]
    assert roll.teach_minutes == 15  # the quickest teacher
    # Ann owns it and hasn't said she can't, so she counts too (with no teach time).
    assert [p.name for p in roll.teachers] == ["Ann", "Ben", "Cat"]
    everyone_knows_it = rollup(
        game(playing_time=60),
        [BEN],
        answers(Answer(BEN, plays=2, can_teach=True, teach_minutes=20)),
    )
    assert everyone_knows_it.teach_minutes is None


def test_reasons_explain_the_score() -> None:
    roll = rollup(
        game(player_count_votes={"3": {"best": 10, "recommended": 0, "not_recommended": 0}}),
        [ANN, BEN, CAT],
        answers(
            Answer(
                ANN,
                ownership=Ownership.OWNED,
                can_teach=True,
                teach_minutes=10,
                moods=frozenset({"chill"}),
            ),
            Answer(BEN, want_to_play=True),
            Answer(CAT, wishlist_priority=2, rating=3),
        ),
        players=3,
    )

    text = reasons_for(roll, fits_maybes=True, tonight_moods=["chill", "brain", "no_preference"])

    assert text == [
        "Ben wants to play",
        "On Cat's wishlist",
        "Best at 3",
        "Fits the maybes too",
        "Matches Chill",  # Brain-burner was picked, but nobody tagged the game with it
        "Ann can teach (10 min)",
        "Group rating 3.0",
        "Cat isn't keen (3)",
    ]


def test_names_turn_into_counts_past_two() -> None:
    three = answers(*(Answer(p, want_to_play=True, wishlist_priority=1) for p in (ANN, BEN, CAT)))
    two = answers(*(Answer(p, want_to_play=True, wishlist_priority=1) for p in (ANN, BEN)))

    assert reasons_for(rollup(game(), [ANN, BEN, CAT], three))[:2] == [
        "3 want to play",
        "On 3 wishlists",
    ]
    assert reasons_for(rollup(game(), [ANN, BEN], two))[:2] == [
        "Ann and Ben want to play",
        "On Ann's and Ben's wishlists",
    ]


def test_scoring_rewards_what_the_group_wants() -> None:
    def total(*given: Answer, **options: Any) -> float:
        # Ann owns it but has said she can't teach it.
        ann = Answer(ANN, ownership=Ownership.OWNED, can_teach=False)
        roll = rollup(game(), [ANN, BEN], answers(ann, *given))
        options = {"fits_maybes": False, "tonight_moods": [], "mood_names": MOOD_NAMES, **options}
        return score(roll, players=2, **options)[0]

    plain = total(Answer(BEN, plays=1))
    assert total(Answer(BEN, plays=1, want_to_play=True)) > plain
    assert total(Answer(BEN, plays=1), fits_maybes=True) > plain
    assert total(Answer(BEN, rating=9)) > plain
    assert total(Answer(BEN, rating=2)) < total(Answer(BEN, rating=5)) < plain
    # Ben is new to it and nobody coming can teach.
    assert total(Answer(BEN)) < plain
    assert "New to Ben, nobody to teach" in reasons_for(
        rollup(game(), [ANN, BEN], answers(Answer(ANN, ownership=Ownership.OWNED, can_teach=False)))
    )


def test_owners_teach_unless_they_say_otherwise() -> None:
    assert Answer(ANN, ownership=Ownership.OWNED).teaches
    assert not Answer(ANN, ownership=Ownership.OWNED, can_teach=False).teaches
    assert not Answer(ANN, ownership=Ownership.PREORDERED).teaches
    assert not Answer(ANN, ownership=Ownership.PREVIOUSLY_OWNED).teaches
    assert Answer(ANN, can_teach=True, teach_minutes=5).teaches

    owner = rollup(game(), [ANN, BEN], answers(Answer(ANN, ownership=Ownership.OWNED)))
    assert "Ann can teach" in reasons_for(owner)


def test_mood_matches_need_attendees_tags() -> None:
    tagged = rollup(game(), [ANN], answers(Answer(ANN, plays=1, moods=frozenset({"brain"}))))
    untagged = rollup(game(), [ANN], answers(Answer(ANN, plays=1)))
    options: dict[str, Any] = {"players": 2, "fits_maybes": False, "mood_names": MOOD_NAMES}

    matched, _ = score(tagged, tonight_moods=["brain"], **options)
    unmatched, reasons = score(untagged, tonight_moods=["brain"], **options)

    assert matched > unmatched
    assert not any("Matches" in r.text for r in reasons)

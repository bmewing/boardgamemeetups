"""The knobs for game recommendations, in one place so they're easy to tune.

A game's score is the sum of the parts below. Only the order matters, not the numbers
themselves, so each weight is "how much this counts next to the others".
"""

# How well the game plays at tonight's headcount, from 0 (not recommended) to 1 (best).
PLAYER_COUNT_FIT = 3.0
# It would still fit if the people who said maybe (and their guests) came too.
FITS_THE_MAYBES = 1.0
# The group's rating, from -1 (rated well below average) to +1 (well above).
RATING = 2.0
# Ratings at or below this count as "I'd rather not".
SOFT_VETO_AT = 3.0
SOFT_VETO = -3.0  # for each attendee who'd rather not
# For each attendee who wants to play it, or has it on their wishlist.
WANT_TO_PLAY = 1.5
WISHLIST = 1.5
# For each mood picked for tonight that attendees have tagged the game with.
MOOD_MATCH = 1.0
# Someone coming is new to it and nobody coming can teach it.
NOBODY_TO_TEACH = -2.0
# Phase 10: played at one of the group's last few meetups.
RECENTLY_PLAYED = 0.0

# Group ratings and weights lean on BGG's until a few people have answered:
# (sum of answers + PRIOR * BGG's value) / (answers + PRIOR).
PRIOR = 2
# The rating where the RATING part is 0, and how far from it counts as "well above/below".
RATING_MIDPOINT = 6.5
RATING_SPREAD = 1.5
# BGG's player-count poll counts as this many votes in all, shared out the way BGG voted,
# so a member's own vote soon outweighs thousands of strangers'.
BGG_PLAYER_COUNT_VOTES = 3.0
# Each net "feels shorter/longer" answer moves the length shown by up to this share.
LENGTH_FEEL = 0.25

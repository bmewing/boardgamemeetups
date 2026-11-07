"""The Discord bot: slash commands and buttons Discord sends us (app.discord.interactions),
and the meetup cards we post and keep up to date (app.discord.cards).

There's no always-on connection to Discord. Discord POSTs each command and click to
/api/discord/interactions, and the bot posts and edits messages through Discord's REST API,
so it all runs on the same short-lived function as the rest of the API.
"""

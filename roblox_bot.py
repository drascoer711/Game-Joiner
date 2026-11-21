"""Launcher for the Discord bot, including the Roblox join-game command."""

import aiohttp
import discord
from discord import app_commands

import main


@main.bot.tree.command(
    name="join-game",
    description="Get a link to join a Roblox player's current public game.",
)
@app_commands.describe(username="Roblox username of the player")
@app_commands.check(main.has_bot_access)
async def join_game(
    interaction: discord.Interaction,
    username: str,
):
    username = username.strip()
    await interaction.response.defer(thinking=True, ephemeral=True)

    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": True},
            ) as response:
                if response.status != 200:
                    await interaction.followup.send(
                        "❌ Roblox couldn't look up that username right now. Please try again later.",
                        ephemeral=True,
                    )
                    return
                user_data = await response.json()

            users = user_data.get("data", [])
            if not users:
                await interaction.followup.send(
                    f"❌ No Roblox user found with username `{username}`.",
                    ephemeral=True,
                )
                return

            user = users[0]
            user_id = user.get("id")
            resolved_name = user.get("name", username)
            if not user_id:
                await interaction.followup.send(
                    "❌ Roblox returned incomplete user information. Please try again later.",
                    ephemeral=True,
                )
                return

            async with session.post(
                "https://presence.roblox.com/v1/presence/users",
                json={"userIds": [user_id]},
            ) as response:
                if response.status != 200:
                    await interaction.followup.send(
                        "❌ Roblox presence information isn't available for that player right now.",
                        ephemeral=True,
                    )
                    return
                presence_data = await response.json()

        presences = presence_data.get("userPresences", [])
        presence = next(
            (item for item in presences if item.get("userId") == user_id),
            None,
        )
        if not presence or presence.get("userPresenceType") != 2:
            await interaction.followup.send(
                f"ℹ️ **{resolved_name}** doesn't appear to be in a Roblox game right now.",
                ephemeral=True,
            )
            return

        place_id = presence.get("rootPlaceId") or presence.get("placeId")
        game_id = presence.get("gameId")
        if not place_id or not game_id:
            await interaction.followup.send(
                f"ℹ️ **{resolved_name}** is in a game, but Roblox didn't provide a joinable public server link. They may be in a private or restricted server.",
                ephemeral=True,
            )
            return

        join_url = (
            f"https://www.roblox.com/games/start?"
            f"placeId={int(place_id)}&gameInstanceId={game_id}"
        )
        await interaction.followup.send(
            f"🎮 [Join **{resolved_name}** on Roblox]({join_url})\n"
            "The link only works if Roblox allows your account to join that server.",
            ephemeral=True,
        )

    except (aiohttp.ClientError, TimeoutError) as error:
        print(f"[ROBLOX] /join-game request failed: {type(error).__name__}: {error}")
        await interaction.followup.send(
            "❌ Couldn't contact Roblox right now. Please try again later.",
            ephemeral=True,
        )
    except (TypeError, ValueError, KeyError) as error:
        print(f"[ROBLOX] /join-game response was invalid: {type(error).__name__}: {error}")
        await interaction.followup.send(
            "❌ Roblox returned unexpected player or presence data.",
            ephemeral=True,
        )


if __name__ == "__main__":
    main.bot.run(main.TOKEN)

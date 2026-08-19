"""Discord slash-command bot for join links and opt-in account linking.

The bot only shares links that a player explicitly provides. It does not log
into games, bypass privacy settings, or automate game actions.

Commands:
    /follow player
    /join player
    /unfollow player
    /link-account
    /confirm-link code
    /my-accounts
    /unlink-account account_id

Required secret:
    DISCORD_BOT_TOKEN

Optional environment variable:
    DISCORD_GUILD_ID - sync commands to one server immediately while testing.
                       Without it, commands sync globally and can take a while
                       to appear in Discord.
"""

from __future__ import annotations

import argparse
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from urllib.parse import urlparse

import discord
from discord import app_commands


@dataclass(frozen=True)
class GameSession:
    """A game session that a player has explicitly shared."""

    player: str
    game: str
    session_id: str
    join_url: str
    updated_at: datetime


@dataclass(frozen=True)
class PendingAccountLink:
    owner_id: int
    owner_name: str
    code: str
    expires_at: datetime


class GameJoinSystem:
    """Tracks sessions and followers for the lifetime of the bot process."""

    def __init__(self) -> None:
        self._sessions: Dict[str, GameSession] = {}
        self._followers: Dict[str, set[str]] = {}
        self._linked_accounts: Dict[int, Dict[int, str]] = {}
        self._pending_links: Dict[str, PendingAccountLink] = {}

    @staticmethod
    def _clean_name(value: str, label: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{label} cannot be empty.")
        if len(value) > 80:
            raise ValueError(f"{label} is too long.")
        return value

    @staticmethod
    def _validate_join_url(join_url: str) -> str:
        parsed = urlparse(join_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("join_url must be a complete http(s) URL.")
        return join_url.strip()

    def share_session(
        self, player: str, game: str, session_id: str, join_url: str
    ) -> GameSession:
        """Publish a player's current session and notify their followers."""

        player = self._clean_name(player, "player")
        game = self._clean_name(game, "game")
        session_id = self._clean_name(session_id, "session_id")
        join_url = self._validate_join_url(join_url)

        session = GameSession(
            player=player,
            game=game,
            session_id=session_id,
            join_url=join_url,
            updated_at=datetime.now(timezone.utc),
        )
        self._sessions[player.casefold()] = session
        return session

    def follow(self, follower: str, player: str) -> None:
        """Start following a player's explicitly shared game sessions."""

        follower = self._clean_name(follower, "follower")
        player = self._clean_name(player, "player")
        if follower.casefold() == player.casefold():
            raise ValueError("A player cannot follow themselves.")

        self._followers.setdefault(player.casefold(), set()).add(follower)

    def unfollow(self, follower: str, player: str) -> None:
        """Stop notifications for a player's shared sessions."""

        player_key = self._clean_name(player, "player").casefold()
        followers = self._followers.get(player_key)
        if followers:
            followers.discard(self._clean_name(follower, "follower"))
            if not followers:
                self._followers.pop(player_key, None)

    def get_session(self, player: str) -> Optional[GameSession]:
        """Return the latest session shared by a player, if any."""

        return self._sessions.get(self._clean_name(player, "player").casefold())

    def get_join_message(self, player: str) -> str:
        """Build a Discord-friendly join message for a player's session."""

        player = self._clean_name(player, "player")
        session = self.get_session(player)
        if session is None:
            raise LookupError(f"{player} has not shared a game session.")

        return (
            f"{player} is playing {session.game}.\n"
            f"Join here: {session.join_url}\n"
            "Only join if you recognize the game and trust the link."
        )

    def is_following(self, follower: str, player: str) -> bool:
        return self._clean_name(follower, "follower") in self._followers.get(
            self._clean_name(player, "player").casefold(), set()
        )

    def create_account_link(self, owner_id: int, owner_name: str) -> str:
        """Create a short-lived code that another account must confirm."""

        self._remove_expired_links()
        code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()
        self._pending_links[code] = PendingAccountLink(
            owner_id=owner_id,
            owner_name=owner_name,
            code=code,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        return code

    def confirm_account_link(
        self, alt_id: int, alt_name: str, code: str
    ) -> tuple[str, str]:
        """Confirm a link from the second Discord account."""

        self._remove_expired_links()
        link = self._pending_links.pop(code.strip().upper(), None)
        if link is None:
            raise LookupError("That code is invalid or has expired.")
        if link.owner_id == alt_id:
            raise ValueError("The second account must be different from the first.")

        accounts = self._linked_accounts.setdefault(link.owner_id, {})
        accounts[link.owner_id] = link.owner_name
        accounts[alt_id] = alt_name
        return link.owner_name, alt_name

    def get_linked_accounts(self, owner_id: int) -> Dict[int, str]:
        return dict(self._linked_accounts.get(owner_id, {}))

    def unlink_account(self, owner_id: int, account_id: int) -> bool:
        accounts = self._linked_accounts.get(owner_id, {})
        if account_id not in accounts:
            return False
        accounts.pop(account_id)
        if len(accounts) < 2:
            self._linked_accounts.pop(owner_id, None)
        return True

    def _remove_expired_links(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            code
            for code, link in self._pending_links.items()
            if link.expires_at <= now
        ]
        for code in expired:
            self._pending_links.pop(code, None)


class JoinBot(discord.Client):
    """Discord client that registers and handles the slash commands."""

    def __init__(self) -> None:
        intents = discord.Intents.none()
        super().__init__(intents=intents)
        self.commands = app_commands.CommandTree(self)
        self.join_system = GameJoinSystem()

    async def setup_hook(self) -> None:
        guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.commands.copy_global_to(guild=guild)
            synced = await self.commands.sync(guild=guild)
            print(f"Synced {len(synced)} slash commands to guild {guild_id}.")
        else:
            synced = await self.commands.sync()
            print(
                f"Synced {len(synced)} global slash commands. "
                "Set DISCORD_GUILD_ID for instant testing in one server."
            )

    async def on_ready(self) -> None:
        if self.user:
            print(f"Bot online as {self.user} (ID: {self.user.id})")


bot = JoinBot()


@bot.commands.command(name="follow", description="Follow someone's shared game sessions")
@app_commands.describe(player="The player's Discord display name")
async def follow(interaction: discord.Interaction, player: str) -> None:
    try:
        bot.join_system.follow(interaction.user.display_name, player)
        session = bot.join_system.get_session(player)
        status = (
            f"Current join link: {session.join_url}"
            if session
            else f"{player} has not shared a session yet."
        )
        await interaction.response.send_message(
            f"You are now following {player}. {status}"
        )
    except ValueError as error:
        await interaction.response.send_message(str(error), ephemeral=True)


@bot.commands.command(name="join", description="Get someone's latest game join link")
@app_commands.describe(player="The player's Discord display name")
async def join(interaction: discord.Interaction, player: str) -> None:
    try:
        await interaction.response.send_message(bot.join_system.get_join_message(player))
    except (LookupError, ValueError) as error:
        await interaction.response.send_message(str(error), ephemeral=True)


@bot.commands.command(name="unfollow", description="Stop following someone's sessions")
@app_commands.describe(player="The player's Discord display name")
async def unfollow(interaction: discord.Interaction, player: str) -> None:
    try:
        bot.join_system.unfollow(interaction.user.display_name, player)
        await interaction.response.send_message(f"You unfollowed {player}.")
    except ValueError as error:
        await interaction.response.send_message(str(error), ephemeral=True)


@bot.commands.command(
    name="link-account",
    description="Create a code to link another Discord account you own",
)
async def link_account(interaction: discord.Interaction) -> None:
    code = bot.join_system.create_account_link(
        interaction.user.id, interaction.user.display_name
    )
    await interaction.response.send_message(
        "Run `/confirm-link` from the other Discord account and enter this code: "
        f"`{code}`\nThe code expires in 10 minutes.",
        ephemeral=True,
    )


@bot.commands.command(
    name="confirm-link",
    description="Confirm an account link using a one-time code",
)
@app_commands.describe(code="The one-time code generated by /link-account")
async def confirm_link(interaction: discord.Interaction, code: str) -> None:
    try:
        owner_name, alt_name = bot.join_system.confirm_account_link(
            interaction.user.id, interaction.user.display_name, code
        )
        await interaction.response.send_message(
            f"Verified link: {owner_name} and {alt_name} are now connected.",
            ephemeral=True,
        )
    except (LookupError, ValueError) as error:
        await interaction.response.send_message(str(error), ephemeral=True)


@bot.commands.command(
    name="my-accounts",
    description="Show the Discord accounts you have explicitly linked",
)
async def my_accounts(interaction: discord.Interaction) -> None:
    accounts = bot.join_system.get_linked_accounts(interaction.user.id)
    if not accounts:
        await interaction.response.send_message(
            "No verified accounts are linked to you.", ephemeral=True
        )
        return
    account_list = "\n".join(
        f"• {name} (`{account_id}`)" for account_id, name in accounts.items()
    )
    await interaction.response.send_message(
        f"Your verified accounts:\n{account_list}", ephemeral=True
    )


@bot.commands.command(
    name="unlink-account",
    description="Remove one of your verified linked accounts",
)
@app_commands.describe(account_id="The Discord ID shown by /my-accounts")
async def unlink_account(
    interaction: discord.Interaction, account_id: str
) -> None:
    try:
        target_id = int(account_id.strip())
    except ValueError:
        await interaction.response.send_message(
            "account_id must be a Discord user ID.", ephemeral=True
        )
        return
    if bot.join_system.unlink_account(interaction.user.id, target_id):
        await interaction.response.send_message(
            "That account link was removed.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "That account is not linked to you.", ephemeral=True
        )


def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Game follow-and-join system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    share = subparsers.add_parser("share", help="share a current game session")
    share.add_argument("player")
    share.add_argument("game")
    share.add_argument("session_id")
    share.add_argument("join_url")

    follow = subparsers.add_parser("follow", help="follow a player's sessions")
    follow.add_argument("follower")
    follow.add_argument("player")

    send = subparsers.add_parser("send", help="send a join link manually")
    send.add_argument("recipient")
    send.add_argument("player")
    return parser


def main() -> None:
    parser = _build_cli()
    args = parser.parse_args()
    system = GameJoinSystem()

    try:
        if args.command == "share":
            session = system.share_session(args.player, args.game, args.session_id, args.join_url)
            print(f"Shared {session.game} session for {session.player}.")
        elif args.command == "follow":
            system.follow(args.follower, args.player)
        elif args.command == "send":
            print(system.get_join_message(args.player))
    except (LookupError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    if os.getenv("DISCORD_BOT_TOKEN"):
        bot.run(os.environ["DISCORD_BOT_TOKEN"])
    else:
        main()
"""Generic game follow-and-join link system.

This module does not log into games, bypass privacy settings, or automate
game actions. Each game should provide its own official presence/invite API.
The system stores the latest game session a player has shared, creates a
join link, and sends that link through a pluggable message sender.

Run:
    python main.py

Use the classes directly to connect this to an official game API or chat
service. See the example at the bottom of the file.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Optional
from urllib.parse import quote, urlparse


@dataclass(frozen=True)
class GameSession:
    """A game session that a player has explicitly shared."""

    player: str
    game: str
    session_id: str
    join_url: str
    updated_at: datetime


MessageSender = Callable[[str, str], None]


class GameJoinSystem:
    """Tracks shared sessions and sends official join links."""

    def __init__(self, sender: Optional[MessageSender] = None) -> None:
        self._sessions: Dict[str, GameSession] = {}
        self._followers: Dict[str, set[str]] = {}
        self._sender = sender or self._console_sender

    @staticmethod
    def _console_sender(recipient: str, message: str) -> None:
        print(f"\nMessage to {recipient}:\n{message}\n")

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

        for follower in self._followers.get(player.casefold(), set()):
            self.send_join_link(follower, player)
        return session

    def follow(self, follower: str, player: str) -> None:
        """Start following a player's explicitly shared game sessions."""

        follower = self._clean_name(follower, "follower")
        player = self._clean_name(player, "player")
        if follower.casefold() == player.casefold():
            raise ValueError("A player cannot follow themselves.")

        self._followers.setdefault(player.casefold(), set()).add(follower)
        session = self._sessions.get(player.casefold())
        if session:
            self.send_join_link(follower, player)
        else:
            self._sender(
                follower,
                f"{player} is not currently sharing a game session.",
            )

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

    def send_join_link(self, recipient: str, player: str) -> None:
        """Send the latest official join URL for a player."""

        recipient = self._clean_name(recipient, "recipient")
        player = self._clean_name(player, "player")
        session = self.get_session(player)
        if session is None:
            raise LookupError(f"{player} has not shared a game session.")

        message = (
            f"{player} is playing {session.game}.\n"
            f"Join here: {session.join_url}\n"
            "Only join if you recognize the game and trust the link."
        )
        self._sender(recipient, message)


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
            session = system.share_session(
                args.player, args.game, args.session_id, args.join_url
            )
            print(f"Shared {session.game} session for {session.player}.")
        elif args.command == "follow":
            system.follow(args.follower, args.player)
        elif args.command == "send":
            system.send_join_link(args.recipient, args.player)
    except (LookupError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
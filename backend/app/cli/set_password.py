"""Set / reset a user's password (the seed never changes an existing admin's password).

    docker compose exec backend python -m app.cli.set_password admin            # prompts twice
    docker compose exec -e NEW_PASSWORD backend python -m app.cli.set_password admin

The password is never accepted as a command-line argument (it would end up in shell history / ps)
and is never logged. All refresh tokens of the user are revoked.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from app.core.security import hash_password
from app.db.session import dispose_engine, get_session_factory
from app.repositories.user_repository import RefreshTokenRepository, UserRepository

MIN_LENGTH = 8


def _read_password() -> str:
    if env := os.environ.get("NEW_PASSWORD"):
        return env
    if not sys.stdin.isatty():
        raise SystemExit("no TTY: pass the password via the NEW_PASSWORD environment variable")
    first = getpass.getpass("New password: ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("passwords do not match")
    return first


async def set_password(username: str, password: str, activate: bool) -> None:
    async with get_session_factory()() as session:
        users = UserRepository(session)
        user = await users.get_by_username(username)
        if user is None:
            raise SystemExit(f"user '{username}' not found")
        user.hashed_password = hash_password(password)
        if activate:
            user.is_active = True
        await RefreshTokenRepository(session).revoke_all_for_user(user.id)
        await session.commit()
    await dispose_engine()
    print(f"password updated for '{username}'; existing sessions revoked")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("username")
    parser.add_argument("--activate", action="store_true", help="also re-enable a disabled account")
    args = parser.parse_args()
    password = _read_password()
    if len(password) < MIN_LENGTH:
        raise SystemExit(f"password must be at least {MIN_LENGTH} characters")
    asyncio.run(set_password(args.username, password, args.activate))


if __name__ == "__main__":
    main()

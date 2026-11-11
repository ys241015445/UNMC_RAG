"""Encrypt existing participant emails and transcripts in place.

Run once after deploying the encrypted columns:

    python scripts/encrypt_participant_fields.py

By default the legacy plaintext columns are cleared after the encrypted copies
are written. Pass --keep-plaintext to leave them in place.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from app.config import get_database_settings
from app.db import close_pool, create_pool
from app.privacy.crypto import get_field_cipher
from app.privacy.schema import ensure_privacy_columns


async def backfill(*, keep_plaintext: bool) -> None:
    db_settings = get_database_settings()
    if not db_settings.enabled:
        raise SystemExit("DATABASE_URL is not configured; nothing to backfill")

    cipher = get_field_cipher()
    if not cipher.enabled:
        raise SystemExit("UNMC_RAG_DATA_ENCRYPTION_KEY must be set before backfilling")

    pool = await create_pool(db_settings.database_url)
    try:
        await ensure_privacy_columns(pool)
        async with pool.acquire() as connection:
            conversations = await connection.fetch(
                """
                select id, email, title, messages
                from rag.chat_conversations
                where email_hash is null or messages_enc is null
                """
            )
            for row in conversations:
                email = row["email"] or ""
                messages = row["messages"]
                text = messages if isinstance(messages, str) else json.dumps(messages, ensure_ascii=False)
                await connection.execute(
                    """
                    update rag.chat_conversations
                    set email_enc = $2,
                        email_hash = $3,
                        title_enc = $4,
                        messages_enc = $5,
                        email = case when $6 then email else '' end,
                        title = case when $6 then title else '' end,
                        messages = case when $6 then messages else '[]'::jsonb end
                    where id = $1
                    """,
                    row["id"],
                    cipher.encrypt(email),
                    cipher.email_index(email),
                    cipher.encrypt(row["title"] or ""),
                    cipher.encrypt(text),
                    keep_plaintext,
                )

            sessions = await connection.fetch(
                """
                select id, school_email
                from rag.chat_sessions
                where school_email_hash is null
                """
            )
            for row in sessions:
                email = row["school_email"] or ""
                await connection.execute(
                    """
                    update rag.chat_sessions
                    set school_email_enc = $2,
                        school_email_hash = $3,
                        school_email = case when $4 then school_email else '' end
                    where id = $1
                    """,
                    row["id"],
                    cipher.encrypt(email),
                    cipher.email_index(email),
                    keep_plaintext,
                )

            messages = await connection.fetch(
                """
                select id, school_email, content
                from rag.chat_messages
                where school_email_hash is null or content_enc is null
                """
            )
            for row in messages:
                email = row["school_email"] or ""
                await connection.execute(
                    """
                    update rag.chat_messages
                    set school_email_enc = $2,
                        school_email_hash = $3,
                        content_enc = $4,
                        school_email = case when $5 then school_email else '' end,
                        content = case when $5 then content else '' end
                    where id = $1
                    """,
                    row["id"],
                    cipher.encrypt(email),
                    cipher.email_index(email),
                    cipher.encrypt(row["content"] or ""),
                    keep_plaintext,
                )
    finally:
        await close_pool(pool)

    print(
        "Backfilled "
        f"{len(conversations)} conversations, "
        f"{len(sessions)} sessions, "
        f"{len(messages)} messages"
        + (" (plaintext kept)" if keep_plaintext else " (plaintext cleared)")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-plaintext",
        action="store_true",
        help="Leave the legacy plaintext columns populated",
    )
    args = parser.parse_args()
    asyncio.run(backfill(keep_plaintext=args.keep_plaintext))


if __name__ == "__main__":
    main()

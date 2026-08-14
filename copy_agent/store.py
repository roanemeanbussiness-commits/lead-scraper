"""SQLite persistence for conversations and learned knowledge."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class ChatStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialize()

    # -- conversations ----------------------------------------------------

    def create_conversation(self, title: str = "") -> str:
        conversation_id = uuid.uuid4().hex[:16]
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO conversations (id, title) VALUES (?, ?)",
                (conversation_id, title.strip()[:80]),
            )
        return conversation_id

    def conversation_exists(self, conversation_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return row is not None

    def set_title_if_empty(self, conversation_id: str, title: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE conversations SET title = ? WHERE id = ? AND title = ''",
                (title.strip()[:80], conversation_id),
            )

    def list_conversations(self, limit: int = 60) -> list[dict[str, str]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.title, c.created_at,
                       COALESCE(MAX(m.created_at), c.created_at) AS updated_at
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "title": row[1] or "New chat",
                "created_at": row[2],
                "updated_at": row[3],
            }
            for row in rows
        ]

    def delete_conversation(self, conversation_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )
            connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )

    # -- messages ---------------------------------------------------------

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, content),
            )

    def messages(self, conversation_id: str, limit: int = 200) -> list[dict[str, str]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT role, content, created_at FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        return [
            {"role": row[0], "content": row[1], "created_at": row[2]}
            for row in reversed(rows)
        ]

    # -- learnings (self-updating memory) ---------------------------------

    def add_learning(
        self, source_type: str, source_ref: str, title: str, content: str
    ) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO learnings (source_type, source_ref, title, content)
                VALUES (?, ?, ?, ?)
                """,
                (source_type, source_ref.strip()[:500], title.strip()[:200], content),
            )
            return int(cursor.lastrowid or 0)

    def list_learnings(self, limit: int = 100) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, source_type, source_ref, title, content, created_at
                FROM learnings ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "source_type": row[1],
                "source_ref": row[2],
                "title": row[3],
                "content": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]

    def delete_learning(self, learning_id: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM learnings WHERE id = ?", (learning_id,)
            )
            return cursor.rowcount > 0

    def learnings_digest(self, max_chars: int = 8_000) -> str:
        """Newest-first digest of stored learnings for the system prompt."""
        chunks: list[str] = []
        used = 0
        for item in self.list_learnings(limit=50):
            block = f"### {item['title']} ({item['source_type']})\n{item['content']}\n"
            if used + len(block) > max_chars:
                break
            chunks.append(block)
            used += len(block)
        return "\n".join(chunks)

    # -- infrastructure ---------------------------------------------------

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, id);
                CREATE TABLE IF NOT EXISTS learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

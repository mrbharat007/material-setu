from .database import get_connection

_COLUMNS = "id, email, name, password_hash, role, cpse, created_at"
_PUBLIC = "id, email, name, role, cpse, created_at"


def create_user(
    email: str,
    name: str,
    password_hash: str,
    role: str = "steward",
    cpse: str | None = None,
) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO users (email, name, password_hash, role, cpse)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING {_PUBLIC}
                """,
                (email.lower().strip(), name.strip(), password_hash, role, cpse),
            )
            return dict(cur.fetchone())


def get_user_by_email(email: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUMNS} FROM users WHERE email = %s",
                (email.lower().strip(),),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUMNS} FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def count_users() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM users")
            return cur.fetchone()["n"]


def list_users() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_PUBLIC} FROM users ORDER BY id")
            return [dict(row) for row in cur.fetchall()]


def set_role(user_id: int, role: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET role = %s WHERE id = %s RETURNING {_PUBLIC}",
                (role, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def count_admins() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM users WHERE role = 'admin'")
            return cur.fetchone()["n"]

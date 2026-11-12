"""Search a bounded set of member profiles from the supplied Datamart member-profile query."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd

from dashboard.loadings import MANILA


QUERY_PATH = Path(__file__).resolve().parent.parent / "queries" / "datamart" / "memberprofile.sql"
SAMPLE_SIZES = (100, 500, 1000)


class MemberProfileDataError(Exception):
    pass


def load_member_profile(row_limit: int = 100, *, universal_player_id: str = "",
                        first_name: str = "", last_name: str = "") -> tuple[pd.DataFrame, datetime]:
    filters = [
        ("UniversalPlayerID = ?", universal_player_id.strip()),
        ("LOWER(FirstName) = LOWER(?)", first_name.strip()),
        ("LOWER(LastName) = LOWER(?)", last_name.strip()),
    ]
    supplied = [(clause, value) for clause, value in filters if value]
    if not supplied:
        raise MemberProfileDataError("Enter at least one of UniversalPlayerID, FirstName, or LastName.")
    if row_limit not in SAMPLE_SIZES:
        raise MemberProfileDataError("Choose a result limit of 100, 500, or 1,000 rows.")
    try:
        query = QUERY_PATH.read_text(encoding="utf-8-sig").strip().removesuffix(";").rstrip()
    except (OSError, UnicodeError):
        raise MemberProfileDataError(
            "The member profile query file is missing or unreadable. Restart the local launcher."
        ) from None
    if not query:
        raise MemberProfileDataError("The member profile query file is empty.")

    # Limit results in Datamart rather than downloading the entire member table.
    where = " AND ".join(clause for clause, _ in supplied)
    parameters = tuple(value for _, value in supplied)
    sample_query = f"SELECT * FROM (\n{query}\n) member_profile_sample\nWHERE {where}\nLIMIT {row_limit}"
    try:
        from okada import SQL

        loader = SQL("Datamart").get_loader()
        with closing(loader._get_conn(timeout=10)) as connection:
            connection.timeout = 60
            with closing(connection.cursor()) as cursor:
                cursor.execute(sample_query, parameters)
                columns = [column[0] for column in cursor.description]
                data = pd.DataFrame.from_records([tuple(row) for row in cursor.fetchall()], columns=columns)
    except Exception:
        raise MemberProfileDataError(
            "Unable to load member profiles from Datamart. Open Connections Checker and run the Datamart checks. "
            "If they pass, check read access to the member profile table and the query."
        ) from None
    return data, datetime.now(MANILA)

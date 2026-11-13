"""CSV reader and validator for email records."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError as PydanticValidationError

from inbox_helper.core.exceptions import IngestionError
from inbox_helper.domain.models.email import Email


class EmailCsvReader:
    """Read email CSV files using the Day 1 data contract."""

    REQUIRED_COLUMNS = frozenset({"sender", "subject", "body"})
    OPTIONAL_COLUMNS = frozenset({"id", "received_at"})

    def read(self, path: str | Path) -> list[Email]:
        """Load and validate every row; no rows are returned on any error."""
        try:
            with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
                return self._parse(file)
        except (OSError, UnicodeError, csv.Error) as error:
            raise IngestionError(f"Could not read email CSV: {error}") from error

    def read_content(self, content: bytes) -> list[Email]:
        """Decode and validate uploaded CSV bytes using the same parser."""
        try:
            text = content.decode("utf-8-sig")
            return self._parse(StringIO(text, newline=""))
        except (UnicodeError, csv.Error) as error:
            raise IngestionError(f"Could not read email CSV: {error}") from error

    def _parse(self, file: TextIO) -> list[Email]:
        reader = csv.DictReader(file)
        headers = reader.fieldnames
        if not headers:
            raise IngestionError("CSV is empty or has no header row.")
        if len(headers) != len(set(headers)):
            raise IngestionError("CSV contains duplicate column names.")

        missing = self.REQUIRED_COLUMNS - set(headers)
        if missing:
            raise IngestionError(
                f"CSV is missing required columns: {', '.join(sorted(missing))}."
            )

        emails: list[Email] = []
        for row in reader:
            line_number = reader.line_num
            if None in row:
                raise IngestionError(
                    f"CSV record ending at line {line_number} has too many columns."
                )
            values = {
                key: value
                for key, value in row.items()
                if key in self.REQUIRED_COLUMNS | self.OPTIONAL_COLUMNS
                and value is not None
            }
            for optional in self.OPTIONAL_COLUMNS:
                if not values.get(optional):
                    values.pop(optional, None)
            try:
                emails.append(Email.model_validate(values))
            except PydanticValidationError as error:
                details = "; ".join(
                    f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                    for item in error.errors()
                )
                raise IngestionError(
                    f"Invalid email record ending at CSV line {line_number}: {details}."
                ) from error
        return emails

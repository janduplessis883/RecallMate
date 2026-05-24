from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Iterable

import pandas as pd
from dateutil import parser


CANONICAL_COLUMNS = [
    "NHS number",
    "Date of birth",
    "Preferred telephone number",
    "First name",
    "Email",
]

REQUIRED_COLUMNS = [
    "NHS number",
    "Date of birth",
    "Preferred telephone number",
    "First name",
]

EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
EMAIL_SEARCH_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationResult:
    cleaned: pd.DataFrame
    rejected: pd.DataFrame
    summary: dict[str, int]


def read_csv(uploaded_file: BytesIO | str) -> pd.DataFrame:
    return pd.read_csv(
        uploaded_file,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
        skip_blank_lines=False,
    )


def drop_empty_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    mask = df.apply(lambda row: any(str(value).strip() for value in row), axis=1)
    return df.loc[mask].copy(), int((~mask).sum())


def guess_column(columns: Iterable[str], keywords: Iterable[str]) -> str | None:
    normalized = {column: _normalize_heading(column) for column in columns}
    for keyword in keywords:
        needle = _normalize_heading(keyword)
        for column, heading in normalized.items():
            if needle == heading:
                return column
    for keyword in keywords:
        parts = _normalize_heading(keyword).split()
        for column, heading in normalized.items():
            if all(part in heading for part in parts):
                return column
    return None


def default_column_mapping(columns: Iterable[str]) -> dict[str, str | None]:
    return {
        "NHS number": guess_column(columns, ["NHS number", "NHS", "National Health Service number"]),
        "Date of birth": guess_column(columns, ["Date of birth", "DOB", "Birth date"]),
        "Preferred telephone number": guess_column(
            columns,
            ["Preferred telephone number", "Preferred telephone", "Telephone number", "Mobile", "Phone"],
        ),
        "First name": guess_column(columns, ["First name", "Forename", "Given name"]),
        "Email": guess_column(columns, ["Email", "Email address", "EmailAddress", "E-mail", "E-mail address"]),
    }


def standardize_columns(df: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    standardized = pd.DataFrame()
    for target in CANONICAL_COLUMNS:
        source = mapping.get(target)
        if source and source in df.columns:
            standardized[target] = df[source].fillna("").astype(str)
        else:
            standardized[target] = ""
    return standardized


def validate_recall_csv(df: pd.DataFrame) -> ValidationResult:
    df, removed_empty_rows = drop_empty_rows(df)
    accepted_rows: list[dict[str, str]] = []
    rejected_rows: list[dict[str, str]] = []
    invalid_email_count = 0

    for original_index, row in df.iterrows():
        reasons: list[str] = []

        nhs_number = normalize_nhs_number(row.get("NHS number", ""))
        if not nhs_number:
            reasons.append("Missing or invalid NHS number")

        date_of_birth = normalize_date_of_birth(row.get("Date of birth", ""))
        if not date_of_birth:
            reasons.append("Missing or invalid date of birth")

        first_name = normalize_first_name(row.get("First name", ""))
        if not first_name:
            reasons.append("Missing first name")

        phone_number, phone_reason = normalize_mobile_number(row.get("Preferred telephone number", ""))
        if not phone_number:
            reasons.append(phone_reason or "Missing or invalid mobile telephone number")

        email, email_was_invalid = normalize_email(row.get("Email", ""))
        if email_was_invalid:
            invalid_email_count += 1

        cleaned_row = {
            "NHS number": nhs_number,
            "Date of birth": date_of_birth,
            "Preferred telephone number": phone_number or "",
            "First name": first_name,
            "Email": email,
        }

        if reasons:
            rejected_rows.append(
                {
                    "Source row": str(original_index + 2),
                    **{column: str(row.get(column, "")) for column in CANONICAL_COLUMNS},
                    "Reason": "; ".join(reasons),
                }
            )
        else:
            accepted_rows.append(cleaned_row)

    cleaned = pd.DataFrame(accepted_rows, columns=CANONICAL_COLUMNS)
    rejected = pd.DataFrame(
        rejected_rows,
        columns=["Source row", *CANONICAL_COLUMNS, "Reason"],
    )
    summary = {
        "input_rows_after_empty_removed": len(df),
        "empty_rows_removed": removed_empty_rows,
        "valid_rows": len(cleaned),
        "rejected_rows": len(rejected),
        "invalid_emails_cleared": invalid_email_count,
    }
    return ValidationResult(cleaned=cleaned, rejected=rejected, summary=summary)


def normalize_nhs_number(value: object) -> str:
    text = str(value).strip()
    if not text:
        return ""
    text = re.sub(r"\.0+$", "", text)
    digits = re.sub(r"\D", "", text)
    return digits if len(digits) == 10 else ""


def normalize_date_of_birth(value: object) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        parsed = parser.parse(text, dayfirst=False, fuzzy=False).date()
    except (ValueError, OverflowError, TypeError):
        try:
            parsed = parser.parse(text, dayfirst=True, fuzzy=False).date()
        except (ValueError, OverflowError, TypeError):
            return ""

    today = date.today()
    while parsed > today:
        parsed = parsed.replace(year=parsed.year - 100)
    return parsed.strftime("%d/%m/%Y")


def normalize_first_name(value: object) -> str:
    return " ".join(str(value).strip().split())


def normalize_mobile_number(value: object) -> tuple[str | None, str | None]:
    original = str(value).strip()
    if not original:
        return None, "Missing mobile telephone number"

    cleaned = original.replace("O", "0").replace("o", "0")

    mobile_patterns = [
        re.compile(r"(?<!\d)\+?44[\s().-]*7(?:[\s().-]*\d){9}(?!\d)"),
        re.compile(r"(?<!\d)0044[\s().-]*7(?:[\s().-]*\d){9}(?!\d)"),
        re.compile(r"(?<!\d)07(?:[\s().-]*\d){9}(?!\d)"),
        re.compile(r"(?<!\d)7(?:[\s().-]*\d){9}(?!\d)"),
    ]

    for pattern in mobile_patterns:
        match = pattern.search(cleaned)
        if not match:
            continue
        digits = re.sub(r"\D", "", match.group(0))
        if digits.startswith("00447"):
            return "0" + digits[4:14], None
        if digits.startswith("447"):
            return "0" + digits[2:12], None
        if digits.startswith("7"):
            return "0" + digits[:10], None
        return digits[:11], None

    all_digits = re.sub(r"\D", "", cleaned)
    if all_digits.startswith("020"):
        return None, "Landline telephone number removed"
    return None, "Missing or invalid mobile telephone number"


def normalize_email(value: object) -> tuple[str, bool]:
    text = str(value).strip()
    if not text:
        return "", False

    without_notes = re.sub(r"\s*\([^)]*\)\s*", " ", text).strip()
    match = EMAIL_SEARCH_PATTERN.search(without_notes)
    if not match:
        return "", True

    email = match.group(0).lower()
    return (email, False) if EMAIL_PATTERN.fullmatch(email) else ("", True)


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def split_dataframe_by_batch_size(df: pd.DataFrame, batch_size: int) -> list[pd.DataFrame]:
    if batch_size < 1:
        raise ValueError("Batch size must be at least 1")
    return [df.iloc[start : start + batch_size].copy() for start in range(0, len(df), batch_size)]


def split_dataframe_by_batch_count(df: pd.DataFrame, batch_count: int) -> list[pd.DataFrame]:
    if batch_count < 1:
        raise ValueError("Number of batches must be at least 1")
    if df.empty:
        return []

    base_size, extra_rows = divmod(len(df), batch_count)
    batches: list[pd.DataFrame] = []
    start = 0
    for batch_index in range(batch_count):
        current_size = base_size + (1 if batch_index < extra_rows else 0)
        if current_size == 0:
            break
        batches.append(df.iloc[start : start + current_size].copy())
        start += current_size
    return batches


def batch_summary(batches: list[pd.DataFrame], filename_prefix: str = "recallmate_batch") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Batch": index,
                "Rows": len(batch),
                "Filename": batch_filename(index, filename_prefix),
            }
            for index, batch in enumerate(batches, start=1)
        ]
    )


def batches_to_zip_bytes(batches: list[pd.DataFrame], filename_prefix: str = "recallmate_batch") -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for index, batch in enumerate(batches, start=1):
            zip_file.writestr(batch_filename(index, filename_prefix), dataframe_to_csv_bytes(batch))
    return buffer.getvalue()


def batch_filename(batch_number: int, filename_prefix: str = "recallmate_batch") -> str:
    return f"{sanitize_filename_prefix(filename_prefix)}_{batch_number:03d}.csv"


def sanitize_filename_prefix(filename_prefix: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename_prefix.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "recallmate_batch"


def _normalize_heading(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()

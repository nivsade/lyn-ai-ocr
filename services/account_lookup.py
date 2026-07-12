import os
import re
import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_PATH = os.path.join(BASE_DIR, "accounts.xlsx")


def clean_value(value):
    if pd.isna(value):
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    value = str(value).strip()

    if re.fullmatch(r"\d+\.0", value):
        value = value[:-2]

    return value


def clean_bank_code(value):
    value = clean_value(value)

    if value.startswith("9000"):
        value = value[4:]

    return value


def normalize_text(value):
    value = clean_value(value)

    value = value.replace('"', "")
    value = value.replace("'", "")
    value = value.replace("בע״מ", "")
    value = value.replace('בע"מ', "")
    value = value.replace("בעמ", "")

    value = re.sub(r"[^א-תa-zA-Z0-9]", "", value)

    return value.lower()


def build_account_number(row):
    bank = clean_bank_code(row.get("קוד בנק", ""))
    branch = clean_value(row.get("קוד סניף", ""))
    account = clean_value(row.get("מספר חשבון", ""))

    if not bank or not branch or not account:
        return "לא זוהה"

    return f"{bank}-{branch}-{account}"


def load_accounts():
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(
            f"קובץ accounts.xlsx לא נמצא בנתיב: {EXCEL_PATH}"
        )

    accounts_df = pd.read_excel(
        EXCEL_PATH,
        dtype=str,
    )

    required_columns = [
        "מספר ח.פ",
        "שם קופה / קרן",
        "מספר קופה / קרן",
        "קוד בנק",
        "קוד סניף",
        "מספר חשבון",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in accounts_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "חסרות עמודות בקובץ accounts.xlsx: "
            + ", ".join(missing_columns)
        )

    accounts_df["חפ_נקי"] = accounts_df[
        "מספר ח.פ"
    ].apply(clean_value)

    accounts_df["מספר_קופה_נקי"] = accounts_df[
        "מספר קופה / קרן"
    ].apply(clean_value)

    accounts_df["שם_קופה_נקי"] = accounts_df[
        "שם קופה / קרן"
    ].apply(normalize_text)

    accounts_df["חשבון_מלא"] = accounts_df.apply(
        build_account_number,
        axis=1,
    )

    return accounts_df


df = load_accounts()


def find_account_by_row(row):
    hp = clean_value(
        row.get("חפ_גוף", row.get("מספר ח.פ", ""))
    )

    fund_number = clean_value(
        row.get(
            "מספר קופה בקובץ",
            row.get("מספר קופה / קרן", ""),
        )
    )

    original_name = clean_value(
        row.get(
            "שם_הקופה",
            row.get(
                "fund_name",
                row.get("שם קופה", ""),
            ),
        )
    )

    matches = pd.DataFrame()

    # 1. התאמה מלאה: ח.פ + מספר קופה
    if hp and fund_number:
        matches = df[
            (df["חפ_נקי"] == hp)
            & (df["מספר_קופה_נקי"] == fund_number)
        ]
    # אם לא נמצאה התאמה, נסה להוסיף אפס בסוף מספר הקופה
    if matches.empty and hp and fund_number:
        fund_number_with_zero = fund_number + "0"

        matches = df[
            (df["חפ_נקי"] == hp)
            & (df["מספר_קופה_נקי"] == fund_number_with_zero)
        ]

    # 2. יש ח.פ אבל אין מספר קופה
    # מחפשים רשומה של אותו גוף שגם באקסל אין לה מספר קופה
    if matches.empty and hp and not fund_number:
        hp_matches = df[df["חפ_נקי"] == hp]

        empty_fund_number_matches = hp_matches[
            hp_matches["מספר_קופה_נקי"] == ""
        ]

        if len(empty_fund_number_matches) == 1:
            matches = empty_fund_number_matches

        # אם לח.פ כולו קיימת רק רשומה אחת באקסל
        elif len(hp_matches) == 1:
            matches = hp_matches

    # 3. התאמה מדויקת לפי שם הקופה
    if matches.empty and original_name:
        normalized_name = normalize_text(original_name)

        matches = df[
            df["שם_קופה_נקי"] == normalized_name
        ]

    # 4. התאמה חלקית לפי שם — רק אם נמצאה תוצאה יחידה
    if matches.empty and original_name:
        normalized_name = normalize_text(original_name)

        if normalized_name:
            partial_matches = df[
                df["שם_קופה_נקי"].apply(
                    lambda excel_name:
                    normalized_name in excel_name
                    or excel_name in normalized_name
                )
            ]

            if len(partial_matches) == 1:
                matches = partial_matches

    if matches.empty:
        return pd.Series({
            "שם_הקופה": original_name or "לא זוהה",
            "חשבון": "לא זוהה",
            "מספר קופה": fund_number or "לא זוהה",
            "סטטוס התאמה": "לא נמצאה התאמה",
        })

    if len(matches) > 1:
        return pd.Series({
            "שם_הקופה": original_name or "לא זוהה",
            "חשבון": "לא זוהה",
            "מספר קופה": fund_number or "לא זוהה",
            "סטטוס התאמה": "נמצאו מספר התאמות",
        })

    match = matches.iloc[0]

    return pd.Series({
        "שם_הקופה": clean_value(
            match["שם קופה / קרן"]
        ),
        "חשבון": match["חשבון_מלא"],
        "מספר קופה": clean_value(
            match["מספר קופה / קרן"]
        ) or "ללא מספר קופה",
        "סטטוס התאמה": (
            "התאמה לפי ח.פ"
            if hp and not fund_number
            else "התאמה מלאה"
        ),
    })
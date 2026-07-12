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
        row.get("חפ_גוף", "")
    )

    fund_number = clean_value(
        row.get("מספר קופה בקובץ", "")
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

    # התאמה לפי ח.פ ומספר קופה
    if hp and fund_number:
        matches = df[
            (df["חפ_נקי"] == hp)
            & (df["מספר_קופה_נקי"] == fund_number)
        ]

    # התאמה מדויקת לפי שם
    if matches.empty and original_name:
        normalized_name = normalize_text(original_name)

        matches = df[
            df["שם_קופה_נקי"] == normalized_name
        ]

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
        ),
        "סטטוס התאמה": "התאמה מלאה",
    })

import xml.etree.ElementTree as ET


def clean_tag(tag: str) -> str:
    """
    מסיר namespace מתג XML.
    """
    return tag.split("}")[-1]


def find_direct_child(parent, tag_name):
    """
    מחפש ילד ישיר בלבד ולא ערך שנמצא עמוק יותר בתוך האלמנט.
    """
    for child in list(parent):
        if clean_tag(child.tag) == tag_name:
            return child

    return None


def find_direct_text(parent, tag_name, default="") -> str:
    child = find_direct_child(parent, tag_name)

    if child is None or child.text is None:
        return default

    return child.text.strip()


def find_all_by_tag(parent, tag_name):
    for element in parent.iter():
        if clean_tag(element.tag) == tag_name:
            yield element


def to_float(value) -> float:
    try:
        cleaned_value = str(value).replace(",", "").strip()
        return float(cleaned_value)
    except (TypeError, ValueError):
        return 0.0


def parse_kupa_identifier(value):
    """
    מבנה הקוד הוא בדרך כלל:

    9 ספרות ראשונות: ח.פ הגוף
    לאחר מכן אפסים
    לאחר מכן מספר הקופה
    ולבסוף אפסים

    דוגמאות:
    512065202000000000001630000000 -> ח.פ 512065202, קופה 163
    512267592000000000018770000000 -> ח.פ 512267592, קופה 1877
    """
    value = str(value or "").strip()

    if len(value) < 9:
        return "", ""

    hp = value[:9]
    rest = value[9:]

    # מסיר אפסים מסוף הקוד ואז אפסים מתחילתו
    fund_number = rest.rstrip("0").lstrip("0")

    return hp, fund_number


def normalize_id(value) -> str:
    """
    שומר תעודת זהות עם אפסים מובילים.
    """
    value = str(value or "").strip()

    if value.isdigit():
        return value.zfill(9)

    return value


def analyze_xml(uploaded_file):
    uploaded_file.seek(0)

    tree = ET.parse(uploaded_file)
    root = tree.getroot()

    funds_summary = []
    employees_rows = []

    for transfer in find_all_by_tag(
        root,
        "PirteiHaavaratKsafim",
    ):
        kupa_identifier = find_direct_text(
            transfer,
            "KOD-MEZAHE-KUPA-H-P",
        )

        hp_guf, fund_number = parse_kupa_identifier(
            kupa_identifier
        )

        # מחפשים רק קופות ששייכות להעברה הנוכחית
        kupa_elements = [
            element
            for element in list(transfer)
            if clean_tag(element.tag) == "PirteiKupa"
        ]

        # במקרה שבו PirteiKupa אינו ילד ישיר
        if not kupa_elements:
            kupa_elements = list(
                find_all_by_tag(transfer, "PirteiKupa")
            )

        for kupa in kupa_elements:
            fund_name = find_direct_text(
                kupa,
                "SHEM-KUPA-ETZEL-MAASIK",
                "לא זוהה",
            )

            fund_type = find_direct_text(
                kupa,
                "SUG-KUPA",
            )

            total_fund = 0.0
            worker_count = 0

            worker_elements = [
                element
                for element in list(kupa)
                if clean_tag(element.tag) == "PirteiOved"
            ]

            if not worker_elements:
                worker_elements = list(
                    find_all_by_tag(kupa, "PirteiOved")
                )

            for worker in worker_elements:
                worker_count += 1

                first_name = find_direct_text(
                    worker,
                    "SHEM-PRATI",
                )

                last_name = find_direct_text(
                    worker,
                    "SHEM-MISHPACHA",
                )

                full_name = " ".join(
                    part
                    for part in [first_name, last_name]
                    if part
                ).strip()

                if not full_name:
                    full_name = "לא זוהה"

                worker_id = normalize_id(
                    find_direct_text(
                        worker,
                        "MISPAR-MEZAHE",
                    )
                )

                employee_contribution = 0.0
                employer_contribution = 0.0
                severance_contribution = 0.0

                for contribution in find_all_by_tag(
                    worker,
                    "PizulHafrashotOvedBeKupa",
                ):
                    contribution_type = find_direct_text(
                        contribution,
                        "SUG-HAFRASHA",
                    )

                    contribution_amount = to_float(
                        find_direct_text(
                            contribution,
                            "SCHUM-HAFRASHA",
                        )
                    )

                    # מיפוי נכון לפי הקובץ:
                    # 1 = פיצויים
                    # 2 = עובד
                    # 3 = מעסיק
                    if contribution_type == "1":
                        severance_contribution += contribution_amount

                    elif contribution_type == "2":
                        employee_contribution += contribution_amount

                    elif contribution_type == "3":
                        employer_contribution += contribution_amount

                worker_total = round(
                    employee_contribution
                    + employer_contribution
                    + severance_contribution,
                    2,
                )

                total_fund += worker_total

                employees_rows.append({
                    "שם מלא": full_name,
                    "ת.ז": worker_id,
                    "שם_הקופה": fund_name,
                    "חפ_גוף": hp_guf,
                    "מספר קופה בקובץ": fund_number,
                    "סכום העברה": worker_total,
                    "הפרשות עובד": round(
                        employee_contribution,
                        2,
                    ),
                    "הפרשות מעסיק": round(
                        employer_contribution,
                        2,
                    ),
                    "הפרשות פיצויים": round(
                        severance_contribution,
                        2,
                    ),
                })

            funds_summary.append({
                "שם_הקופה": fund_name,
                "סכום העברה": round(total_fund, 2),
                "חפ_גוף": hp_guf,
                "מספר קופה בקובץ": fund_number,
                "סוג קופה": fund_type,
                "מספר עובדים": worker_count,
            })

    return {
        "funds": funds_summary,
        "employees": employees_rows,
    }
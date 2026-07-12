import io
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

from services.openai_service import analyze_pension_image
from services.account_lookup import find_account_by_row
from services.xml_parser import analyze_xml


st.set_page_config(
    page_title="LYN AI",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 LYN AI")
st.subheader("מערכת חכמה לניתוח מסלקה פנסיונית")
st.divider()

client = st.text_input("שם הלקוח")

uploaded_file = st.file_uploader(
    "העלה תמונה או קובץ XML/DAT",
    type=["png", "jpg", "jpeg", "xml", "dat"],
)


def format_money_dataframe(dataframe, money_columns):
    column_config = {}

    for column in money_columns:
        if column in dataframe.columns:
            column_config[column] = st.column_config.NumberColumn(
                column,
                format="%.2f ₪",
            )

    return column_config


def build_excel_file(summary_df, employees_df):
    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:
        summary_df.to_excel(
            writer,
            sheet_name="סיכום קופות",
            index=False,
        )

        if not employees_df.empty:
            employees_df.to_excel(
                writer,
                sheet_name="פירוט עובדים",
                index=False,
            )

        workbook = writer.book

        for worksheet in workbook.worksheets:
            worksheet.sheet_view.rightToLeft = True
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

            for cell in worksheet[1]:
                cell.font = cell.font.copy(
                    bold=True,
                    color="FFFFFF",
                )
                cell.fill = cell.fill.copy(
                    fill_type="solid",
                    fgColor="1F4E78",
                )

            for column_cells in worksheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter

                for cell in column_cells:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, len(value))

                worksheet.column_dimensions[
                    column_letter
                ].width = min(max(max_length + 3, 12), 35)

    output.seek(0)
    return output


if uploaded_file:
    st.success("✅ הקובץ הועלה בהצלחה")

    if st.button(
        "נתח קובץ",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("מנתח את הקובץ..."):
                filename = uploaded_file.name.lower()

                if filename.endswith((".xml", ".dat")):
                    result = analyze_xml(uploaded_file)
                    source_type = "xml"
                else:
                    result = analyze_pension_image(uploaded_file)
                    source_type = "image"

            funds = result.get("funds", [])
            employees = result.get("employees", [])

            funds_df = pd.DataFrame(funds)
            employees_df = pd.DataFrame(employees)

            # התמונות מחזירות fund_name ו-amount
            # ה-XML מחזיר שמות עמודות בעברית
            funds_df = funds_df.rename(columns={
                "fund_name": "שם_הקופה",
                "amount": "סכום העברה",
                "סכום": "סכום העברה",
            })

            if funds_df.empty:
                st.warning("לא נמצאו קופות בקובץ.")
                st.stop()

            lookup_results = funds_df.apply(
                find_account_by_row,
                axis=1,
            )

            funds_df["שם קופה"] = lookup_results[
                "שם_הקופה"
            ]

            funds_df[
                "חשבון (בנק-סניף-חשבון)"
            ] = lookup_results["חשבון"]

            funds_df["סטטוס התאמה"] = lookup_results[
                "סטטוס התאמה"
            ]

            summary_df = funds_df[[
                "שם קופה",
                "סכום העברה",
                "חשבון (בנק-סניף-חשבון)",
            ]].copy()

            # יצירת מפת התאמות כדי שגם טבלת העובדים
            # תקבל את שם הקופה הרשמי מהאקסל
            if not employees_df.empty:
                employees_lookup = employees_df.apply(
                    find_account_by_row,
                    axis=1,
                )

                employees_df["שם קופה"] = employees_lookup[
                    "שם_הקופה"
                ]

                employees_display_df = employees_df[[
                    "שם מלא",
                    "ת.ז",
                    "שם קופה",
                    "סכום העברה",
                    "הפרשות עובד",
                    "הפרשות מעסיק",
                    "הפרשות פיצויים",
                ]].copy()

                employees_display_df["ת.ז"] = (
                    employees_display_df["ת.ז"]
                    .fillna("")
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.zfill(9)
                )
            else:
                employees_display_df = pd.DataFrame(columns=[
                    "שם מלא",
                    "ת.ז",
                    "שם קופה",
                    "סכום העברה",
                    "הפרשות עובד",
                    "הפרשות מעסיק",
                    "הפרשות פיצויים",
                ])

            st.subheader("טבלה 1 – סיכום קופות")

            st.dataframe(
                summary_df,
                use_container_width=True,
                hide_index=True,
                column_config=format_money_dataframe(
                    summary_df,
                    ["סכום העברה"],
                ),
            )

            if not employees_display_df.empty:
                st.subheader("טבלה 2 – פירוט עובדים")

                st.dataframe(
                    employees_display_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config=format_money_dataframe(
                        employees_display_df,
                        [
                            "סכום העברה",
                            "הפרשות עובד",
                            "הפרשות מעסיק",
                            "הפרשות פיצויים",
                        ],
                    ),
                )

            elif source_type == "image":
                st.info(
                    "בתמונה נמצאה רק טבלת סיכום. "
                    "כדי להפיק פירוט עובדים, יש להעלות XML/DAT "
                    "או תמונה המכילה את פירוט העובדים."
                )

            excel_file = build_excel_file(
                summary_df,
                employees_display_df,
            )

            download_name = (
                f"{client.strip()}_הפקדות.xlsx"
                if client.strip()
                else "טבלאות_הפקדות.xlsx"
            )

            st.download_button(
                label="⬇️ הורד קובץ Excel",
                data=excel_file,
                file_name=download_name,
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

            unmatched = funds_df[
                funds_df["סטטוס התאמה"] != "התאמה מלאה"
            ]

            if not unmatched.empty:
                with st.expander("⚠️ קופות שלא הותאמו באופן מלא"):
                    st.dataframe(
                        unmatched[[
                            "שם_הקופה",
                            "חפ_גוף",
                            "מספר קופה בקובץ",
                            "סטטוס התאמה",
                        ]],
                        use_container_width=True,
                        hide_index=True,
                    )

        except ET.ParseError:
            st.error(
                "הקובץ אינו XML תקין או שהוא פגום."
            )

        except Exception as error:
            st.error(f"שגיאה בניתוח הקובץ: {error}")
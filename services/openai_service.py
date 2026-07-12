from openai import OpenAI
from dotenv import load_dotenv
import os
import base64
import json

import os
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def get_openai_api_key():
    # קודם מנסה לקרוא מה-Secrets של Streamlit Cloud
    try:
        return st.secrets["OPENAI_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass

    # במקרה של עבודה מקומית, קורא מקובץ .env
    return os.getenv("OPENAI_API_KEY")


api_key = get_openai_api_key()

if not api_key:
    raise ValueError("לא נמצא OPENAI_API_KEY")

client = OpenAI(api_key=api_key)


def analyze_pension_image(uploaded_file):
    image_bytes = uploaded_file.getvalue()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.responses.create(
        model="gpt-5.5",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": """
אתה מומחה בקריאת מסלקות פנסיוניות בישראל.

החזר JSON בלבד.

חלץ אך ורק את:
- שם הקופה
- הסכום מתוך העמודה "סכום תנועות שדווחו לקופה"

אל תיקח סכומים מעמודות אחרות.
אל תנחש.

הפורמט חייב להיות:

{
  "funds": [
    {
      "fund_name": "",
      "amount": 0
    }
  ]
}
"""
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{base64_image}"
                    }
                ]
            }
        ]
    )

    text = response.output_text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return json.loads(text)

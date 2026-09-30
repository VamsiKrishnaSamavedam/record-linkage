import re
import unicodedata
import pandas as pd


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(
        character
        for character in text
        if unicodedata.category(character) != "Mn"
    )

    text = re.sub(r"[^a-zñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text
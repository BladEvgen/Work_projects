import os

import mysql.connector
import pandas as pd
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


def platonus_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


connection = platonus_connection()

df = pd.read_sql_query("SELECT * FROM users", connection)

unique_study_language_ids = df["StudyLanguageID"].unique()

print(unique_study_language_ids)

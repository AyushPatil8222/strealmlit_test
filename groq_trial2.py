import pyodbc
import re
import json
from datetime import date, datetime
from groq import Groq
from dotenv import load_dotenv
import os
# =========================================================
# CONFIG
# ========================================================
# 🔥 LOAD .env FIRST
load_dotenv()

# THEN read env vars
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")
DB_NAME = os.getenv("DB_NAME")
DB_SERVER = os.getenv("DB_SERVER")



FORBIDDEN_SQL_PATTERN = r"\b(insert|update|delete|drop|alter|truncate|exec|merge|create)\b"

# =========================================================
# GROQ CLIENT
# =========================================================
client = Groq(api_key=GROQ_API_KEY)

def groq_call(prompt, temperature=0):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "You are a precise enterprise HR assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# =========================================================
# DATABASE CONNECTION
# =========================================================
def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        "Trusted_Connection=yes;"
    )

# =========================================================
# LOAD SCHEMA
# =========================================================
def load_schema():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """)
    schema = {}
    for table, column in cursor.fetchall():
        schema.setdefault(table, []).append(column)
    conn.close()
    return schema

# =========================================================
# SANITIZE SQL
# =========================================================
def sanitize_sql(sql: str) -> str:
    sql = re.sub(r"```sql|```", "", sql, flags=re.IGNORECASE)
    sql = sql.replace("`", "").strip()
    return sql

def validate_sql(sql: str):
    sql_lower = sql.lower().strip()
    if not sql_lower.startswith("select"):
        raise ValueError("Only SELECT queries allowed")
    if re.search(FORBIDDEN_SQL_PATTERN, sql_lower):
        raise ValueError("Unsafe SQL detected")

# =========================================================
# SQL GENERATION
# =========================================================
def generate_sql(question: str, schema: dict) -> str:
    """
    Generates a safe, fully-qualified SQL query from a natural language question.
    Automatically includes any columns referenced in the query (WHERE/JOIN/GROUP/ORDER BY).
    
    Args:
        question (str): The user's natural language question.
        schema (dict): Database schema {table_name: [columns]}.
    
    Returns:
        str: Sanitized SQL query ready for execution.
    """

    # 1️⃣ Convert schema to LLM-readable text
    schema_text = "\n".join(f"{table}({', '.join(cols)})" for table, cols in schema.items())

    # 2️⃣ Prompt LLM to generate SQL
    # Key improvements:
    # - Always include in SELECT any column used in WHERE/JOIN
    # - Include all relevant columns for human-readable answers
    # - Do not invent columns
    # - Use LEFT JOIN when unsure if related table may be empty
    prompt = f"""
You are an expert SQL Server developer.

Task:
- Generate a fully correct SELECT query for the user question.
- Include in SELECT all columns that are:
    - Used in WHERE, JOIN, GROUP BY, ORDER BY
    - Relevant for a human-readable answer
- Always use LEFT JOIN for related tables unless filtering requires INNER JOIN
- Use dbo.TableName syntax
- Do not invent any column names
- Use TOP, ORDER BY, GROUP BY only if required

Database Schema:
{schema_text}

User Question:
{question}

Return ONLY the raw SQL.
"""

    raw_sql = groq_call(prompt, temperature=0)

    # 3️⃣ Sanitize SQL
    sql = sanitize_sql(raw_sql)

    # 4️⃣ Safety check
    validate_sql(sql)

    return sql

# =========================================================
# SQL EXECUTION
# =========================================================
def execute_sql(sql: str):
    validate_sql(sql)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    cols = [c[0] for c in cursor.description]
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(cols, row)) for row in rows]

# =========================================================
# EXPERIENCE CALCULATION
# =========================================================
def calculate_experience(joining_date):
    if not joining_date:
        return "N/A"
    if isinstance(joining_date, datetime):
        joining_date = joining_date.date()
    today = date.today()
    delta = today - joining_date
    years = delta.days // 365
    months = (delta.days % 365) // 30
    return f"{years} years {months} months"

# =========================================================
# HUMAN READABLE ANSWER
# =========================================================
def generate_answer(question: str, data: list):
    prompt = f"""
You are a senior HR assistant.

Question:
{question}

Database Result:
{json.dumps(data, default=str)}

Rules:
- Give concise, human-readable answers
- If multiple rows, use numbered list
- Include experience where relevant
- Do not invent data
"""
    return groq_call(prompt)

# =========================================================
# FULL PIPELINE
# =========================================================
def ask_hr_bot(question: str):
    schema = load_schema()
    sql = generate_sql(question, schema)
    data = execute_sql(sql)
    answer = generate_answer(question, data)
    return {
        "sql": sql,
        "answer": answer,
        "raw_data": data
    }

# =========================================================
# CLI
# =========================================================
if __name__ == "__main__":
    print("🤖 Expert HR Chatbot (Groq, type 'exit' to quit)")

    while True:
        q = input("\nAsk: ")
        if q.lower() in ("exit", "quit"):
            break
        try:
            res = ask_hr_bot(q)
            print("\n🧠 SQL:\n", res["sql"])
            print("\n🤖 Answer:\n", res["answer"])
        except Exception as e:
            print("\n❌ Error:", e)

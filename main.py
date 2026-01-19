# main.py - RAG Compliance Chatbot (PostgreSQL Only)
import re
from urllib.parse import quote_plus
from langchain_ollama import OllamaLLM
from langchain_community.utilities import SQLDatabase
from sqlalchemy.exc import SQLAlchemyError


MODEL_NAME = "llama3.2:3b"


DB_CONFIG = {
    "user": "postgres",
    "password": "Nikhil@0987",
    "host": "localhost",
    "port": "5432",
    "dbname": "complykaro"
}


DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{DB_CONFIG['user']}:{quote_plus(DB_CONFIG['password'])}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
)


RAG_PROMPT = """You are a Companies Act 2013 compliance expert.

DATABASE QUERY RESULTS:
{db_context}

USER QUESTION: {question}

Based on the database records above, provide a professional answer covering:
1. What compliance action is required
2. Specific steps to take
3. Applicable legal section
4. Penalties for non-compliance

If no relevant records found, state that clearly and suggest the user check database entries.

Answer:"""


def generate_sql(llm, question: str, db: SQLDatabase) -> str:
    """Generate safe SQL query from natural language question"""
    tables = db.get_usable_table_names()
    
    if not tables:
        return "SELECT 1;"
    
    table_info = db.get_table_info(tables[:3])  # Get schema for top 3 tables
    
    prompt = f"""Database Schema:
{table_info}

User Question: "{question}"

Generate ONLY a SELECT query that answers this question.
Requirements:
- Use ILIKE for text search (case-insensitive)
- Add LIMIT 20
- No DELETE/UPDATE/DROP
- Return relevant columns only

SQL Query:"""
    
    sql_raw = llm.invoke(prompt)
    
    # Clean and validate SQL
    sql = sql_raw.strip()
    
    # Remove markdown code blocks if present
    sql = re.sub(r'```sql|```', '', sql).strip()
    
    # Extract SELECT statement
    select_match = re.search(r'(SELECT.*?);?$', sql, re.IGNORECASE | re.DOTALL)
    if select_match:
        sql = select_match.group(1)
    
    # Safety check
    dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE']
    if any(keyword in sql.upper() for keyword in dangerous_keywords):
        sql = f"SELECT * FROM {tables[0]} LIMIT 5"
    
    if not sql.upper().startswith('SELECT'):
        sql = f"SELECT * FROM {tables[0]} LIMIT 5"
    
    # Ensure LIMIT exists
    if 'LIMIT' not in sql.upper():
        sql += ' LIMIT 20'
    
    return sql


def query_database(llm, db: SQLDatabase, question: str) -> str:
    """Execute database query and return formatted results"""
    try:
        sql = generate_sql(llm, question, db)
        print(f"📝 Generated SQL: {sql}\n")
        
        result = db.run(sql)
        
        if not result or result.strip() == "[]":
            return "No matching records found in database."
        
        return result
    
    except SQLAlchemyError as e:
        return f"Database query error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("🔥 RAG Compliance Chatbot")
    print("Database-Driven Knowledge Base")
    print("=" * 50)

    # Connect to PostgreSQL
    try:
        db = SQLDatabase.from_uri(DATABASE_URL)
        print("✅ PostgreSQL Connected")
        tables = db.get_usable_table_names()
        print(f"📋 Available Tables: {', '.join(tables)}")
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        print("💡 Ensure PostgreSQL service is running")
        return

    # Initialize LLM
    try:
        llm = OllamaLLM(model=MODEL_NAME, temperature=0.1)
        print(f"✅ {MODEL_NAME} Ready\n")
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        print("💡 Run: ollama pull llama3.2:3b && ollama serve")
        return

    print("🚀 Ask compliance questions (type 'quit' to exit):")
    print("💡 Example: 'What compliance needed for fire incident?'")
    print("💡 Example: 'Show public company requirements'")
    print("-" * 50)

    while True:
        question = input("\nYou: ").strip()
        
        if question.lower() in {"quit", "exit", "bye"}:
            print("\n👋 Goodbye!")
            break
        
        if not question:
            continue

        print("\n🔍 Searching database...")

        # Query database for relevant information
        db_context = query_database(llm, db, question)
        
        # Generate answer using RAG
        prompt = RAG_PROMPT.format(
            db_context=db_context,
            question=question
        )
        
        answer = llm.invoke(prompt)
        
        print("\n✅ Answer:")
        print("-" * 40)
        print(answer)
        print("-" * 40)
        print("📊 Source: PostgreSQL Database")
        print("-" * 50)


if __name__ == "__main__":
    main()

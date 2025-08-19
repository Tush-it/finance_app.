import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px
import hashlib

# -------------------------------------
# Database config
# -------------------------------------
DB = 'finance_app.db'
DEFAULT_CATEGORIES = ["Food", "Transport", "Health", "Entertainment", "Other"]

def connect_db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = connect_db()
    c = conn.cursor()

    # Users with password hash
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )''')

    # Categories
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        username TEXT,
        category TEXT,
        PRIMARY KEY (username, category)
    )''')

    # Expenses
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        date TEXT,
        category TEXT,
        amount REAL,
        description TEXT
    )''')

    # Budgets
    c.execute('''CREATE TABLE IF NOT EXISTS budget (
        username TEXT,
        category TEXT,
        monthly_limit REAL,
        PRIMARY KEY(username, category)
    )''')

    conn.commit()
    conn.close()

# -------------------------------------
# Auth Helpers
# -------------------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def signup_user(username: str, password: str) -> bool:
    conn = connect_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        # add default categories
        for cat in DEFAULT_CATEGORIES:
            c.execute("INSERT OR IGNORE INTO categories (username, category) VALUES (?, ?)", (username, cat))
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok

def login_user(username: str, password: str) -> bool:
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == hash_password(password):
        return True
    return False

def user_exists(username: str) -> bool:
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row is not None

# -------------------------------------
# Categories
# -------------------------------------
def get_categories(username: str) -> pd.DataFrame:
    conn = connect_db()
    df = pd.read_sql_query("SELECT category FROM categories WHERE username = ? ORDER BY category", conn, params=(username,))
    conn.close()
    return df

def add_category(username: str, category: str) -> bool:
    if not category:
        return False
    conn = connect_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (username, category) VALUES (?, ?)", (username, category.strip()))
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok

def delete_category(username: str, category: str) -> None:
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM expenses WHERE username=? AND category=?", (username, category))
    exp_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM budget WHERE username=? AND category=?", (username, category))
    bud_count = c.fetchone()[0]
    if exp_count == 0 and bud_count == 0:
        c.execute("DELETE FROM categories WHERE username=? AND category=?", (username, category))
        conn.commit()
    conn.close()

# -------------------------------------
# Expenses
# -------------------------------------
def add_expense(username, date_str, category, amount, description):
    conn = connect_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO expenses (username, date, category, amount, description) VALUES (?, ?, ?, ?, ?)",
        (username, date_str, category, float(amount), description.strip())
    )
    conn.commit()
    conn.close()

def get_expenses(username) -> pd.DataFrame:
    conn = connect_db()
    df = pd.read_sql_query(
        "SELECT id, date, category, amount, description FROM expenses WHERE username = ?",
        conn, params=(username,)
    )
    conn.close()
    return df

def delete_expense(expense_id: int):
    conn = connect_db()
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()

# -------------------------------------
# Budgets
# -------------------------------------
def set_budget(username, category, limit):
    conn = connect_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO budget (username, category, monthly_limit) VALUES (?, ?, ?)",
        (username, category, float(limit))
    )
    conn.commit()
    conn.close()

def get_budget(username) -> pd.DataFrame:
    conn = connect_db()
    df = pd.read_sql_query(
        "SELECT category, monthly_limit FROM budget WHERE username = ?",
        conn, params=(username,)
    )
    conn.close()
    return df

# -------------------------------------
# Helpers
# -------------------------------------
def current_month_key(dt: datetime) -> str:
    return dt.strftime('%Y-%m')

def month_filter(df: pd.DataFrame, dt: datetime) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    key = current_month_key(dt)
    return df[df['date'].dt.strftime('%Y-%m') == key]

def format_inr(x: float) -> str:
    return f"₹{x:,.2f}"

# -------------------------------------
# App
# -------------------------------------
def main():
    st.set_page_config(page_title="💰 Finance App", layout="wide")
    st.title("💰 Personal Finance Manager")
    init_db()

    # ---------------- AUTH ----------------
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None

    if st.session_state.auth_user is None:
        tab1, tab2 = st.tabs(["🔑 Login", "🆕 Sign Up"])

        with tab1:
            st.subheader("Login")
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", type="primary"):
                if login_user(username, password):
                    st.session_state.auth_user = username
                    st.success("Logged in successfully! Refreshing...")
                    st.experimental_rerun()
                else:
                    st.error("Invalid username or password.")

        with tab2:
            st.subheader("Sign Up")
            new_user = st.text_input("New Username", key="signup_user")
            new_pass = st.text_input("New Password", type="password", key="signup_pass")
            if st.button("Create Account"):
                if not new_user or not new_pass:
                    st.error("Please fill both fields.")
                elif user_exists(new_user):
                    st.warning("Username already exists, choose another.")
                else:
                    if signup_user(new_user, new_pass):
                        st.success("Account created! Please log in.")
                    else:
                        st.error("Failed to create account.")
        return

    # If logged in
    username = st.session_state.auth_user
    st.sidebar.success(f"👋 Hello, {username}")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.auth_user = None
        st.experimental_rerun()

    # ---------------- MAIN APP ----------------
    from_finance_app(username)


def from_finance_app(username: str):
    """Wrapped main app for logged in user"""
    # Tabs UI
    tab_dashboard, tab_add, tab_budget, tab_reports, tab_io = st.tabs(
        ["🏠 Dashboard", "➕ Add Expense", "💸 Budget", "📊 Reports", "📤 Import / 📥 Export"]
    )

    cat_df = get_categories(username)
    categories = cat_df['category'].tolist()
    exp_df = get_expenses(username)
    bud_df = get_budget(username)

    # ---------------- Dashboard ----------------
    with tab_dashboard:
        st.subheader("📊 Dashboard")
        if exp_df.empty:
            st.info("No data yet. Add some expenses in the 'Add Expense' tab!")
        else:
            exp_df_local = exp_df.copy()
            exp_df_local['date'] = pd.to_datetime(exp_df_local['date'])
            month_expenses = month_filter(exp_df_local, datetime.now())

            total = float(month_expenses['amount'].sum()) if not month_expenses.empty else 0.0
            daily_avg = month_expenses.groupby(month_expenses['date'].dt.date)['amount'].sum().mean() if not month_expenses.empty else 0.0

            c1, c2 = st.columns(2)
            c1.metric("📅 Total This Month", format_inr(total))
            c2.metric("📈 Daily Avg (This Month)", format_inr(daily_avg))

            # Budget alerts + overview
            if not bud_df.empty:
                spent_by_cat = month_expenses.groupby('category')['amount'].sum().reset_index() if not month_expenses.empty else pd.DataFrame(columns=['category','amount'])
                merged = pd.merge(bud_df, spent_by_cat, on='category', how='left').fillna({'amount': 0.0})
                merged['status'] = merged['amount'] / merged['monthly_limit']
                for _, row in merged.iterrows():
                    if row['monthly_limit'] <= 0:
                        continue
                    if row['status'] > 1:
                        st.warning(f"🚨 Over budget in {row['category']}: {format_inr(row['amount'])}/{format_inr(row['monthly_limit'])}")
                    elif row['status'] > 0.8:
                        st.info(f"⚠️ Almost at limit for {row['category']}: {format_inr(row['amount'])}/{format_inr(row['monthly_limit'])}")
                st.dataframe(merged[['category','monthly_limit','amount']].rename(columns={'monthly_limit':'Monthly Limit','amount':'Spent'}))

    # ---------------- Add Expense ----------------
    with tab_add:
        st.subheader("🧾 Add New Expense")
        d = st.date_input("Date", value=date.today())
        cat_col, amt_col = st.columns([2,1])
        with cat_col:
            category = st.selectbox("Category", options=categories if categories else ["— No categories —"])
        with amt_col:
            amount = st.number_input("Amount (₹)", min_value=0.01, format="%.2f")
        desc = st.text_input("Description", "")
        if st.button("➕ Add Expense", type="primary"):
            add_expense(username, d.strftime('%Y-%m-%d'), category, amount, desc)
            st.success("Expense added!")

    # ---------------- Budget ----------------
    with tab_budget:
        st.subheader("💸 Set Monthly Budgets")
        if categories:
            bcat = st.selectbox("Budget Category", options=categories)
            blimit = st.number_input("Monthly Limit (₹)", min_value=0.01, format="%.2f")
            if st.button("💾 Save Budget", type="primary"):
                set_budget(username, bcat, blimit)
                st.success("Budget saved!")
        bud = get_budget(username)
        if not bud.empty:
            st.dataframe(bud)

    # ---------------- Reports ----------------
    with tab_reports:
        st.subheader("📈 Expense Reports")
        df = get_expenses(username)
        if df.empty:
            st.warning("No data to show.")
        else:
            df['date'] = pd.to_datetime(df['date'])
            with st.expander("🗂 View Table"):
                st.dataframe(df.sort_values('date', ascending=False))
            with st.expander("🗑 Delete Expense"):
                del_id = st.selectbox("Select Expense ID", options=df['id'].tolist())
                if st.button("Delete Expense"):
                    delete_expense(int(del_id))
                    st.success("Deleted!")
            pie = px.pie(df, values='amount', names='category', title='Spending by Category')
            st.plotly_chart(pie, use_container_width=True)

    # ---------------- Import/Export ----------------
    with tab_io:
        st.subheader("📤 Export / 📥 Import")
        df = get_expenses(username)
        if not df.empty:
            csv = df.to_csv(index=False).encode()
            st.download_button("Download Expenses", csv, file_name=f"{username}_expenses.csv", mime='text/csv')


if __name__ == "__main__":
    main()

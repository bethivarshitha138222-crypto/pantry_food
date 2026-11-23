import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------- PAGE SETTINGS ----------------
st.set_page_config(
    page_title="Food Pantry Tracker",
    page_icon="🥗",
    layout="wide"
)

# ---------------- DATABASE ----------------
DB_PATH = Path(__file__).resolve().parent / "food_pantry.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS foods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    quantity INTEGER,
    purchase_date TEXT,
    expiry_date TEXT,
    location TEXT,
    added_date TEXT
)
""")

# Safely upgrade an older database without deleting existing food records.
columns = [row[1] for row in cursor.execute("PRAGMA table_info(foods)").fetchall()]
if "added_date" not in columns:
    cursor.execute("ALTER TABLE foods ADD COLUMN added_date TEXT")
    cursor.execute("""
        UPDATE foods
        SET added_date = COALESCE(purchase_date, date('now'))
        WHERE added_date IS NULL
    """)
conn.commit()


# ---------------- THEME ----------------
if "theme" not in st.session_state:
    st.session_state.theme = "Light"

st.sidebar.title("🥗 Food Pantry")
st.sidebar.caption("Expiry Management System")

theme = st.sidebar.radio(
    "Choose appearance",
    ["Light", "Dark"],
    index=0 if st.session_state.theme == "Light" else 1,
    horizontal=True,
    key="theme_choice"
)
st.session_state.theme = theme

if theme == "Dark":
    page_bg = "#111827"
    panel_bg = "#1f2937"
    text_color = "#f9fafb"
    muted_color = "#cbd5e1"
    border_color = "#374151"
    input_bg = "#273449"
    metric_bg = "#1f2937"
else:
    page_bg = "#f5f8f2"
    panel_bg = "#ffffff"
    text_color = "#1f2937"
    muted_color = "#526052"
    border_color = "#dce9dc"
    input_bg = "#ffffff"
    metric_bg = "#ffffff"

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {page_bg};
        color: {text_color};
    }}
    [data-testid="stSidebar"] {{
        background-color: {panel_bg};
    }}
    [data-testid="stHeader"] {{
        background-color: {page_bg};
    }}
    h1, h2, h3, h4, p, label, .stMarkdown, [data-testid="stCaptionContainer"] {{
        color: {text_color};
    }}
    div[data-testid="stMetric"] {{
        background-color: {metric_bg};
        padding: 18px;
        border-radius: 12px;
        border: 1px solid {border_color};
    }}
    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    textarea {{
        background-color: {input_bg};
        color: {text_color};
        border-color: {border_color};
    }}
    [data-testid="stDataFrame"], [data-testid="stTable"] {{
        border: 1px solid {border_color};
        border-radius: 8px;
    }}
    </style>
    """,
    unsafe_allow_html=True
)


# ---------------- HELPER FUNCTIONS ----------------
def get_foods():
    return pd.read_sql_query(
        "SELECT * FROM foods ORDER BY expiry_date, added_date DESC",
        conn
    )


def get_status(expiry):
    expiry_day = date.fromisoformat(str(expiry))
    days_left = (expiry_day - date.today()).days

    if days_left < 0:
        return "Expired"
    if days_left <= 3:
        return "Critical"
    if days_left <= 7:
        return "Expiring Soon"
    return "Fresh"


def add_tracking_columns(df):
    if df.empty:
        return df

    df = df.copy()
    df["Added Date"] = pd.to_datetime(df["added_date"], errors="coerce").dt.date
    df["Days Stored"] = df["Added Date"].apply(
        lambda added: (date.today() - added).days if pd.notna(added) else 0
    )
    df["Expiry Status"] = df["expiry_date"].apply(get_status)
    return df


def save_food(name, category, quantity, purchase, expiry, location):
    cursor.execute(
        """
        INSERT INTO foods
        (name, category, quantity, purchase_date, expiry_date, location, added_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name, category, quantity, str(purchase),
            str(expiry), location, date.today().isoformat()
        )
    )
    conn.commit()


# ---------------- SIDEBAR NAVIGATION ----------------
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Add Food", "Inventory", "Expiry Alerts", "Reports"]
)

st.sidebar.markdown("---")
st.sidebar.info("Manage food smartly. Reduce food waste!")
st.sidebar.caption("Food Pantry Expiry Tracker | Python Project")


# ---------------- DASHBOARD ----------------
if page == "Dashboard":
    st.title("🥗 Food Pantry Dashboard")
    st.write("Welcome! Manage your food inventory in one place.")

    df = add_tracking_columns(get_foods())
    total = len(df)

    if total:
        expired = (df["Expiry Status"] == "Expired").sum()
        critical = (df["Expiry Status"] == "Critical").sum()
        soon = (df["Expiry Status"] == "Expiring Soon").sum()
        fresh = (df["Expiry Status"] == "Fresh").sum()
    else:
        expired = critical = soon = fresh = 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Food Items", total)
    c2.metric("Fresh Items", int(fresh))
    c3.metric("Expiring Soon", int(soon + critical))
    c4.metric("Expired Items", int(expired))

    st.markdown("---")
    st.subheader("🗓️ Food Added in the Last 5 Days")
    st.caption(
        "Items added today and during the previous four days are shown here. "
        "They remain in your inventory after five days too."
    )

    if total:
        five_day_start = date.today() - timedelta(days=4)
        recent = df[df["Added Date"].apply(
            lambda d: pd.notna(d) and d >= five_day_start
        )]

        if not recent.empty:
            st.dataframe(
                recent[[
                    "name", "category", "quantity", "Added Date",
                    "Days Stored", "expiry_date", "Expiry Status"
                ]].rename(columns={
                    "name": "Food Item",
                    "category": "Category",
                    "quantity": "Quantity",
                    "expiry_date": "Expiry Date"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No food has been added in the last five days.")

        st.subheader("📦 All Saved Food Items")
        st.dataframe(
            df[[
                "name", "category", "quantity", "Added Date",
                "Days Stored", "expiry_date", "Expiry Status", "location"
            ]].rename(columns={
                "name": "Food Item",
                "category": "Category",
                "quantity": "Quantity",
                "expiry_date": "Expiry Date",
                "location": "Storage Location"
            }),
            use_container_width=True,
            hide_index=True
        )

        fig = px.pie(
            df,
            names="Expiry Status",
            title="Food Expiry Status",
            color="Expiry Status",
            color_discrete_map={
                "Fresh": "#38a169",
                "Expiring Soon": "#ecc94b",
                "Critical": "#ed8936",
                "Expired": "#e53e3e"
            }
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No food items added yet. Go to Add Food to get started.")


# ---------------- ADD FOOD ----------------
elif page == "Add Food":
    st.title("➕ Add Food Items")
    st.write("Enter the details of your food products.")

    with st.form("add_food_form", clear_on_submit=True):
        name = st.text_input("Food Item Name")

        category = st.selectbox(
            "Food Category",
            ["Fruits", "Vegetables", "Dairy", "Grains", "Snacks",
             "Canned Food", "Meat", "Beverages", "Other"]
        )

        quantity = st.number_input("Quantity", min_value=1, step=1)
        purchase = st.date_input("Purchase Date", value=date.today())
        expiry = st.date_input(
            "Expiry Date", value=date.today() + timedelta(days=7)
        )
        location = st.selectbox(
            "Storage Location",
            ["Refrigerator", "Freezer", "Kitchen Shelf",
             "Pantry Cabinet", "Other"]
        )

        submit = st.form_submit_button(
            "➕ Add Food Item",
            use_container_width=True
        )

        if submit:
            if not name.strip():
                st.error("Please enter the food item name.")
            elif expiry < purchase:
                st.error("Expiry date cannot be before purchase date.")
            else:
                save_food(
                    name.strip(), category, int(quantity),
                    purchase, expiry, location
                )
                st.success(f"{name} added successfully!")
                st.rerun()


# ---------------- INVENTORY ----------------
elif page == "Inventory":
    st.title("📦 Food Inventory Management")
    df = add_tracking_columns(get_foods())

    if df.empty:
        st.info("Your inventory is empty. Add some food items first.")
    else:
        search = st.text_input("🔍 Search Food Item")
        categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
        selected_category = st.selectbox("Filter by Category", categories)
        statuses = ["All", "Fresh", "Expiring Soon", "Critical", "Expired"]
        selected_status = st.selectbox("Filter by Expiry Status", statuses)

        filtered = df.copy()
        if search:
            filtered = filtered[
                filtered["name"].str.contains(search, case=False, na=False)
            ]
        if selected_category != "All":
            filtered = filtered[filtered["category"] == selected_category]
        if selected_status != "All":
            filtered = filtered[filtered["Expiry Status"] == selected_status]

        st.dataframe(
            filtered[[
                "id", "name", "category", "quantity", "purchase_date",
                "expiry_date", "Added Date", "Days Stored",
                "Expiry Status", "location"
            ]].rename(columns={
                "id": "ID",
                "name": "Food Item",
                "category": "Category",
                "quantity": "Quantity",
                "purchase_date": "Purchase Date",
                "expiry_date": "Expiry Date",
                "location": "Storage Location"
            }),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        st.subheader("✏️ Edit or Delete Food Items")
        ids = df["id"].tolist()
        selected_id = st.selectbox(
            "Select Food Item ID",
            ids,
            format_func=lambda x: (
                f"{x} - {df.loc[df['id'] == x, 'name'].iloc[0]}"
            )
        )
        item = df[df["id"] == selected_id].iloc[0]

        categories_all = [
            "Fruits", "Vegetables", "Dairy", "Grains", "Snacks",
            "Canned Food", "Meat", "Beverages", "Other"
        ]
        category_index = (
            categories_all.index(item["category"])
            if item["category"] in categories_all else 0
        )

        with st.form("edit_food_form"):
            edit_name = st.text_input("Food Name", value=item["name"])
            edit_category = st.selectbox(
                "Category", categories_all, index=category_index
            )
            edit_quantity = st.number_input(
                "Quantity", min_value=1, value=max(1, int(item["quantity"]))
            )
            edit_purchase = st.date_input(
                "Purchase Date", value=date.fromisoformat(item["purchase_date"])
            )
            edit_expiry = st.date_input(
                "Expiry Date", value=date.fromisoformat(item["expiry_date"])
            )
            edit_location = st.text_input(
                "Storage Location", value=item["location"] or ""
            )
            update = st.form_submit_button("Update Item")

            if update:
                if not edit_name.strip():
                    st.error("Food name cannot be empty.")
                elif edit_expiry < edit_purchase:
                    st.error("Expiry date cannot be before purchase date.")
                else:
                    cursor.execute(
                        """
                        UPDATE foods
                        SET name=?, category=?, quantity=?,
                            purchase_date=?, expiry_date=?, location=?
                        WHERE id=?
                        """,
                        (
                            edit_name.strip(), edit_category, int(edit_quantity),
                            str(edit_purchase), str(edit_expiry),
                            edit_location, selected_id
                        )
                    )
                    conn.commit()
                    st.success("Food item updated!")
                    st.rerun()

        if st.button("🗑️ Delete Selected Item", type="primary"):
            cursor.execute("DELETE FROM foods WHERE id=?", (selected_id,))
            conn.commit()
            st.success("Food item deleted!")
            st.rerun()


# ---------------- EXPIRY ALERTS ----------------
elif page == "Expiry Alerts":
    st.title("⚠️ Food Expiry Alerts")
    df = add_tracking_columns(get_foods())

    if df.empty:
        st.info("No food items available.")
    else:
        expired_items = df[df["Expiry Status"] == "Expired"]
        critical_items = df[df["Expiry Status"] == "Critical"]
        soon_items = df[df["Expiry Status"] == "Expiring Soon"]

        st.subheader("🔴 Expired Items")
        if not expired_items.empty:
            st.error("These food items have passed their expiry dates.")
            st.dataframe(expired_items, use_container_width=True, hide_index=True)
        else:
            st.success("No expired food items!")

        st.subheader("🟠 Expiring Within 3 Days")
        if not critical_items.empty:
            st.warning("Check these items immediately and follow food-safety guidance.")
            st.dataframe(critical_items, use_container_width=True, hide_index=True)
        else:
            st.success("No critical expiry alerts!")

        st.subheader("🟡 Expiring Within 7 Days")
        if not soon_items.empty:
            st.warning("These food items are expiring soon.")
            st.dataframe(soon_items, use_container_width=True, hide_index=True)
        else:
            st.success("No upcoming expiry alerts!")


# ---------------- REPORTS ----------------
elif page == "Reports":
    st.title("📊 Food Pantry Reports")
    df = add_tracking_columns(get_foods())

    if df.empty:
        st.info("Add food items to generate reports.")
    else:
        report = df.groupby("Expiry Status").size().reset_index(name="Count")
        fig = px.bar(
            report,
            x="Expiry Status",
            y="Count",
            color="Expiry Status",
            title="Food Inventory Analysis",
            color_discrete_map={
                "Fresh": "#38a169",
                "Expiring Soon": "#ecc94b",
                "Critical": "#ed8936",
                "Expired": "#e53e3e"
            }
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Download Inventory Report")
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download CSV Report",
            data=csv_data,
            file_name="food_pantry_report.csv",
            mime="text/csv"
        )
        st.success("Your inventory report is ready!")

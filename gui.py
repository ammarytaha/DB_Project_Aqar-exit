# gui.py · web GUI for the AqarExit resale database · run with:  streamlit run gui.py
import datetime
from decimal import Decimal

import pandas as pd
import pymysql
import streamlit as st

from queries import (register_user, addReview, get_reviews_by_project, top_10_Projects,
                     LocationOfDevelopment, PropertiesByArea, PropertiesByAreaPriceAmenities,
                     Top5Developers, PropertiesByAreaTypeYear, StatsByAreaAndProject,
                     list_areas, list_types, list_amenities, search_projects)

st.set_page_config(page_title="AqarExit Resale Explorer", page_icon="🏠", layout="wide")

# Streamlit reruns this whole script on every click, so remember the results of read-only queries
# for 10 minutes instead of asking Aiven again. Inserts (register, review) and the reviews page are
# not cached, so new users and reviews always show up immediately.
cached = st.cache_data(ttl=600, show_spinner="Loading from the database…")
top_10_Projects = cached(top_10_Projects)
LocationOfDevelopment = cached(LocationOfDevelopment)
PropertiesByArea = cached(PropertiesByArea)
PropertiesByAreaPriceAmenities = cached(PropertiesByAreaPriceAmenities)
Top5Developers = cached(Top5Developers)
PropertiesByAreaTypeYear = cached(PropertiesByAreaTypeYear)
StatsByAreaAndProject = cached(StatsByAreaAndProject)
search_projects = cached(search_projects)

# property columns, in table order (for queries that return SELECT *)
PROPERTY_COLUMNS = ["UnitCode", "Type", "PropertySize", "GardenSize", "AreaLocation", "BedRoomsNo", "BathsNo",
                    "Floor", "Finishing", "Completion", "DeliveryYear", "ContractYear", "Description",
                    "CurrentMP", "TotalPaid", "RemainingMoney", "InstallmentAmount", "InstallmentFrequency",
                    "RemainingYears", "AnnualInstallments", "GiveUpAmount", "OverDueNo", "OverdueAmount",
                    "OwnerEmail", "ProjectName", "DeveloperName"]
SHOWN_PROPERTY_COLUMNS = ["UnitCode", "Type", "PropertySize", "BedRoomsNo", "BathsNo", "Finishing",
                          "TotalPrice", "TotalPaid", "CurrentMP", "ProjectName", "DeveloperName"]


# The lists of valid values change rarely, so read them once per 10 minutes
@st.cache_data(ttl=600)
def areas():
    return list_areas()

@st.cache_data(ttl=600)
def types():
    return list_types()

@st.cache_data(ttl=600)
def amenities():
    return list_amenities()


def show(rows, columns):
    """Show query rows as a table, with numbers formatted with thousands separators."""
    df = pd.DataFrame(list(rows), columns=columns)
    if df.empty:
        st.info("No results.")
        return
    # MySQL averages arrive as Decimal; convert them to float so the table sorts and formats them as numbers
    df = df.apply(lambda column: column.map(lambda v: float(v) if isinstance(v, Decimal) else v))
    # display only: money and averages as whole numbers, small averages (contract age) with 1 decimal
    for col in df.select_dtypes("number").columns:
        df[col] = df[col].round(1 if df[col].abs().max() < 100 else 0)
    numbers = {col: st.column_config.NumberColumn(format="localized")
               for col in df.select_dtypes("number").columns}
    st.caption(f"{len(df)} row(s)")
    st.dataframe(df, width="stretch", hide_index=True, column_config=numbers)


def show_properties(rows):
    df = pd.DataFrame(list(rows), columns=PROPERTY_COLUMNS)
    df["TotalPrice"] = df["TotalPaid"] + df["RemainingMoney"]
    show(df[SHOWN_PROPERTY_COLUMNS].values.tolist(), SHOWN_PROPERTY_COLUMNS)


def pick_project(key):
    """A project is its name AND its developer: search by name, then pick one result."""
    text = st.text_input("Search project name (e.g. مدينتي, Badya)", key=f"{key}_search")
    if not text:
        return None
    found = search_projects(text)
    if not found:
        st.warning("No project matches that name.")
        return None
    labels = [f"{p} — {d} ({n} listings)" for p, d, n in found]
    index = st.selectbox("Project", range(len(found)), format_func=lambda i: labels[i], key=f"{key}_pick")
    return found[index][0], found[index][1]


def run_safely(action, success_message):
    try:
        action()
        st.success(success_message)
    except pymysql.err.IntegrityError as err:
        if err.args[0] == 1062:
            st.error("Not saved: this already exists (email already registered, or you already reviewed this project).")
        elif err.args[0] == 1452:
            st.error("Not saved: this email is not registered. Register first.")
        else:
            st.error(f"Not saved: {err.args[1]}")
    except pymysql.err.OperationalError as err:
        st.error(f"Database error: {err.args[1]}")


# ---------- pages ----------

def page_register():
    st.header("Register a user")
    with st.form("register"):
        email = st.text_input("Email")
        username = st.text_input("Username")
        gender = st.radio("Gender", ["Male", "Female"], horizontal=True)
        birthdate = st.date_input("Birth date", value=datetime.date(2000, 1, 1),
                                  min_value=datetime.date(1920, 1, 1), max_value=datetime.date.today())
        phone = st.text_input("Phone number")
        focus = st.multiselect("Main areas of focus", areas())
        if st.form_submit_button("Register"):
            if not (email and username and phone):
                st.error("Email, username and phone are required.")
            else:
                run_safely(lambda: register_user(email, username, gender, birthdate.isoformat(), phone, focus),
                           f"User {username} registered.")


def page_add_review():
    st.header("Add a review on a project")
    project = pick_project("review")
    if project:
        with st.form("review"):
            email = st.text_input("Your email (registered user)")
            rating = st.slider("Rating", 1, 10, 8)
            text = st.text_area("Your review")
            if st.form_submit_button("Submit review"):
                if not (email and text):
                    st.error("Email and review text are required.")
                else:
                    run_safely(lambda: addReview(email, project[0], project[1], rating, text), "Review added.")


def page_view_reviews():
    st.header("Reviews of a project")
    project = pick_project("view")
    if project:
        rows = get_reviews_by_project(*project)
        if rows:
            st.metric("Average rating", f"{sum(r[1] for r in rows) / len(rows):.1f} / 10")
        show(rows, ["User", "Rating", "Review"])


def page_top_projects():
    st.header("Top 10 projects")
    col1, col2 = st.columns(2)
    property_type = col1.selectbox("Property type", types(), index=types().index("شقة") if "شقة" in types() else 0)
    order = col2.radio("Rank by", ["inventory", "amount", "gain"], horizontal=True,
                       format_func={"inventory": "Resale inventory", "amount": "Resale amount",
                                    "gain": "Gain over market value"}.get)
    show(top_10_Projects(property_type, order),
         ["Project", "Developer", "Listings", "Resale amount (EGP)", "Avg gain (EGP)"])


def page_location():
    st.header("Location of a development")
    project = pick_project("location")
    if project:
        show(LocationOfDevelopment(*project), ["Location", "Unit type", "Avg price per m² (EGP)", "Listings"])


def page_area():
    st.header("Properties in an area")
    area = st.selectbox("Area", areas())
    properties, averages = PropertiesByArea(area)
    st.subheader("Average price per m² for each unit type")
    show(averages, ["Unit type", "Avg price per m² (EGP)"])
    st.subheader("Properties")
    show(properties, ["Unit code", "Type", "Size (m²)", "Total price (EGP)"])


def page_search():
    st.header("Search an area by price range and amenities")
    area = st.selectbox("Area", areas())
    col1, col2 = st.columns(2)
    min_price = col1.number_input("Minimum total price (EGP)", min_value=0, value=0, step=500_000)
    max_price = col2.number_input("Maximum total price (EGP)", min_value=0, value=20_000_000, step=500_000)
    chosen = st.multiselect("Must have ALL of these amenities", amenities())
    show_properties(PropertiesByAreaPriceAmenities(area, min_price, max_price, chosen))


def page_top_developers():
    st.header("Top 5 developers by resale listings")
    show(Top5Developers(), ["Developer", "Resale listings", "Avg price per m² (EGP)",
                            "Avg down payment (EGP)", "Avg gain over market (EGP)"])


def page_area_type_year():
    st.header("Properties by area, property type and contract year")
    col1, col2, col3 = st.columns(3)
    area = col1.selectbox("Area", areas())
    property_type = col2.selectbox("Property type", types())
    year = col3.number_input("Contract year", min_value=2000, max_value=2100, value=2024, step=1)
    show_properties(PropertiesByAreaTypeYear(area, property_type, int(year)))


def page_stats():
    st.header("Statistics by area and development project")
    rows = sorted(StatsByAreaAndProject(), key=lambda r: -r[5])     # most properties first
    show(rows, ["Area", "Project", "Developer", "Avg installment", "Avg down payment", "Properties",
                "Avg discount below market", "Avg contract age (years)", "Avg market price"])


PAGES = {
    "1 · Register a user": page_register,
    "2 · Add a review": page_add_review,
    "3 · View reviews": page_view_reviews,
    "4 · Top 10 projects": page_top_projects,
    "5 · Location of a development": page_location,
    "6 · Properties in an area": page_area,
    "7 · Search by price & amenities": page_search,
    "8 · Top 5 developers": page_top_developers,
    "9 · Area, type & contract year": page_area_type_year,
    "10 · Stats by area & project": page_stats,
}

st.sidebar.title("🏠 AqarExit Resale")
st.sidebar.caption("Resale properties in Egypt · data from aqarexit.com · hosted on Aiven MySQL")
PAGES[st.sidebar.radio("Choose", list(PAGES))]()

# app.py · command-line menu for the AqarExit resale database (runs against the Aiven cloud database)
import datetime
import sys

import pymysql

from queries import (register_user, addReview, get_reviews_by_project, top_10_Projects,
                     LocationOfDevelopment, PropertiesByArea, PropertiesByAreaPriceAmenities,
                     Top5Developers, PropertiesByAreaTypeYear, StatsByAreaAndProject,
                     list_areas, list_types, list_amenities, search_projects)

sys.stdout.reconfigure(encoding="utf-8")     # Arabic text on the Windows console

MAX_ROWS = 25          # rows printed per result; the full count is always shown


# ---------- small helpers for input and output ----------

def fmt(value):
    """Numbers with thousands separators and no decimals; None shown as '-'."""
    if value is None:
        return "-"
    if isinstance(value, (int, float)) or type(value).__name__ == "Decimal":
        if value != int(value) and abs(value) < 100:     # small averages, e.g. contract age 1.7 years
            return f"{value:,.1f}"
        return f"{value:,.0f}"
    return str(value)


def print_table(headers, rows):
    rows = list(rows)
    if not rows:
        print("  (no results)")
        return
    shown = [[fmt(v) for v in r] for r in rows[:MAX_ROWS]]
    widths = [min(max(len(str(h)), *(len(r[i]) for r in shown)), 40) for i, h in enumerate(headers)]
    print("  " + " | ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
    print("  " + "-+-".join("-" * w for w in widths))
    for r in shown:
        print("  " + " | ".join(v[:40].ljust(w) for v, w in zip(r, widths)))
    if len(rows) > MAX_ROWS:
        print(f"  ... showing {MAX_ROWS} of {len(rows)} rows")
    else:
        print(f"  {len(rows)} row(s)")


def ask_int(prompt, low=None, high=None):
    while True:
        text = input(prompt).strip().replace(",", "")
        try:
            value = int(text)
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if (low is not None and value < low) or (high is not None and value > high):
            print(f"  Please enter a number between {low} and {high}.")
            continue
        return value


def choose(prompt, options):
    """Show a numbered list and return the chosen option."""
    for i, option in enumerate(options, 1):
        print(f"  {i}) {option}")
    return options[ask_int(prompt, 1, len(options)) - 1]


def choose_many(prompt, options):
    """Numbered list; the user types several numbers separated by commas (or nothing for none)."""
    for i, option in enumerate(options, 1):
        print(f"  {i}) {option}")
    while True:
        text = input(prompt).strip()
        if not text:
            return []
        try:
            picks = [int(x) for x in text.split(",")]
            if all(1 <= p <= len(options) for p in picks):
                return [options[p - 1] for p in picks]
        except ValueError:
            pass
        print(f"  Type numbers between 1 and {len(options)} separated by commas, e.g. 1,3")


def choose_area():
    """195 areas are too many to list, so the user searches first."""
    areas = list_areas()
    while True:
        text = input("Area (type part of the name, e.g. زايد or التجمع): ").strip()
        matches = [a for a in areas if text.lower() in a.lower()]
        if matches:
            return choose("Choose the area number: ", matches[:20])
        print("  No area matches that, try again.")


def choose_project():
    """A project is its name AND its developer, so the user picks from a search result."""
    while True:
        text = input("Project name (type part of it, e.g. مدينتي or Badya): ").strip()
        projects = search_projects(text)
        if projects:
            labels = [f"{p} — {d} ({n} listings)" for p, d, n in projects]
            index = labels.index(choose("Choose the project number: ", labels))
            return projects[index][0], projects[index][1]
        print("  No project matches that, try again.")


# ---------- one function per menu option ----------

def option_register():
    email = input("Email: ").strip()
    username = input("Username: ").strip()
    gender = choose("Gender: ", ["Male", "Female"])
    while True:
        birthdate = input("Birth date (YYYY-MM-DD): ").strip()
        try:
            datetime.date.fromisoformat(birthdate)
            break
        except ValueError:
            print("  Please use the format YYYY-MM-DD, e.g. 2001-05-20.")
    phone = input("Phone number: ").strip()
    print("Main areas of focus (choose one or more):")
    areas = []
    while True:
        areas.append(choose_area())
        if input("Add another area? (y/n): ").strip().lower() != "y":
            break
    register_user(email, username, gender, birthdate, phone, areas)
    print(f"User {username} registered.")


def option_add_review():
    email = input("Your email (must be a registered user): ").strip()
    project, developer = choose_project()
    rating = ask_int("Rating (1-10): ", 1, 10)
    review = input("Your review: ").strip()
    addReview(email, project, developer, rating, review)
    print("Review added.")


def option_view_reviews():
    project, developer = choose_project()
    print_table(["User", "Rating", "Review"], get_reviews_by_project(project, developer))


def option_top_projects():
    property_type = choose("Property type number: ", list_types())
    order = choose("Rank by: ", ["inventory", "amount", "gain"])
    print_table(["Project", "Developer", "Listings", "Resale amount", "Avg gain"],
                top_10_Projects(property_type, order))


def option_location():
    project, developer = choose_project()
    print_table(["Location", "Unit type", "Avg price/m²", "Listings"],
                LocationOfDevelopment(project, developer))


def option_properties_in_area():
    properties, averages = PropertiesByArea(choose_area())
    print("\nAverage price per m² for each unit type:")
    print_table(["Unit type", "Avg price/m²"], averages)
    print("\nProperties:")
    print_table(["Unit code", "Type", "Size m²", "Total price"], properties)


def option_search():
    area = choose_area()
    min_price = ask_int("Minimum price (EGP): ", 0)
    max_price = ask_int("Maximum price (EGP): ", min_price)
    print("Amenities the property must have:")
    amenities = choose_many("Numbers separated by commas (Enter for none): ", list_amenities())
    rows = PropertiesByAreaPriceAmenities(area, min_price, max_price, amenities)
    # property columns: 0 UnitCode, 1 Type, 2 PropertySize, 5 BedRoomsNo, 6 BathsNo,
    #                   14 TotalPaid, 15 RemainingMoney, 24 ProjectName
    print_table(["Unit code", "Type", "Size m²", "Bedrooms", "Baths", "Total price", "Project"],
                [(r[0], r[1], r[2], r[5], r[6], r[14] + r[15], r[24]) for r in rows])


def option_top_developers():
    print_table(["Developer", "Listings", "Avg price/m²", "Avg down payment", "Avg gain"], Top5Developers())


def option_area_type_year():
    area = choose_area()
    property_type = choose("Property type number: ", list_types())
    year = ask_int("Contract year (e.g. 2024): ", 1990, 2100)
    rows = PropertiesByAreaTypeYear(area, property_type, year)
    print_table(["Unit code", "Size m²", "Bedrooms", "Baths", "Total price", "Project"],
                [(r[0], r[2], r[5], r[6], r[14] + r[15], r[24]) for r in rows])


def option_stats():
    print_table(["Area", "Project", "Developer", "Avg installment", "Avg down payment", "Properties",
                 "Avg discount", "Avg contract age", "Avg market price"],
                sorted(StatsByAreaAndProject(), key=lambda r: -r[5]))    # most properties first


MENU = [
    ("Register a user", option_register),
    ("Add a review on a project", option_add_review),
    ("View the reviews of a project", option_view_reviews),
    ("Top 10 projects for a property type", option_top_projects),
    ("Location of a development, with price/m² and listings per unit type", option_location),
    ("All properties in an area, with avg price/m² per unit type", option_properties_in_area),
    ("Search an area by price range and amenities", option_search),
    ("Top 5 developers", option_top_developers),
    ("Properties by area, property type and contract year", option_area_type_year),
    ("Statistics by area and development project", option_stats),
]


def menu():
    while True:
        print("\n===== AqarExit Resale Properties =====")
        for i, (title, _) in enumerate(MENU, 1):
            print(f"{i:2}) {title}")
        print(" 0) Exit")
        choice = ask_int("> ", 0, len(MENU))
        if choice == 0:
            break
        try:
            MENU[choice - 1][1]()
        except pymysql.err.IntegrityError as err:
            code = err.args[0]
            if code == 1062:                      # duplicate primary key
                print("Not saved: this already exists (email already registered, or you already reviewed this project).")
            elif code == 1452:                    # foreign key: the referenced row is missing
                print("Not saved: this email is not registered. Register first (option 1).")
            else:
                print("Not saved:", err.args[1])
        except pymysql.err.OperationalError as err:
            # CHECK constraints (gender, rating), lost connection, powered-off Aiven service, ...
            print("Database error:", err.args[1])


if __name__ == "__main__":
    menu()

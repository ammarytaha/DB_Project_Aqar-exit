from db import run


# 1) Register a user
def register_user(email, username, gender, birthdate, phone, focus_areas):
    run("""INSERT INTO users (Email, UserName, Gender, BirthDate, PhoneNo)
           VALUES (%s, %s, %s, %s, %s)""", (email, username, gender, birthdate, phone))

    # strip spaces, drop empty entries and repeats (a repeat would break the primary key)
    for area in dict.fromkeys(a.strip() for a in focus_areas if a.strip()):
        run("INSERT INTO user_focusarea (Email, FocusArea) VALUES (%s, %s)", (email, area))

# 2) Add a review on a project
def addReview(email, ProjectName, DeveloperName, rating, review_text):
    run("""INSERT INTO rate (UserEmail, ProjectName, DeveloperName, Rating, TextualReview)
           VALUES (%s, %s, %s, %s, %s)""", (email, ProjectName, DeveloperName, rating, review_text))

# 3) View the reviews of a project (a project is its name AND its developer)
def get_reviews_by_project(project_name, developer_name):
    return run("""SELECT UserEmail, Rating, TextualReview
                  FROM rate
                  WHERE ProjectName = %s AND DeveloperName = %s""", (project_name, developer_name))


# Lookups: the valid values the user can choose from in the app
def list_areas():
    # most listed areas first, so a search like "التجمع" shows التجمع الخامس before rare spellings
    return [r[0] for r in run("""SELECT AreaLocation FROM property
                                 GROUP BY AreaLocation ORDER BY COUNT(*) DESC""")]

def list_types():
    return [r[0] for r in run("SELECT DISTINCT Type FROM property ORDER BY Type")]

def list_amenities():
    return [r[0] for r in run("SELECT DISTINCT Amenity FROM property_amenities ORDER BY Amenity")]

def search_projects(text):
    """Projects whose name contains the text, most listed first (to help the user pick one)."""
    return run("""SELECT dp.ProjectName, dp.DeveloperName, COUNT(p.UnitCode) AS listings
                  FROM development_project dp
                  LEFT JOIN property p
                         ON p.ProjectName = dp.ProjectName AND p.DeveloperName = dp.DeveloperName
                  WHERE dp.ProjectName LIKE %s
                  GROUP BY dp.ProjectName, dp.DeveloperName
                  ORDER BY listings DESC
                  LIMIT 15""", ("%" + text + "%",))

# 4) Top 10 projects by resale inventory, resale amount, or gain over market value, for one property type
#    order_by: "inventory" (number of listings), "amount" (total cash paid by buyers),
#              "gain" (average market price minus total contract price)
TOP_PROJECTS_ORDER = {"inventory": "inventory", "amount": "resale_amount", "gain": "avg_gain"}

def top_10_Projects(property_type, order_by="inventory"):
    order_column = TOP_PROJECTS_ORDER[order_by]   # only these three names can reach the SQL
    sql = f"""SELECT P.ProjectName, P.DeveloperName,
                     COUNT(*)                                             AS inventory,
                     SUM(P.TotalPaid)                                     AS resale_amount,
                     AVG(P.CurrentMP - (P.TotalPaid + P.RemainingMoney)) AS avg_gain
              FROM property P
              WHERE P.Type = %s AND P.ProjectName IS NOT NULL
              GROUP BY P.ProjectName, P.DeveloperName
              ORDER BY {order_column} DESC
              LIMIT 10"""
    return run(sql, (property_type,))

# 5) Location of a development project, with the average price per m² and number of listings per unit type
def LocationOfDevelopment(project_name, developer_name):
    return run("""SELECT dp.Location, p.Type,
                         ROUND(AVG((p.TotalPaid + p.RemainingMoney) / p.PropertySize)) AS avg_price_per_sqm,
                         COUNT(p.UnitCode) AS listings
                  FROM development_project dp
                  INNER JOIN property p
                          ON dp.ProjectName = p.ProjectName AND dp.DeveloperName = p.DeveloperName
                  WHERE dp.ProjectName = %s AND dp.DeveloperName = %s
                  GROUP BY dp.Location, p.Type""", (project_name, developer_name))
# 6) All properties in an area, each with the average price per m² of its unit type in that area
def PropertiesByArea(area):
    # all the properties in the area
    properties = run("""SELECT UnitCode, Type, PropertySize, TotalPaid + RemainingMoney AS total_price
                        FROM property
                        WHERE AreaLocation = %s""", (area,))

    # the average price per m² of each unit type in the area
    averages = run("""SELECT Type, AVG((TotalPaid + RemainingMoney) / PropertySize) AS avg_price_per_sqm
                      FROM property
                      WHERE AreaLocation = %s
                      GROUP BY Type""", (area,))

    return properties, averages

# Show all the properties in a certain area in a given price range, with a given set of amenities
#    price = total price (TotalPaid + RemainingMoney); the property must have ALL the given amenities
def PropertiesByAreaPriceAmenities(area, min_price, max_price, amenities):
    amenities = list(dict.fromkeys(a.strip() for a in amenities if a.strip()))   # no blanks or repeats

    if not amenities:                     # no amenities chosen -> filter by area and price only
        return run("""SELECT *
                      FROM property
                      WHERE AreaLocation = %s
                        AND TotalPaid + RemainingMoney BETWEEN %s AND %s""",
                   (area, min_price, max_price))

    placeholders = ", ".join(["%s"] * len(amenities))      # one %s per amenity: "%s, %s, %s"
    return run(f"""SELECT p.*
                   FROM property p
                   INNER JOIN property_amenities a ON a.UnitCode = p.UnitCode
                   WHERE p.AreaLocation = %s
                     AND p.TotalPaid + p.RemainingMoney BETWEEN %s AND %s
                     AND a.Amenity IN ({placeholders})
                   GROUP BY p.UnitCode
                   HAVING COUNT(DISTINCT a.Amenity) = %s""",
               (area, min_price, max_price, *amenities, len(amenities)))
    
    
# 8) Top 5 developers by number of resale listings, with their average price per m²,
#    average required down payment (TotalPaid) and average gain over market value
def Top5Developers():
    return run("""SELECT DeveloperName,
                         COUNT(*)                                       AS resale_listings,
                         AVG((TotalPaid + RemainingMoney) / PropertySize) AS avg_price_per_sqm,
                         AVG(TotalPaid)                                 AS avg_down_payment,
                         AVG(CurrentMP - (TotalPaid + RemainingMoney))  AS avg_gain
                  FROM property
                  WHERE DeveloperName IS NOT NULL
                  GROUP BY DeveloperName
                  ORDER BY resale_listings DESC
                  LIMIT 5""")





# 9) All the properties in an area, of a property type, with a contract year
def PropertiesByAreaTypeYear(area, property_type, contract_year):
    return run("""SELECT *
                  FROM property
                  WHERE AreaLocation = %s AND Type = %s AND ContractYear = %s""",
               (area, property_type, contract_year))


# 10) For each area and development project: average installment, average down payment, number of properties,
#     average discount below market price, average age of the contract (years), and average market price
def StatsByAreaAndProject():
    return run("""SELECT AreaLocation, ProjectName, DeveloperName,
                         AVG(InstallmentAmount)                        AS avg_installment,
                         AVG(TotalPaid)                                AS avg_down_payment,
                         COUNT(*)                                      AS properties,
                         AVG(CurrentMP - (TotalPaid + RemainingMoney)) AS avg_discount,
                         AVG(YEAR(CURDATE()) - ContractYear)           AS avg_contract_age,
                         AVG(CurrentMP)                                AS avg_market_price
                  FROM property
                  WHERE ProjectName IS NOT NULL
                  GROUP BY AreaLocation, ProjectName, DeveloperName""")

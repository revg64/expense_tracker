from flask import Flask, render_template, request, redirect, session,flash
from datetime import date, datetime
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, SECRET_KEY
from models.db import db
from models.user import User
from models.expense import Expense
from models.budget import Budget
from sqlalchemy import func
from models.budget import Budget
from models.expense import Expense
from datetime import date
from dotenv import load_dotenv
load_dotenv()




app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config["SECRET_KEY"] = SECRET_KEY

db.init_app(app)

with app.app_context():
    db.create_all()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            session["user_id"] = user.id
            return redirect("/dashboard")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = User(
            email=request.form["email"],
            password=generate_password_hash(request.form["password"])
        )
        db.session.add(user)
        db.session.commit()
        return redirect("/")
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    today = date.today()
    month = int(request.args.get("month", today.month))
    year = int(request.args.get("year", today.year))

    start_date = date(year, month, 1)
    end_date = date(year + (month // 12), (month % 12) + 1, 1)

    expenses = Expense.query.filter(
        Expense.user_id == session["user_id"],
        Expense.date >= start_date,
        Expense.date < end_date
    ).order_by(Expense.date.desc()).limit(10).all()

    total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == session["user_id"],
        Expense.date >= start_date,
        Expense.date < end_date
    ).scalar() or 0
    category_totals = db.session.query(
        Expense.category,
        func.sum(Expense.amount)
    ).filter(
        Expense.user_id == session["user_id"],
        Expense.date >= start_date,
        Expense.date < end_date
    ).group_by(Expense.category).all()
    budgets = Budget.query.filter_by(
    user_id=session["user_id"]).all()


    budget_map = {b.category: b.amount for b in budgets}

    exceeded_categories = []

    for c, spent in category_totals:
        if c in budget_map and spent > budget_map[c]:
            exceeded_categories.append(c)

    return render_template(
        "dashboard.html",
        expenses=expenses,
        total=total,
        category_totals=category_totals,
        exceeded_categories=exceeded_categories,
        selected_month=month,
        selected_year=year
    )
@app.route("/all-expenses")
def all_expenses():
    if "user_id" not in session:
        return redirect("/")

    expenses = Expense.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Expense.date.desc()).all()

    return render_template(
        "all_expenses.html",
        expenses=expenses
    )


@app.route("/budget", methods=["GET", "POST"])
def budget():
    if "user_id" not in session:
        return redirect("/")

    categories = [
        "Food", "Travel", "Rent", "Shopping",
        "Entertainment", "Utilities", "Health", "Education"
    ]

    if request.method == "POST":
        action = request.form["action"]
        category = action.split("_", 1)[1]

        if action.startswith("set"):
            amount = float(request.form[f"amount_{category}"])

            budget = Budget.query.filter_by(
                user_id=session["user_id"],
                category=category
            ).first()

            if budget:
                budget.amount = amount
            else:
                budget = Budget(
                    user_id=session["user_id"],
                    category=category,
                    amount=amount
                )
                db.session.add(budget)

        if action.startswith("clear"):
            Budget.query.filter_by(
                user_id=session["user_id"],
                category=category
            ).delete()

        db.session.commit()

    existing = Budget.query.filter_by(
        user_id=session["user_id"]
    ).all()

    budgets = {b.category: b.amount for b in existing}

    return render_template(
        "budget.html",
        categories=categories,
        budgets=budgets
    )

@app.route("/add-expense", methods=["POST"])
def add_expense():
    if "user_id" not in session:
        return redirect("/")

    expense = Expense(
        amount=request.form["amount"],
        category=request.form["category"],
        description=request.form["description"],
        date=datetime.strptime(request.form["date"], "%Y-%m-%d"),
        user_id=session["user_id"]
    )

    db.session.add(expense)
    db.session.commit()

    flash("Expense added successfully")

    return redirect("/dashboard")

@app.route("/alerts")
def alerts():
    if "user_id" not in session:
        return redirect("/")

    budgets = Budget.query.filter_by(
        user_id=session["user_id"]
    ).all()

    budget_map = {b.category: b.amount for b in budgets}

    alerts = {}

    expenses = db.session.query(
        Expense.category,
        func.sum(Expense.amount),
        func.month(Expense.date),
        func.year(Expense.date)
    ).filter(
        Expense.user_id == session["user_id"]
    ).group_by(
        Expense.category,
        func.year(Expense.date),
        func.month(Expense.date)
    ).all()

    month_names = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

    for category, spent, month, year in expenses:
        if category in budget_map and spent > budget_map[category]:
            key = f"{month_names[month - 1]} {year}"

            if key not in alerts:
                alerts[key] = []

            alerts[key].append({
                "category": category,
                "budget": budget_map[category],
                "spent": spent
            })
    return render_template(
        "alerts.html",
        alerts=alerts
    )
@app.route("/statistics")
def statistics():
    if "user_id" not in session:
        return redirect("/")

    selected_month = request.args.get("month")
    selected_year = request.args.get("year")

    expenses = Expense.query.filter_by(
        user_id=session["user_id"]
    ).all()

    monthly_category = {}
    global_category_totals = {}
    monthly_totals = {}

    for e in expenses:
        key = (e.date.year, e.date.month)

        monthly_totals.setdefault(key, {})
        monthly_totals[key][e.category] = monthly_totals[key].get(e.category, 0) + e.amount

        global_category_totals[e.category] = global_category_totals.get(e.category, 0) + e.amount

    highest_spending = []
    for (year, month), categories in monthly_totals.items():
        cat = max(categories, key=categories.get)
        highest_spending.append({
            "month": month,
            "year": year,
            "category": cat,
            "amount": categories[cat]
        })

    chart_data = {}
    if selected_month and selected_year:
        for e in expenses:
            if e.date.month == int(selected_month) and e.date.year == int(selected_year):
                chart_data[e.category] = chart_data.get(e.category, 0) + e.amount

    return render_template(
        "statistics.html",
        highest_spending=highest_spending,
        global_category_totals=global_category_totals,
        chart_data=chart_data,
        selected_month=selected_month,
        selected_year=selected_year
    )



@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)

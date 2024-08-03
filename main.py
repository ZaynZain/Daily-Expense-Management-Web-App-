from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from models import db, User, Budget, Expense
from config import Config
from datetime import datetime
import io
import csv
from io import StringIO
from flask import make_response

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    current_month = datetime.now().strftime('%B')
    user_id = current_user.id
    print(f'Current User ID: {user_id}')
    print(f'Current Month: {current_month}')

    all_budgets = Budget.query.filter_by(user_id=user_id).all()
    print('All Budgets for User:')
    for budget in all_budgets:
        print(f'Month: {budget.month}, Amount: {budget.amount}')

    monthly_budget = Budget.query.filter_by(user_id=user_id).filter(Budget.month.ilike(current_month)).first()
    print(f'Monthly Budget: {monthly_budget}')

    daily_expenses = Expense.query.filter_by(user_id=user_id).all()
    total_expenses = sum(expense.amount for expense in daily_expenses)
    remaining_budget = (monthly_budget.amount - total_expenses) if monthly_budget else 0

    return render_template('dashboard.html', monthly_budget=monthly_budget, daily_expenses=daily_expenses,
                           total_expenses=total_expenses, remaining_budget=remaining_budget)


@app.route('/add_budget', methods=['GET', 'POST'])
@login_required
def add_budget():
    if request.method == 'POST':
        amount = request.form['amount']
        current_month = datetime.now().strftime('%B')
        existing_budget = Budget.query.filter_by(user_id=current_user.id, month=current_month).first()

        if existing_budget:
            flash('You have already set a budget for this month. You can only update it.', 'danger')
            return redirect(url_for('update_budget', message='You have already set a budget for this month. You can only update it.'))


        new_budget = Budget(amount=amount, month=current_month, user_id=current_user.id)
        db.session.add(new_budget)
        db.session.commit()
        flash('Monthly budget added!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_budget.html')

@app.route('/update_budget', methods=['GET', 'POST'])
@login_required
def update_budget():
    current_month = datetime.now().strftime('%B')
    monthly_budget = Budget.query.filter_by(user_id=current_user.id, month=current_month).first()

    if not monthly_budget:
        flash('No monthly budget set for the current month. Please add a budget first.', 'danger')
        return redirect(url_for('add_budget'))

    if request.method == 'POST':
        new_amount = request.form['amount']
        monthly_budget.amount = new_amount
        db.session.commit()
        flash('Monthly budget updated!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('update_budget.html', monthly_budget=monthly_budget)


@app.route('/add_expenses', methods=['GET', 'POST'])
@login_required
def add_expenses():
    if request.method == 'POST':
        category = request.form['category']
        amount = request.form['amount']
        date = request.form['date']
        new_expense = Expense(category=category, amount=amount, date=date, user_id=current_user.id)
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense added!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_expenses.html')


@app.route('/monthly_report')
@login_required
def monthly_report():
    current_month = datetime.now().strftime('%B')  # Get the current month as a string
    current_year = datetime.now().year
    user_id = current_user.id

    print(f'Current User ID: {user_id}')
    print(f'Current Month: {current_month}')
    print(f'Current Year: {current_year}')

    # Filter expenses by date range for the current month
    monthly_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        extract('month', Expense.date) == datetime.now().month,
        extract('year', Expense.date) == current_year
    ).all()

    total_expenses = sum(expense.amount for expense in monthly_expenses)
    current_date = datetime.now()

    print(f'The monthly expenses are: {monthly_expenses}')  # Debugging line

    # Fetch the monthly budget for the current month
    monthly_budget = Budget.query.filter_by(user_id=user_id, month=current_month).first()
    total_budget = monthly_budget.amount if monthly_budget else 0

    # Calculate remaining balance
    remaining_balance = total_budget - total_expenses

    print(f'Total budget for the month: {total_budget}')
    print(f'Remaining balance: {remaining_balance}')

    return render_template('monthly_report.html',
                           monthly_expenses=monthly_expenses,
                           total_expenses=total_expenses,
                           total_budget=total_budget,
                           remaining_balance=remaining_balance,
                           current_date=current_date)


@app.route('/download_report')
@login_required
def download_report():
    current_month = datetime.now().month
    current_year = datetime.now().year
    user_id = current_user.id

    # Filter expenses by date range for the current month
    monthly_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).all()

    # Create CSV file
    csv_data = [['Category', 'Amount', 'Date']]
    for expense in monthly_expenses:
        csv_data.append([expense.category, expense.amount, expense.date.strftime('%Y-%m-%d')])

    # Generate CSV response
    def generate():
        data = csv_data
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerows(data)
        return si.getvalue()

    output = make_response(generate())
    output.headers["Content-Disposition"] = "attachment; filename=monthly_report.csv"
    output.headers["Content-type"] = "text/csv"
    return output
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

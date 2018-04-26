from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

''' -------------- index --------------'''
@app.route("/")
@login_required
def index():

    #(total shares + cash)
    grand_total = 0
    portfolio_stocks = db.execute("SELECT shares, symbol FROM portfolio WHERE id=:id",\
    id=session["user_id"])

    # iterate over each stock
    for portfolio_stock in portfolio_stocks:
        stock = lookup(portfolio_stock["symbol"])

        portfolio_stock_total = portfolio_stock["shares"] * stock["price"]
        grand_total += portfolio_stock_total

        db.execute("UPDATE portfolio SET total=:total, price=:price WHERE id=:id AND symbol=:symbol",\
        total=portfolio_stock_total, price=stock["price"], id=session["user_id"], symbol=stock["symbol"])

    user_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    grand_total += user_cash[0]["cash"]

    portfolio_index = db.execute("SELECT * FROM portfolio WHERE id=:id", id=session["user_id"])

    return render_template("index.html", user_cash=user_cash[0]["cash"], grand_total=grand_total, stocks=portfolio_index)

''' -------------- buy --------------'''
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        buy_request = request.form.get("buy")
        buy_stock = lookup(buy_request)

        if not buy_stock:
            return apology("stock does not exist")

        # checks if shares is an not negative integer
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("cannot accept negative numbers")
        except:
            return apology("must input a number")

        # select user cash
        user_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        user_cash = user_cash[0]["cash"]

        # check if user cash is less than price cash
        if user_cash < buy_stock["price"] * shares:
            return apology("you cannot afford this stock at this price")

        # since user can buy, db is updated
        user_cash -= float(shares) * float(buy_stock["price"])
        db.execute("UPDATE users SET cash = :user_cash WHERE id=:id", user_cash=user_cash, id=session["user_id"])

        # insert transaction into history aswell
        db.execute("INSERT INTO history (name, symbol, price, shares, total, action, id) VALUES(:name, :symbol, :price, :shares, :total, :action, :id)",\
        name=buy_stock["name"], symbol=buy_stock["symbol"], price=buy_stock["price"], \
        shares=shares, total=buy_stock["price"]*shares, action="bought", id=session["user_id"])

        # select shares value of user
        portfolio_shares = db.execute("SELECT shares FROM portfolio WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=buy_stock["symbol"])

        # check if there are existing shares for the user in the company
        if not portfolio_shares:
            # insert into databaase the transaction
            db.execute("INSERT into portfolio (price, name, symbol, id, total, shares) VALUES(:price, :name,:symbol, :id, :total, :shares)", \
            price=buy_stock["price"], name=buy_stock["name"], symbol=buy_stock["symbol"], id=session["id"], total=buy_stock*shares, shares=shares)
        else:
            db.execute("UPDATE portfolio SET shares=:shares WHERE id=:id AND symbol=:symbol", shares=portfolio_shares[0]["shares"] + shares, id=session["user_id"], symbol=buy_stock["symbol"])

        return redirect(url_for("index"))

    else:
        return render_template("buy.html")

''' -------------- history --------------'''
@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    history = db.execute("SELECT * FROM history WHERE id=:id", id=session["user_id"])
    return render_template("history.html", values=history)
''' -------------- log in --------------'''
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

''' -------------- logout --------------'''
@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

''' -------------- quote --------------'''
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        symbol = request.form.get("quote")
        quote_stock = lookup(symbol)

        if not quote_stock:
            return apology("symbol does not exit")

        quote_stock_name = quote_stock["name"]
        quote_stock_symbol = quote_stock["symbol"]
        quote_stock_price = quote_stock["price"]

        return render_template("quoted.html", name=quote_stock_name, symbol=quote_stock_symbol, price=quote_stock_price)

    else:
        return render_template("quote.html")


''' --------------register --------------'''
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")


        # ensure username was submitted
        if not username:
            return apology("must provide username")

        # ensure password was submitted
        elif not password:
            return apology("must provide password")

        # ensure password was submitted
        elif not request.form.get("resubmit_password"):
            return apology("must provide password again")

        # checks if passwords match
        if password != request.form.get("resubmit_password"):
            return apology("passwords do not match")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # inserts the username and passwords into database
        if not rows:
            db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=username, hash=pwd_context.hash(password))
        else:
            return apology("user already exists")

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

''' -------------- sell --------------'''
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    if request.method == "POST":

        sell_stock = lookup(request.form.get("sell"))

        if not sell_stock:
            return apology("no stock with that name")

        # check if share input is valid
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("must give an postive number")
        except:
            return apology("give a number")

        # if valid input is given (stock in portfolio 0<share<max_shares)
        # select shares from portfolio
        user_shares = db.execute("SELECT shares FROM portfolio WHERE id=:id AND symbol=:symbol",\
        id=session["user_id"], symbol=sell_stock["symbol"])

        if not user_shares or int(user_shares[0]["shares"])<shares:
            return apology("you do not have eought shares to sell")

        # put the transaction into history
        db.execute("INSERT INTO history (name, symbol, price, shares, total, action, id) VALUES(:name, :symbol, :price, :shares, :total, :action, :id)",\
        name=sell_stock["name"], symbol=sell_stock["symbol"], price=sell_stock["price"], \
        shares=shares, total=sell_stock["price"]*shares, action="sold", id=session["user_id"])

        # update the cash
        db.execute("UPDATE users SET cash=cash+:total WHERE id=:id", total=float(shares)*sell_stock["price"], id=session["user_id"])

        # if shares is zero then remove it from portfolio
        if int(user_shares[0]["shares"])-shares == 0: #(not shares)
            db.execute("DELETE FROM portfolio WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=sell_stock["symbol"])
        else:
            # udate the shares
            db.execute("UPDATE portfolio SET shares=shares-:shares WHERE id=:id", shares=shares, id=session["user_id"])

        return redirect(url_for("index"))
    else:
        return render_template("sell.html")

''' -------------- TODO --------------
1. change password feature (DONE)
2. add more cash to account
3. buy/sell at the index
4. others.

'''

@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    ''' change passwords '''

    if request.method == "POST":
        current_p = request.form.get("current_password")
        new_p = request.form.get("new_password")
        #reenter_new_p = request.form.get("reenter_new_password")

        if not current_p:
            return apology("enter current password")
        if not new_p:
            return apology("enter new password")

        user = db.execute("SELECT hash FROM users WHERE id=:id", id=session["user_id"])

        if not pwd_context.verify(current_p, user[0]["hash"]):
            return apology("invalid password")

        else:
            db.execute("UPDATE users SET hash =:new_hash WHERE id=:id", new_hash=pwd_context.hash(new_p), id=session["user_id"])

        return redirect(url_for("index"))

    else:
        return render_template("change.html")


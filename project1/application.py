import os
import re
import requests
import json

from flask import Flask, session, render_template, request, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import urljoin
from helpers import login_required, apology, display_rating


app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "GET":
        return render_template("index.html")
    else:
        if not request.form.get("book"):
            return apology("Please enter the isbn, author or title", 403)
        book = request.form.get("book")
        book = book.upper()
        book = "%" + book + "%"
        book_proxy = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn OR UPPER(title) LIKE :title OR UPPER(author) LIKE :author",
                                {"isbn":book, "title":book, "author":book})
        rows = book_proxy.fetchall()
        if len(rows) == 0:
            return apology("No results found", 403)
        return render_template("results.html", rows=rows)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register User"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username", 403)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("Must provide password", 403)

        #Ensure password confirmation was submitted
        if not request.form.get("confirmation"):
            return apology("Passwords must match", 403)

        # Ensure username is available
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username":username})
        num_rows = rows.fetchall()
        if len(num_rows) != 0:
            return apology("Username is taken", 403)
        pw = request.form.get("password")
        conf =  request.form.get("confirmation")

        # Ensure passwords match
        if pw != conf:
            return apology("Passwords must match", 403)

        # Ensure password length is 6-12 characters
        if len(pw) < 6 or len(pw) > 12:
            return apology("Password must be between 6-12 characters and include a number and special character", 403)
        no_count = 0
        sc_count = 0

        # Ensure password contains at least 1 number
        for i in pw:
            if i.isdigit() == True:
                no_count = no_count + 1
        if no_count == 0:
            return apology("Password must be between 6-12 characters and include a number and special character", 403)

        # Ensure password contains at least 1 special character
        regex = re.compile('[@_!#$%^&*()<>?/\|}{~:]')
        if (regex.search(pw) == None):
            return apology("Password must be between 6-12 characters and include a number and special character", 403)

        # Insert user, hash into users table
        pw_hash = generate_password_hash(pw)
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", {"username":username, "hash":pw_hash})
        db.commit()
        return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    
    session.clear()

    if request.method == "GET":
        return render_template("login.html")
    else:
        if not request.form.get("username"):
            return apology("Please enter your username", 403)
        if not request.form.get("password"):
            return apology("Please enter your password", 403)
        
        username = request.form.get("username")
        pw = request.form.get("password")

        row_proxy = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username":username})
        rows = row_proxy.fetchall()
        if len(rows) != 1:
            return apology("Invalid username", 403)
        if not check_password_hash(rows[0]["hash"], pw):
            return apology("Incorrect password", 403)
        
        session["username"] = rows[0]["username"]

        return render_template("index.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/results")
@login_required
def results():
    if request.method == "GET":
        return render_template("results.html")
    

@app.route("/book/<isbn>", methods=["GET", "POST"])
@login_required
def book(isbn):
    if request.method == "GET":
        info = db.execute("SELECT * FROM books WHERE isbn = :isbn",{"isbn":isbn}).fetchall()
        if len(info) == 0:
            return apology("No data exists for that ISBN", 403)
        api_key = "a2hG6Rxa46GnDH2OqewwQ"
        response = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": api_key, "isbns": isbn})
        goodreads = json.loads(response.text)
        gr_dict = goodreads["books"]
        avg_rating = gr_dict[0]["average_rating"]
        rating_count = gr_dict[0]["work_ratings_count"]
        try:
            reviews = db.execute("SELECT user_review FROM reviews WHERE isbn = :isbn", {"isbn":isbn}).fetchall()
            rtg = db.execute("SELECT AVG(rating) FROM reviews WHERE isbn = :isbn", {"isbn":isbn}).fetchone()
            for row in rtg:
                rating = display_rating(row)
            return render_template("book.html", isbn = isbn, title = info[0]["title"], author = info[0]["author"], year = info[0]["year"], 
                                    avg_rating = avg_rating, rating_count = rating_count, rating = rating, reviews = reviews)
        except:
            rating = "No Ratings Yet"
            return render_template("book.html", isbn = isbn, title = info[0]["title"], author = info[0]["author"], year = info[0]["year"], 
                                    avg_rating = avg_rating, rating_count = rating_count, rating = rating)

    if request.method == "POST":
        if not request.form.get("rating"):
            return apology("Please select a rating from the dropdown menu")
        if not request.form.get("review"):
            return apology("Reviews cannot be blank")
        rating = request.form.get("rating")
        review = request.form.get("review")
        username = session["username"]
        check_review = db.execute("SELECT * FROM reviews WHERE username = :username AND isbn = :isbn", {"username":username, "isbn":isbn}).fetchall()
        if len(check_review) != 0:
            return apology("only 1 review is permitted per user", 403)
        db.execute("INSERT INTO reviews (username, isbn, user_review, rating) VALUES (:username, :isbn, :user_review, :rating)",
                    {"username":username, "isbn":isbn, "user_review":review, "rating":rating})
        db.commit()
        reviews = db.execute("SELECT user_review FROM reviews WHERE isbn = :isbn", {"isbn":isbn}).fetchall()
        rtg = db.execute("SELECT AVG(rating) FROM reviews WHERE isbn = :isbn", {"isbn":isbn}).fetchone()
        for row in rtg:
            rating = display_rating(row)        
        info = db.execute("SELECT * FROM books WHERE isbn = :isbn",{"isbn":isbn}).fetchall()
        api_key = "a2hG6Rxa46GnDH2OqewwQ"
        response = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": api_key, "isbns": isbn})
        goodreads = json.loads(response.text)
        gr_dict = goodreads["books"]
        avg_rating = gr_dict[0]["average_rating"]
        rating_count = gr_dict[0]["work_ratings_count"]
        return render_template("book.html", isbn = isbn, title = info[0]["title"], author = info[0]["author"], year = info[0]["year"], 
                                    avg_rating = avg_rating, rating_count = rating_count, rating = rating, reviews = reviews)

@app.route("/api/<isbn>")
def api(isbn):
    info = db.execute("SELECT * FROM books WHERE isbn = :isbn",{"isbn":isbn}).fetchall()
    if len(info) == 0:
        return apology("No data exists for that ISBN", 403)
    try:
        rvw = db.execute("SELECT COUNT(user_review) FROM reviews WHERE isbn = :isbn", {"isbn":isbn}).fetchone()
        rtg = db.execute("SELECT AVG(rating) FROM reviews WHERE isbn = :isbn", {"isbn":isbn}).fetchone()
        for row in rtg:
            rating = display_rating(row)
        for row in rvw:
            num_reviews = row
        return jsonify({"isbn":isbn,
                        "title": info[0]["title"],
                        "author": info[0]["author"],
                        "year": info[0]["year"],
                        "rating": rating,
                        "num_reviews": num_reviews})
    except:
        rating = "N/A"
        num_reviews = "0"
        return jsonify({"isbn":isbn,
                        "title": info[0]["title"],
                        "author": info[0]["author"],
                        "year": info[0]["year"],
                        "rating": rating,
                        "num_reviews": num_reviews})

@app.route("/api_documentation")
def api_documentation():
    return render_template("api_documentation.html")

import csv
from flask import Flask
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine("postgres://swruhupcbgjuiq:f1cc1b8bff37b3af6142abc5817ab7899f899c91962dd543b538c802fc148274@ec2-18-235-20-228.compute-1.amazonaws.com:5432/d62cpi8aqhsbct")
db = scoped_session(sessionmaker(bind=engine))
books = db.execute("SELECT * FROM books")
for book in books:
    print(f"{book}")

f = open("books.csv")
reader = csv.DictReader(f)
for row in reader:
    isbn = row["isbn"]
    title = row["title"]
    author = row["author"]
    year = row["year"]
    db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
                {"isbn":isbn, "title":title, "author":author, "year":year})
db.commit()
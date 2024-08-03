import os

class Config:
    SECRET_KEY = 'mysecretkey'
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:@localhost/budgetbuddy'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

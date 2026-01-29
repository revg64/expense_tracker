import os

SQLALCHEMY_DATABASE_URI = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:@localhost:3306/expense_manager"
)

SQLALCHEMY_TRACK_MODIFICATIONS = False

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

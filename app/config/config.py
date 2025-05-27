import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:Atomic123!@localhost/2ncodes'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey123')  # ✅ Used for JWT
    JWT_SECRET_KEY = SECRET_KEY  # ✅ Add JWT Secret Key

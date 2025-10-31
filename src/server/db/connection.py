from sqlalchemy import create_engine 
from dotenv import load_dotenv
import os

load_dotenv()

# this is the database connection manager, provided by sqlalchemy. It handles connection-related plumbing for us. 
engine = create_engine(os.getenv("DATABASE_URL"))
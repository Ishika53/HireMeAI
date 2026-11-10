import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

mongodb_url = os.getenv("MONGODB_URL")

client = MongoClient(
    mongodb_url,
    serverSelectionTimeoutMS=5000
)

client.admin.command("ping")

print("MongoDB connected successfully!")
from pymongo import MongoClient

uri = ""
client = MongoClient(uri)

try:
    client.admin.command("ping")
    print("✅ MongoDB connection successful!")
except Exception as e:
    print("❌ Connection failed:", e)

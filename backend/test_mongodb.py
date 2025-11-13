from pymongo import MongoClient

uri = "mongodb+srv://harshitbansal184507_db_user:F4yYlwsc9ZgjsQyx@cluster0.db7c0j5.mongodb.net/?appName=Cluster0"
client = MongoClient(uri)

try:
    client.admin.command("ping")
    print("✅ MongoDB connection successful!")
except Exception as e:
    print("❌ Connection failed:", e)

from typing import Dict, Optional
from enum import Enum
from ibm_watsonx_orchestrate.agent_builder.tools import tool
from pymongo import MongoClient
import os

# Use MongoDB Atlas instead of local MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://khushboo110597_db_user:iYHpCXn8bTSZYEFT@onboardingassistant.ijmnyjp.mongodb.net/?tlsAllowInvalidCertificates=true")

# Connect with a timeout
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)

# Use a database in MongoDB Atlas
db = client["buddy_db"]


@tool
def buddy(buddy_name: str,  buddy_email:str, team_name: str) -> dict:
    """
    Tool for buddies to collection information for buddy, buddy email team name and their onboarding plan teamwise.
    
    Args:
        buddy_name: Name of the buddy
        buddy_email: Email of the buddy
        team_name: Name of the team
    Returns:
        A dict having template as key and value as a url of that template
    """
    try:
        insert_team_data(team_name, buddy_name, buddy_email)
        msg = "Successfully stored buddy information in MongoDB"
    except Exception as e:
        msg = f"Warning: Could not store data in MongoDB: {e}"
        # Continue even if MongoDB storage fails
    
    return {"template": "https://onboarding-template-bucket.s3.us-west.cloud-object-storage.test.appdomain.cloud/onboarding-template.xlsx",
            "status" : msg}

def insert_team_data(team_name, buddy_name, buddy_email):
    collection = db["team_data"]
    team_data = {
        "team_name": team_name,
        "buddy_name": buddy_name,
        "buddy_email": buddy_email,
    }
    result = collection.insert_one(team_data)
    print(f"Data inserted with ID: {result.inserted_id}")

        


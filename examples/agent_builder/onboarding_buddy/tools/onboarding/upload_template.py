from typing import Dict, Optional
from enum import Enum
from ibm_watsonx_orchestrate.agent_builder.tools import tool
from pymongo import MongoClient
import os
import requests

# MongoDB connection
API_KEY="C3ePfiQHqD_PbHuo6rHivG1fDa_AgOcqMdmzHOawUyi1"
BUCKET_NAME="hacker-01"
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://khushboo110597_db_user:iYHpCXn8bTSZYEFT@onboardingassistant.ijmnyjp.mongodb.net/?tlsAllowInvalidCertificates=true")

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)

# Use a database in MongoDB Atlas
db = client["buddy_db"]

@tool
def upload_template(team_name: str, onboarding_template) -> dict:
    """
    Tool for buddies to upload the onboarding template of their respective team.
    
    Args:
        team_name: Name of the team for which you want to upload template.
        onboarding_template: Content of the onboarding template (can be string or bytes).
    Returns:
        A dict having status as key and value as a message
    """
    # Check if onboarding_template is a string and convert to bytes if needed
    if isinstance(onboarding_template, str):
        try:
            # Try to convert string to bytes
            onboarding_template = onboarding_template.encode('utf-8')
        except Exception as e:
            return {
                "status": "error",
                "error": "Failed to convert string to bytes",
                "message": f"Encoding error: {str(e)}",
                "error_code": "ENCODING_ERROR"
            }
    
    # Ensure we have bytes
    if not isinstance(onboarding_template, bytes):
        return {
            "status": "error",
            "error": "Invalid data type",
            "message": f"Expected bytes, got {type(onboarding_template).__name__}",
            "error_code": "TYPE_ERROR"
        }
    
    url, msg = upload_to_ibm_cos(team_name, onboarding_template)
    
    # Update the template URL in the database
    if url:
        try:
            update_result = update_template_in_db(team_name, url)
            if update_result:
                msg += f". Template URL updated in database for team {team_name}"
        except Exception as e:
            msg += f". Warning: Could not update template URL in database: {str(e)}"
    
    return {"status": msg}


def get_ibm_iam_access_token() -> str:
    url = "https://iam.test.cloud.ibm.com/oidc/token"
    payload = {
        "apikey": API_KEY,
        "response_type": "cloud_iam",
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey"
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        raise Exception(f"Failed to obtain access token: {response.status_code} {response.text}")


def upload_to_ibm_cos(file_name,data):
    access_token = get_ibm_iam_access_token()
    content_type = "text/plain"
    url = f"https://s3.us-west.cloud-object-storage.test.appdomain.cloud/{BUCKET_NAME}/{file_name}"
    headers = {
        "Content-Type": content_type,
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.put(url, data=data, headers=headers)

    if response.status_code in (200, 201):
        return url, "Congratulation you have successfully onboarded to the onboarding assistant"
    else:
        # Return a tuple with None for URL and error message for consistency
        return None, f"Upload failed: {response.status_code}\n{response.text}"
        
def update_template_in_db(team_name, template_url):
    """
    Update the template_url field in the team_data collection for the specified team.
    
    Args:
        team_name: Name of the team to update
        template_url: Template URL to add to the document
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        collection = db["team_data"]
        
        # Find the document for the specified team
        query = {"team_name": team_name}
        
        # Update the document with the template_url field
        # Using upsert=True to create the document if it doesn't exist
        update_result = collection.update_one(
            query,
            {"$set": {"template_url": template_url}},
            upsert=True
        )
        return update_result.acknowledged
    except Exception as e:
        # Return False if there was an error
        return False

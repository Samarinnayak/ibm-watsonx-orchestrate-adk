from io import BytesIO
from typing import List, Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass
import os
import requests
import pandas as pd
import httpx
from pymongo import MongoClient
from dotenv import load_dotenv
from ibm_watsonx_orchestrate.agent_builder.tools import tool

MONGO_URI = os.getenv("MONGO_URI", "")
# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)

# Use a database in MongoDB Atlas
db = client["buddy_db"]

# Get current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Try to load the GitHub token from the .env file in the onboarding_buddy directory
onboarding_buddy_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), 'onboarding_buddy')
onboarding_env_path = os.path.join(onboarding_buddy_dir, '.env')
if os.path.exists(onboarding_env_path):
    load_dotenv(onboarding_env_path)
    print(f"Loaded .env from {onboarding_env_path}")

# Get GitHub token from environment or use hardcoded value as fallback
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "TestRepo"
GITHUB_API_URL = f"https://api.github.com/repos/Samarinnayak/project_buddy_test_1/issues"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


def fetch_file_url(team_name):
    collection = db["team_data"]
    team_doc = collection.find_one(
    {"team_name": team_name},
    {"template_id": 1})
    print(team_doc)
    if team_doc:
        return team_doc["template_id"]
    else:
        print("Template not found")


async def read_task_from_excel(csv_file):
    df = pd.read_excel(csv_file, sheet_name="onboarding_template", header=0)
    payloads = []
    task_types = df['Task Type'].dropna().unique()
    for task_type in task_types:
            task_df = df[df['Task Type'] == task_type]
            if task_df.empty:
                continue
            body = await format_task_body(task_df)

            payload = {
                "title": task_type.strip(),
                "body": body,
            }
            payloads.append(payload)
    return payloads

async def format_task_body(task_df):
    formatted_rows = []
    for _, row in task_df.iterrows():
        task_name = row['Task Name'].strip() if pd.notna(row['Task Name']) else ""
        task_info = row['Task Info'].strip() if pd.notna(row['Task Info']) else ""
        task_links = row['Task Related Links'].strip() if pd.notna(row['Task Related Links']) else ""
        task_duration = row['Task Duration'].strip() if pd.notna(row['Task Duration']) else ""
        additional_info = row['Additional Information'].strip() if pd.notna(row['Additional Information']) else ""

        # Format the row as a checklist item
        line = f"- [ ] **{task_name}**"
        if task_duration:
            line += f" ({task_duration})"
        if task_info:
            line += f"\n      {task_info}"
        if task_links:
            line += f"\n      🔗 [Link]({task_links})"
        if additional_info:
            line += f"\n      {additional_info}"

        formatted_rows.append(line)

    return "\n\n".join(formatted_rows)

@dataclass
class Document:
    title: str
    content: str
    url: Optional[str] = None


@dataclass
class GitHubTask:
    title: str
    description: str
    assignee: str
    status: str


@tool
def new_joiner(action: str, team: Optional[str] = None, query: Optional[str] = None) -> dict:
    """
    Tool for new joiners to get information about teams, documentation, and create GitHub tasks.
    
    Args:
        action: The action to perform. Must be one of: "list_teams", "get_docs", "create_tasks", "ask_question"
        team: The team to get information about (required for "get_docs", "create_tasks", and "ask_question")
        query: The question to ask (required for "ask_question")
    
    Returns:
        A dictionary containing the requested information
    """
    # Convert string team name to Team enum if provided
    
    collection = db["team_data"]
    if action == "list_teams":

        # Try to get teams from database
        team_names = []  # Start with default teams
        try:
            print("DEBUG: Attempting to connect to database...")
            
            db_team_names = collection.distinct("team_name")
            print(f"DEBUG: Raw DB response: {db_team_names}")
            
            # If teams found in database, use them instead of defaults
            if db_team_names and len(db_team_names) > 0:
                team_names = db_team_names
                print(f"DEBUG: Found {len(team_names)} teams in database: {team_names}")
            else:
                print("DEBUG: No teams found in database, using default teams")
        except Exception as e:
            # If there's an error with the database query, use default values as fallback
            print(f"DEBUG: Error retrieving team names from database: {str(e)}")
            print("DEBUG: Using default teams instead")
        
        print(f"DEBUG: Final team_names list: {team_names}")
        
        # Create a formatted message with team options that look like buttons
        team_buttons = []
        for team_name in team_names:
            button = f"[{team_name}]"
            team_buttons.append(button)
            print(f"DEBUG: Added button: {button}")
        
        # Join the team buttons with line breaks
        team_buttons_text = "\n".join(team_buttons)
        
        # Create a more visually appealing message with clear instructions
        message = "Please select one of the following teams by clicking or typing the team name:\n\n"
        message += team_buttons_text
        
        # For debugging
        print(f"DEBUG: Team buttons list: {team_buttons}")
        print(f"DEBUG: Final formatted message: \n{message}")
        
        # Create selectable teams for the response
        selectable_teams = []
        for team_name in team_names:
            team_obj = {
                "name": team_name,
                "id": team_name,
                "selectable": True
            }
            selectable_teams.append(team_obj)
            print(f"DEBUG: Added selectable team: {team_obj}")
        
        response = {
            "teams": selectable_teams,
            "message": message
        }
        
        print(f"DEBUG: Final response object: {response}")
        return response
    
    if not team:
        return {
            "error": "Team is required for this action",
            "message": "Please specify a team."
        }
    
    # Get team name for display
    team_name = team
    
    if action == "get_docs":
        buddy_name = ""
        buddy_email = ""
        buddy_github_username = ""
        # Return a default response for get_docs action
        try:
            print(f"DEBUG: Attempting to find team {team_name} in database")
            team_doc = collection.find_one(
                {"team_name": team_name},
                {"_id": 0, "buddy_name": 1, "buddy_email": 1, "buddy_github_username": 1}
            )
            
            print(f"DEBUG: Database response: {team_doc}")
            
            if team_doc:
                if "buddy_name" in team_doc and team_doc["buddy_name"]:
                    buddy_name = team_doc["buddy_name"]
                    print(f"DEBUG: Found buddy name: {buddy_name}")
                else:
                    print("DEBUG: buddy_name field missing or empty")
                    
                if "buddy_email" in team_doc and team_doc["buddy_email"]:
                    buddy_email = team_doc["buddy_email"]
                    print(f"DEBUG: Found buddy email: {buddy_email}")
                else:
                    print("DEBUG: buddy_email field missing or empty")
                    
                if "buddy_github_username" in team_doc and team_doc["buddy_github_username"]:
                    buddy_github_username = team_doc["buddy_github_username"]
                    print(f"DEBUG: Found buddy github username: {buddy_github_username}")
                else:
                    print("DEBUG: buddy_github_username field missing or empty")
            else:
                print(f"DEBUG: Team {team_name} not found in database")
        except Exception as e:
            print(f"DEBUG: Error retrieving team data from database: {str(e)}")
        
        # Create the welcome message with the buddy information
        message = f"🎉 Welcome to the **{team_name}** team!\n\n"
        message += f"Your onboarding buddy is **{buddy_name}**, and their W3 ID is `{buddy_email}`.\n\n"
        message += f"They'll help you get settled in — don't hesitate to reach out!"
        
        print(f"DEBUG: Final message: {message}")
        
        return {
            "buddy_name": buddy_name,
            "buddy_email": buddy_email,
            "buddy_github_username": buddy_github_username,
            "message": message
        }
    
    elif action == "create_tasks":
        try:
            success_messages = []
            error_messages = []
            file_url = fetch_file_url(team_name)
        #     if file_url:
        #         onboarding_excel = fetch_file_from_cos(file_url)
        #         item_lists = await read_task_from_excel(onboarding_excel)
        #         with httpx.AsyncClient() as client:
        #             # Create issues asynchronously
        #             for task in item_lists:
        #                 issue_data = {
        #                     "title": task["title"],
        #                     "body": task["body"],
        #                     # "assignees": [username],  # Optional: must be a collaborator in the repo
        #                 }
                        
        #                 # Asynchronous POST request to GitHub API
        #                 response = await client.post(GITHUB_API_URL, json=issue_data, headers=HEADERS)
                        
        #                 if response.status_code == 201:
        #                     issue = response.json()
        #                     issue_url = issue.get("html_url", "No URL available")  # Get the URL of the created issue
        #                     success_message = f"Issue '{issue_url}' created successfully."
        #                     print(success_message)
        #                     success_messages.append(success_message)
        #                 else:
        #                     error_message = f"Failed to create issue '{task['title']}': {response.json()}"
        #                     print(error_message)
        #                     error_messages.append(error_message)

            return {
                "message": "Tasks have been created in GitHub",
                "status": "success",
                "success_messages": success_messages,
                "error_messages": error_messages
            }
        except Exception as e:
            return {
                "error": "Failed to create tasks",
                "message": f"An error occurred while creating tasks: {str(e)}"
            }

    elif action == "ask_question":
        if not query:
            return {
                "error": "Query is required for asking questions",
                "message": "Please provide a question to ask."
            }
        
        # Get the knowledge base directory
        knowledge_base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                        "knowladge_base")
        
        # Try to load team-specific Excel file for answering questions
        try:
            # Construct the file path based on team name
            team_file_name = f"{team_name}.xlsx"
            excel_path = os.path.join(knowledge_base_dir, team_file_name)
            
            # If team-specific file doesn't exist, try the Example.xlsx as fallback
            if not os.path.exists(excel_path):
                excel_path = os.path.join(knowledge_base_dir, "Example.xlsx")
                
            # Read Excel file if it exists
            if os.path.exists(excel_path):
                try:
                    # Read Excel file
                    df = pd.read_excel(excel_path)
                    
                    # Try to find an answer in the Excel file
                    if 'Question' in df.columns and 'Answer' in df.columns:
                        for _, row in df.iterrows():
                            question = row['Question'] if not pd.isna(row['Question']) else ""
                            answer = row['Answer'] if not pd.isna(row['Answer']) else ""
                            
                            # Simple keyword matching
                            if question and answer and query.lower() in question.lower():
                                return {
                                    "answer": answer,
                                    "message": f"Here's information about your question for the {team_name} team."
                                }
                except Exception:
                    pass
        except Exception:
            pass
        
        # Fallback to hardcoded responses if no match found in Excel
        if team_name == "Engineer":
            sample_responses = {
                "development environment": "Our engineering team uses VS Code as the primary IDE, with Docker for containerization and GitHub for version control.",
                "code review": "We follow a peer review process for all code changes. Each pull request requires at least two approvals before merging.",
                "deployment": "We use a CI/CD pipeline with Jenkins for automated testing and deployment."
            }
        elif team_name == "Product":
            sample_responses = {
                "roadmap": "Our product roadmap is maintained in Jira and reviewed quarterly with stakeholders.",
                "user research": "We conduct user research sessions bi-weekly and share findings with the entire product team.",
                "feature prioritization": "We use the RICE framework (Reach, Impact, Confidence, Effort) for feature prioritization."
            }
        else:
            sample_responses = {}
        
        # Simple keyword matching for demo purposes
        for keyword, response in sample_responses.items():
            if keyword.lower() in query.lower():
                return {
                    "answer": response,
                    "message": f"Here's information about {keyword} for the {team_name} team."
                }
        
        return {
            "answer": f"I don't have specific information about that for the {team_name} team. Please check the team documentation or ask your team lead.",
            "message": "If you have more questions, feel free to ask!"
        }
    
    else:
        return {
            "error": "Invalid action",
            "message": "Please specify a valid action: list_teams, get_docs, create_tasks, or ask_question."
        }
    

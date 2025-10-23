from typing import List, Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass
import os
import pandas as pd
import httpx
import asyncio
from dotenv import load_dotenv

from ibm_watsonx_orchestrate.agent_builder.tools import tool

# Load environment variables
# Try to load from different possible locations
current_dir = os.path.dirname(os.path.abspath(__file__))
env_paths = [
    os.path.join(current_dir, '.env'),  # Current directory
    os.path.join(os.path.dirname(current_dir), '.env'),  # Parent directory
    os.path.join(os.path.dirname(os.path.dirname(current_dir)), '.env'),  # Grandparent directory
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), '.env'),  # Great-grandparent directory
    '.env'  # Root directory
]

env_loaded = False
for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded .env from {env_path}")
        env_loaded = True
        break

if not env_loaded:
    print("Warning: Could not find .env file")
    load_dotenv()  # Try default loading as fallback

# GitHub API configuration
# Set GitHub token directly
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com/repos/Samarinnayak/project_buddy_test_1/issues"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


class Team(str, Enum):
    ENGINEER = 'Engineer'
    PRODUCT = 'Product'
    DESIGN = 'Design'
    MARKETING = 'Marketing'
    SALES = 'Sales'
    CUSTOMER_SUPPORT = 'Customer Support'
    HUMAN_RESOURCES = 'Human Resources'


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
def new_joiner(action: str, team: Optional[str] = None, query: Optional[str] = None) -> Dict:
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
    team_enum = None
    if team:
        try:
            # Try to find the matching team enum
            for t in Team:
                if t.value == team:
                    team_enum = t
                    break
        except Exception:
            pass
    
    if action == "list_teams":
        # Return teams in a format that can be rendered as selectable options
        selectable_teams = []
        for team in Team:
            selectable_teams.append({
                "name": team.value,
                "id": team.value,
                "selectable": True
            })
        
        # Create a formatted message with team options that look like buttons
        # Format each team as a separate line with a button-like appearance
        team_buttons = "\n".join([f"[{team.value}]" for team in Team])
        
        return {
            "teams": selectable_teams,
            "message": f"Please select one of the following teams by clicking or typing the team name:\n\n{team_buttons}"
        }
    
    if not team:
        return {
            "error": "Team is required for this action",
            "message": "Please specify a team."
        }
    
    # Get team name for display
    team_name = team
    
    if action == "get_docs":
        # Get the knowledge base directory
        knowledge_base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                        "knowladge_base")
        
        # Dynamically load team-specific Excel file
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
                    
                    # Convert Excel data to documents
                    team_docs = []
                    for _, row in df.iterrows():
                        if 'Title' in df.columns and 'Content' in df.columns:
                            title = row['Title'] if not pd.isna(row['Title']) else "Untitled Document"
                            content = row['Content'] if not pd.isna(row['Content']) else "No content available"
                            url = row['URL'] if 'URL' in df.columns and not pd.isna(row['URL']) else None
                            
                            team_docs.append(Document(
                                title=title,
                                content=content,
                                url=url
                            ))
                    
                    if team_docs:
                        # Use documents from Excel file
                        docs = team_docs
                    else:
                        # Fallback to default documents if Excel file is empty
                        docs = [
                            Document(
                                title=f"{team_name} Onboarding Guide (Default)",
                                content=f"This is a default guide as the Excel file was empty for {team_name} team.",
                                url=f"https://example.com/{team_name.lower()}-onboarding"
                            )
                        ]
                except Exception as e:
                    # Fallback to default documents if there's an error reading the Excel file
                    docs = [
                        Document(
                            title=f"{team_name} Onboarding Guide (Default)",
                            content=f"This is a default guide. Error reading Excel file: {str(e)}",
                            url=f"https://example.com/{team_name.lower()}-onboarding"
                        )
                    ]
            else:
                # Fallback to default documents if Excel file doesn't exist
                docs = [
                    Document(
                        title=f"{team_name} Onboarding Guide (Default)",
                        content=f"This is a default guide as no Excel file was found for {team_name} team.",
                        url=f"https://example.com/{team_name.lower()}-onboarding"
                    )
                ]
        except Exception as e:
            # Fallback to default documents if there's any error
            docs = [
                Document(
                    title=f"{team_name} Onboarding Guide (Default)",
                    content=f"This is a default guide. Error: {str(e)}",
                    url=f"https://example.com/{team_name.lower()}-onboarding"
                )
            ]
            
        return {
            "documents": [{"title": doc.title, "url": doc.url, "content_preview": doc.content[:100] + "..."} for doc in docs],
            "message": f"Here are the documents for the {team_name} team. These resources will help you get started and understand the team's processes."
        }
    
    elif action == "create_tasks":
        # Get the knowledge base directory
        knowledge_base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                        "knowladge_base")
        
        # Dynamically load team-specific Excel file for tasks
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
                    # Read Excel file - following ProjectBuddyApp approach
                    df = pd.read_excel(excel_path, sheet_name="FinalSheet", header=0)
                    
                    # Group tasks by Task Type
                    task_types = df['Task Type'].dropna().unique() if 'Task Type' in df.columns else []
                    
                    if len(task_types) > 0:
                        # Create GitHub tasks from Excel data
                        github_tasks = []
                        
                        for task_type in task_types:
                            task_df = df[df['Task Type'] == task_type]
                            if task_df.empty:
                                continue
                            
                            # Format tasks as checklist items
                            for _, row in task_df.iterrows():
                                task_name = row['Task Name'].strip() if 'Task Name' in row and pd.notna(row['Task Name']) else "Untitled Task"
                                task_info = row['Task Info'].strip() if 'Task Info' in row and pd.notna(row['Task Info']) else ""
                                task_links = row['Task Related Links'].strip() if 'Task Related Links' in row and pd.notna(row['Task Related Links']) else ""
                                task_duration = row['Task Duration'].strip() if 'Task Duration' in row and pd.notna(row['Task Duration']) else ""
                                additional_info = row['Additional Information'].strip() if 'Additional Information' in row and pd.notna(row['Additional Information']) else ""
                                
                                # Build description with markdown formatting
                                description = f"**{task_name}**"
                                if task_duration:
                                    description += f" ({task_duration})"
                                if task_info:
                                    description += f"\n{task_info}"
                                if task_links:
                                    description += f"\n🔗 [Link]({task_links})"
                                if additional_info:
                                    description += f"\n{additional_info}"
                                
                                github_tasks.append(GitHubTask(
                                    title=f"{task_type}: {task_name}",
                                    description=description,
                                    assignee="new_joiner",
                                    status="To Do"
                                ))
                        
                        if github_tasks:
                            # Use tasks from Excel file
                            specific_tasks = github_tasks
                        else:
                            # Fallback to default tasks if Excel file has no valid tasks
                            specific_tasks = [
                                GitHubTask(
                                    title=f"Set up {team_name} environment (Default)",
                                    description=f"Install required tools and configure your local environment for {team_name} team.",
                                    assignee="new_joiner",
                                    status="To Do"
                                )
                            ]
                    else:
                        # Fallback to default tasks if Excel file has no Task Type column
                        specific_tasks = [
                            GitHubTask(
                                title=f"Set up {team_name} environment (Default)",
                                description=f"Install required tools and configure your local environment for {team_name} team.",
                                assignee="new_joiner",
                                status="To Do"
                            )
                        ]
                except Exception as e:
                    # Fallback to default tasks if there's an error reading the Excel file
                    specific_tasks = [
                        GitHubTask(
                            title=f"Set up {team_name} environment (Default)",
                            description=f"Install required tools and configure your local environment for {team_name} team. (Error reading Excel: {str(e)})",
                            assignee="new_joiner",
                            status="To Do"
                        )
                    ]
            else:
                # Fallback to default tasks if Excel file doesn't exist
                specific_tasks = [
                    GitHubTask(
                        title=f"Set up {team_name} environment (Default)",
                        description=f"Install required tools and configure your local environment for {team_name} team. (Excel file not found)",
                        assignee="new_joiner",
                        status="To Do"
                    )
                ]
        except Exception as e:
            # Fallback to default tasks if there's any error
            specific_tasks = [
                GitHubTask(
                    title=f"Set up {team_name} environment (Default)",
                    description=f"Install required tools and configure your local environment for {team_name} team. (Error: {str(e)})",
                    assignee="new_joiner",
                    status="To Do"
                )
            ]
        
        # Add common tasks for all teams
        common_tasks = [
            GitHubTask(
                title=f"Complete {team_name} onboarding checklist",
                description=f"Go through the {team_name} onboarding checklist and mark items as completed.",
                assignee="new_joiner",
                status="To Do"
            ),
            GitHubTask(
                title="Schedule 1:1 meetings with team members",
                description="Schedule introductory 1:1 meetings with all team members.",
                assignee="new_joiner",
                status="To Do"
            ),
            GitHubTask(
                title="Complete company-wide orientation",
                description="Attend the company-wide orientation session for new employees.",
                assignee="new_joiner",
                status="To Do"
            )
        ]
        
        # Combine specific and common tasks
        all_tasks = specific_tasks + common_tasks
        
        # Create GitHub issues via the API if token is available
        created_issues = []
        # Debug information about GitHub token
        token_status = "available" if GITHUB_TOKEN else "missing"
        print(f"GitHub token status: {token_status}")
        print(f"GitHub API URL: {GITHUB_API_URL}")
        
        if GITHUB_TOKEN:
            try:
                # Create GitHub issues asynchronously
                for task in all_tasks:
                    # Prepare issue data
                    issue_data = {
                        "title": task.title,
                        "body": task.description,
                        # "assignees": ["new_joiner"],  # Optional: must be a collaborator in the repo
                    }
                    
                    # Make synchronous POST request to GitHub API
                    response = httpx.post(GITHUB_API_URL, json=issue_data, headers=HEADERS)
                    
                    if response.status_code == 201:
                        issue = response.json()
                        issue_url = issue.get("html_url", "No URL available")
                        created_issues.append({
                            "title": task.title,
                            "url": issue_url,
                            "status": "Created"
                        })
                    else:
                        created_issues.append({
                            "title": task.title,
                            "error": f"Failed to create: {response.status_code}",
                            "status": "Failed"
                        })
            except Exception as e:
                # If there's an error with the GitHub API, just return the tasks without creating issues
                task_links_message = ""
                if created_issues:
                    # Check if any issues were successfully created (have URLs)
                    successful_issues = [issue for issue in created_issues if "url" in issue]
                    if successful_issues:
                        task_links_message = "\n\n**GitHub Task Links (partial):**\n"
                        for issue in successful_issues:
                            task_links_message += f"- [{issue['title']}]({issue['url']})\n"
                
                message = f"GitHub tasks have been prepared for your onboarding to the {team_name} team, but could not be created in GitHub due to an error: {str(e)}"
                message += task_links_message
                
                return {
                    "tasks": [{"title": task.title, "description": task.description, "status": task.status} for task in all_tasks],
                    "message": message
                }
        
        # Return both the tasks and created issues
        task_links_message = ""
        permission_error = False
        
        if created_issues:
            # Check if any issues were successfully created (have URLs)
            successful_issues = [issue for issue in created_issues if "url" in issue]
            failed_issues = [issue for issue in created_issues if "error" in issue]
            
            if successful_issues:
                task_links_message = "\n\n**GitHub Task Links:**\n"
                for issue in successful_issues:
                    task_links_message += f"- [{issue['title']}]({issue['url']})\n"
            
            # Check if we had authentication, permission, or not found errors
            if failed_issues and all(("401" in issue.get("error", "") or "403" in issue.get("error", "") or "404" in issue.get("error", "")) for issue in failed_issues):
                permission_error = True
        
        message = f"GitHub tasks have been prepared for your onboarding to the {team_name} team."
        if not GITHUB_TOKEN:
            message += " However, the GitHub token is missing. Please set the GITHUB_TOKEN environment variable to create GitHub issues."
        elif permission_error:
            message += " However, the tasks could not be created in GitHub due to authentication, permission, or repository issues. Please check your GitHub token, repository permissions, and repository existence."
        else:
            message += f" These tasks are based on the team's specific documentation and requirements."
        
        message += task_links_message
        
        return {
            "tasks": [{"title": task.title, "description": task.description, "status": task.status} for task in all_tasks],
            "created_issues": created_issues if created_issues else None,
            "message": message
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

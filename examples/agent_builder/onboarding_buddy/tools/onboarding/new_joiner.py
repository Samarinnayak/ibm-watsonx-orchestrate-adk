from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field

from ibm_watsonx_orchestrate.agent_builder.tools import tool


class Team(str, Enum):
    ENGINEERING = 'Engineering'
    PRODUCT = 'Product'
    DESIGN = 'Design'
    MARKETING = 'Marketing'
    SALES = 'Sales'
    CUSTOMER_SUPPORT = 'Customer Support'
    HUMAN_RESOURCES = 'Human Resources'


class Document(BaseModel):
    title: str = Field(None, description="Title of the document")
    content: str = Field(None, description="Content of the document")
    url: Optional[str] = Field(None, description="URL to the document if available")


class GitHubTask(BaseModel):
    title: str = Field(None, description="Title of the GitHub task")
    description: str = Field(None, description="Description of the GitHub task")
    assignee: str = Field(None, description="Assignee of the GitHub task")
    status: str = Field(None, description="Status of the GitHub task")


@tool
def new_joiner(action: str, team: Optional[Team] = None, query: Optional[str] = None) -> Dict:
    """
    Tool for new joiners to get information about teams, documentation, and create GitHub tasks.
    
    Args:
        action: The action to perform. Must be one of: "list_teams", "get_docs", "create_tasks", "ask_question"
        team: The team to get information about (required for "get_docs", "create_tasks", and "ask_question")
        query: The question to ask (required for "ask_question")
    
    Returns:
        A dictionary containing the requested information
    """
    if action == "list_teams":
        return {
            "teams": [team.value for team in Team],
            "message": "Please select one of the teams above to continue."
        }
    
    if not team:
        return {
            "error": "Team is required for this action",
            "message": "Please specify a team."
        }
    
    if action == "get_docs":
        # In a real implementation, this would fetch documents from a database or knowledge base
        team_docs = {
            Team.ENGINEERING: [
                Document(
                    title="Engineering Onboarding Guide",
                    content="This guide covers the engineering team's processes, tools, and best practices.",
                    url="https://example.com/engineering-onboarding"
                ),
                Document(
                    title="Technical Stack Overview",
                    content="An overview of our technical stack and architecture.",
                    url="https://example.com/tech-stack"
                )
            ],
            Team.PRODUCT: [
                Document(
                    title="Product Team Handbook",
                    content="This handbook covers the product team's processes and methodologies.",
                    url="https://example.com/product-handbook"
                )
            ],
            # Add documents for other teams as needed
        }
        
        docs = team_docs.get(team, [])
        return {
            "documents": [{"title": doc.title, "url": doc.url} for doc in docs],
            "message": f"Here are the documents for the {team.value} team."
        }
    
    elif action == "create_tasks":
        # In a real implementation, this would create tasks in GitHub
        tasks = [
            GitHubTask(
                title=f"Complete {team.value} onboarding checklist",
                description=f"Go through the {team.value} onboarding checklist and mark items as completed.",
                assignee="new_joiner",
                status="To Do"
            ),
            GitHubTask(
                title="Set up development environment",
                description="Set up your local development environment following the team's guidelines.",
                assignee="new_joiner",
                status="To Do"
            ),
            GitHubTask(
                title="Schedule 1:1 meetings with team members",
                description="Schedule introductory 1:1 meetings with all team members.",
                assignee="new_joiner",
                status="To Do"
            )
        ]
        
        return {
            "tasks": [{"title": task.title, "description": task.description, "status": task.status} for task in tasks],
            "message": f"GitHub tasks have been created for your onboarding to the {team.value} team."
        }
    
    elif action == "ask_question":
        if not query:
            return {
                "error": "Query is required for asking questions",
                "message": "Please provide a question to ask."
            }
        
        # In a real implementation, this would use a knowledge base to answer questions
        # For now, we'll provide some sample responses
        sample_responses = {
            Team.ENGINEERING: {
                "development environment": "Our engineering team uses VS Code as the primary IDE, with Docker for containerization and GitHub for version control.",
                "code review": "We follow a peer review process for all code changes. Each pull request requires at least two approvals before merging.",
                "deployment": "We use a CI/CD pipeline with Jenkins for automated testing and deployment."
            },
            Team.PRODUCT: {
                "roadmap": "Our product roadmap is maintained in Jira and reviewed quarterly with stakeholders.",
                "user research": "We conduct user research sessions bi-weekly and share findings with the entire product team.",
                "feature prioritization": "We use the RICE framework (Reach, Impact, Confidence, Effort) for feature prioritization."
            },
            # Add responses for other teams as needed
        }
        
        team_responses = sample_responses.get(team, {})
        
        # Simple keyword matching for demo purposes
        for keyword, response in team_responses.items():
            if keyword.lower() in query.lower():
                return {
                    "answer": response,
                    "message": f"Here's information about {keyword} for the {team.value} team."
                }
        
        return {
            "answer": f"I don't have specific information about that for the {team.value} team. Please check the team documentation or ask your team lead.",
            "message": "If you have more questions, feel free to ask!"
        }
    
    else:
        return {
            "error": "Invalid action",
            "message": "Please specify a valid action: list_teams, get_docs, create_tasks, or ask_question."
        }


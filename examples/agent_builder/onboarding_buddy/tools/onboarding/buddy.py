from typing import Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field

from ibm_watsonx_orchestrate.agent_builder.tools import tool


class BuddyAction(str, Enum):
    GET_TEMPLATE = 'get_template'
    UPLOAD_TEMPLATE = 'upload_template'


class BuddyTemplate(BaseModel):
    new_joiner_name: str = Field(None, description="Name of the new joiner")
    team: str = Field(None, description="Team of the new joiner")
    start_date: str = Field(None, description="Start date of the new joiner")
    buddy_name: str = Field(None, description="Name of the buddy")
    onboarding_plan: str = Field(None, description="Detailed onboarding plan for the new joiner")
    resources: str = Field(None, description="Resources to be provided to the new joiner")
    check_in_schedule: str = Field(None, description="Schedule for check-ins with the new joiner")
    goals_for_first_month: str = Field(None, description="Goals for the new joiner's first month")


@tool
def buddy(action: BuddyAction, template_data: Optional[Dict] = None) -> Dict:
    """
    Tool for buddies to get templates and upload completed templates for onboarding new joiners.
    
    Args:
        action: The action to perform. Must be one of: "get_template", "upload_template"
        template_data: The completed template data (required for "upload_template")
    
    Returns:
        A dictionary containing the requested information or confirmation
    """
    if action == BuddyAction.GET_TEMPLATE:
        template = {
            "new_joiner_name": "",
            "team": "",
            "start_date": "",
            "buddy_name": "",
            "onboarding_plan": "",
            "resources": "",
            "check_in_schedule": "",
            "goals_for_first_month": ""
        }
        
        instructions = """
# Buddy Onboarding Template

Please fill out this template to create an onboarding plan for your new team member.

## Instructions:
1. Fill in all fields with relevant information
2. Be specific about the onboarding plan and resources
3. Set clear goals for the first month
4. Establish a regular check-in schedule
5. Once completed, upload the template using the 'upload_template' action

## Example:
```
{
    "new_joiner_name": "Jane Doe",
    "team": "Engineering",
    "start_date": "2025-11-01",
    "buddy_name": "John Smith",
    "onboarding_plan": "Week 1: Introduction to team and tools\nWeek 2: Shadow team members\nWeek 3: Work on small tasks\nWeek 4: Take on first project",
    "resources": "Team documentation, access to development environment, team chat channels",
    "check_in_schedule": "Daily for first week, then weekly on Mondays at 10am",
    "goals_for_first_month": "Complete onboarding, understand team processes, contribute to at least one project"
}
```
"""
        
        return {
            "template": template,
            "instructions": instructions,
            "message": "Here's the buddy onboarding template. Please fill it out and upload it using the 'upload_template' action."
        }
    
    elif action == BuddyAction.UPLOAD_TEMPLATE:
        if not template_data:
            return {
                "error": "Template data is required",
                "message": "Please provide the completed template data."
            }
        
        # Validate template data
        required_fields = [
            "new_joiner_name", "team", "start_date", "buddy_name", 
            "onboarding_plan", "resources", "check_in_schedule", "goals_for_first_month"
        ]
        
        missing_fields = [field for field in required_fields if not template_data.get(field)]
        
        if missing_fields:
            return {
                "error": "Incomplete template",
                "missing_fields": missing_fields,
                "message": f"Please complete the following fields: {', '.join(missing_fields)}"
            }
        
        # In a real implementation, this would save the template to a database
        # and potentially notify relevant parties
        
        return {
            "success": True,
            "message": f"Onboarding template for {template_data['new_joiner_name']} has been uploaded successfully. The onboarding plan will be shared with them before their start date on {template_data['start_date']}."
        }
    
    else:
        return {
            "error": "Invalid action",
            "message": "Please specify a valid action: get_template or upload_template."
        }
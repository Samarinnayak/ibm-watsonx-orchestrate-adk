from typing import Dict, Optional, List
from enum import Enum
import random
from ibm_watsonx_orchestrate.agent_builder.tools import tool
from pymongo import MongoClient
import os

# MongoDB connection
API_KEY="C3ePfiQHqD_PbHuo6rHivG1fDa_AgOcqMdmzHOawUyi1"
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://khushboo110597_db_user:iYHpCXn8bTSZYEFT@onboardingassistant.ijmnyjp.mongodb.net/?tlsAllowInvalidCertificates=true")

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)

# Use a database in MongoDB Atlas
db = client["buddy_db"]

# Team presentation helpers
TEAM_ICONS = ["🚀", "⚡", "🔥", "💫", "🌟", "🛡️", "🔮", "🧩", "🧠", "💎", "🌈", "🦄", "🏆", "🌊", "🌻", "🍀"]
TEAM_THEMES = [
    {"name": "Ocean Blue", "color": "#1E90FF", "accent": "#00BFFF"},
    {"name": "Forest Green", "color": "#228B22", "accent": "#32CD32"},
    {"name": "Ruby Red", "color": "#B22222", "accent": "#FF6347"},
    {"name": "Royal Purple", "color": "#4B0082", "accent": "#8A2BE2"},
    {"name": "Sunset Orange", "color": "#FF8C00", "accent": "#FFA500"},
    {"name": "Emerald", "color": "#008B8B", "accent": "#20B2AA"},
    {"name": "Amethyst", "color": "#9932CC", "accent": "#BA55D3"},
    {"name": "Golden", "color": "#DAA520", "accent": "#FFD700"}
]

def assign_team_attributes(team_names: List[str]) -> List[Dict]:
    """
    Assigns creative visual attributes to team names
    
    Args:
        team_names: List of team names from the database
        
    Returns:
        List of team objects with visual attributes
    """
    enhanced_teams = []
    used_icons = set()
    used_themes = set()
    
    for team_name in team_names:
        # Generate a unique team identifier based on name
        team_id = team_name.lower().replace(" ", "_")
        
        # Select a unique icon if possible
        available_icons = [icon for icon in TEAM_ICONS if icon not in used_icons]
        if not available_icons:
            available_icons = TEAM_ICONS  # Reuse icons if we run out
        
        icon = random.choice(available_icons)
        used_icons.add(icon)
        
        # Select a unique theme if possible
        available_themes = [theme for theme in TEAM_THEMES if theme["name"] not in used_themes]
        if not available_themes:
            available_themes = TEAM_THEMES  # Reuse themes if we run out
            
        theme = random.choice(available_themes)
        used_themes.add(theme["name"])
        
        # Create team object with visual attributes
        team_obj = {
            "id": team_id,
            "name": team_name,
            "icon": icon,
            "theme": theme["name"],
            "color": theme["color"],
            "accent_color": theme["accent"],
            "display_name": f"{icon} {team_name}",
            "formatted_name": f"[{icon} {team_name}]"  # Format for clickable buttons
        }
        
        enhanced_teams.append(team_obj)
    
    return enhanced_teams

@tool
def get_all_onboarded_teams() -> dict:
    """
    Tool for fetching all the teams names from the database with creative visual attributes
    
    Returns:
        A dict containing enhanced team information for UI display
    """
    collection = db["team_data"]
    team_names = collection.distinct("team_name")
    
    # Enhance team names with visual attributes
    enhanced_teams = assign_team_attributes(team_names)
    
    # Group teams by first letter for alphabetical organization
    grouped_teams = {}
    for team in enhanced_teams:
        first_letter = team["name"][0].upper()
        if first_letter not in grouped_teams:
            grouped_teams[first_letter] = []
        grouped_teams[first_letter].append(team)
    
    return {
        'teams': enhanced_teams,
        'grouped_teams': grouped_teams,
        'team_count': len(enhanced_teams),
        'presentation_style': {
            'suggested_view': 'card_grid',
            'alternate_views': ['list', 'alphabetical_groups']
        },
        'display_instructions': """
        To display team names properly in the UI:
        
        1. For clickable buttons, use the formatted_name property:
           [🚀 Engineering]
           
        2. For inline text, use the display_name property:
           🚀 Engineering
           
        3. For styled display, use HTML with the color property:
           <span style="color: #1E90FF">🚀 Engineering</span>
        """
    }

# Example of how an agent would parse and display this data on UI
"""
UI RENDERING GUIDE:

When the agent receives the response from get_all_onboarded_teams(), it can render the teams in multiple ways:

1. CARD GRID VIEW (suggested default):
   - Create a grid of cards, each representing a team
   - Each card uses the team's color as background or border
   - Display the team icon and name prominently
   - Example HTML/CSS for a single team card:
   
   <div class="team-card" style="border-color: {{team.color}}; background: linear-gradient(to bottom right, white, {{team.accent_color}}10)">
     <div class="team-icon">{{team.icon}}</div>
     <h3 class="team-name">{{team.name}}</h3>
   </div>

2. ALPHABETICAL GROUPS:
   - Display teams grouped by their first letter
   - Use the grouped_teams data structure
   - Example rendering:
   
   <div class="alphabet-section">
     <h2 class="letter-heading">A</h2>
     <div class="team-list">
       <!-- Teams starting with A -->
       <div class="team-item" style="color: {{team.color}}">
         <span class="team-icon">{{team.icon}}</span>
         <span class="team-name">{{team.name}}</span>
       </div>
     </div>
   </div>

3. LIST VIEW:
   - Simple list with team icons and names
   - Color-coded by team theme
   - Example:
   
   <ul class="team-list">
     <li class="team-item" style="border-left: 4px solid {{team.color}}">
       <span class="team-icon">{{team.icon}}</span>
       <span class="team-name">{{team.name}}</span>
     </li>
   </ul>

The agent can switch between these views based on user preference or screen size.
"""
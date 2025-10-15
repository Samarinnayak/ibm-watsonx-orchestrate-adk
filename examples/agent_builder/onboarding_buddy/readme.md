# Onboarding Buddy Agent

This agent helps with the onboarding process for new employees and provides support for buddies who are helping new joiners.

## Features

### For New Joiners
- View available teams
- Access team-specific documentation
- Create GitHub tasks for onboarding
- Ask questions about team processes and resources

### For Buddies
- Get a template for creating an onboarding plan
- Upload completed templates
- Provide structured support for new joiners

## Steps to Import

1. Run `orchestrate server start -e .my-env`
2. Run `pip install -r tools/requirements.txt`
3. Run the import all script `./import-all.sh`
4. Run `orchestrate chat start`

## Suggested Script

### For New Joiners
- I'm a new joiner
- Show me the available teams
- I want to join the Engineering team
- Show me the documentation for the Engineering team
- Create GitHub tasks for my onboarding
- What development environment does the Engineering team use?

### For Buddies
- I'm a buddy
- I need a template for onboarding a new team member
- (Fill out the template)
- Upload the completed template
#!/usr/bin/env bash
set -x

orchestrate env activate local
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Remove agents
orchestrate agents remove -n onboarding_agent -k native
orchestrate agents remove -n onboarding_knowledge_agent -k native

# Remove tools
orchestrate tools remove  -n new_joiner
orchestrate tools remove  -n buddy
orchestrate tools remove  -n upload_template
orchestrate tools remove  -n get_all_onboarded_teams

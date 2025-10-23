#!/usr/bin/env bash
set -x

orchestrate env activate local
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Import knowledge base
orchestrate knowledge-bases import -f ${SCRIPT_DIR}/knowledge_base/onboarding_knowledge_base.yaml

# Import tools
for python_tool in onboarding/new_joiner.py onboarding/buddy.py onboarding/upload_template.py onboarding/get_all_onboarded_teams.py; do
  orchestrate tools import -k python -f ${SCRIPT_DIR}/tools/${python_tool} -r ${SCRIPT_DIR}/tools/requirements.txt
done

# Import agents - knowledge agent must be imported first
orchestrate agents import -f ${SCRIPT_DIR}/agents/onboarding_knowledge_agent.yaml
orchestrate agents import -f ${SCRIPT_DIR}/agents/onboarding_agent.yaml

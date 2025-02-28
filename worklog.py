#!/usr/bin/env python3

import requests
import argparse
import json
import toml

# Load configuration from file
config = toml.load("config.toml")

JIRA_URL = config["JIRA"]["JIRA_URL"]
API_TOKEN = config["JIRA"]["API_TOKEN"]

def add_worklog(ticket, hours, account, component):
    url = f"{JIRA_URL}/rest/tempo-timesheets/4/worklogs"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }
    time_spent = int(hours * 3600)  # Convert hours to seconds
    
    data = {
        "originTaskId": ticket,
        "timeSpentSeconds": time_spent,
        "worker": "JIRAUSER55710",  # Adjust based on actual user ID if needed
        "attributes": {
            "_Initiative_": {
                "name": "Account",
                "workAttributeId": 1,
                "value": account
            },
            "_Componenttool_": {
                "name": "Component/tool",
                "workAttributeId": 2,
                "value": component
            }
        },
        "started": "2025-02-28",  # Should be dynamically generated
        "remainingEstimate": 0,
        "includeNonWorkingDays": False
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code in [200, 201]:
        print(f"Successfully logged {hours} hours to {ticket} with account {account} and component {component}.")
    else:
        print(f"Failed to log work: {response.status_code} {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a worklog to a JIRA ticket using Tempo.")
    parser.add_argument("ticket", help="JIRA ticket number (e.g., PROJ-123)")
    parser.add_argument("hours", type=float, help="Number of hours worked, including fractions")
    parser.add_argument("account", help="Tempo Account associated with the worklog")
    parser.add_argument("component", help="Tempo Component related to the worklog")
    
    args = parser.parse_args()
    add_worklog(args.ticket, args.hours, args.account, args.component)

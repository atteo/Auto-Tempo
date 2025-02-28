#!/usr/bin/env python3

import requests
import argparse
import json
import toml
import datetime

# Load configuration from file
config = toml.load("config.toml")

JIRA_URL = config["JIRA"]["JIRA_URL"]
API_TOKEN = config["JIRA"]["API_TOKEN"]

def delete_worklogs_for_date(ticket, date):
    url = f"{JIRA_URL}/rest/tempo-timesheets/4/worklogs/search"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "from": date,
        "to": date,
        "taskKey": [ticket],
        "includeSubtasks": True
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        worklogs = response.json()
        for worklog in worklogs:
            delete_url = f"{JIRA_URL}/rest/tempo-timesheets/4/worklogs/{worklog['tempoWorklogId']}"
            delete_response = requests.delete(delete_url, headers=headers)
            if delete_response.status_code in [200, 204]:
                print(f"Deleted worklog {worklog['tempoWorklogId']} for {ticket} on {date}.")
            else:
                print(f"Failed to delete worklog {worklog['tempoWorklogId']}: {delete_response.status_code} {delete_response.text}")
    else:
        print(f"Failed to retrieve worklogs for {ticket} on {date}: {response.status_code} {response.text}")

def add_worklog(ticket, hours, account, component, date, comment=""):

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
        "comment": comment,
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
        "started": date,
        "remainingEstimate": 0,
        "includeNonWorkingDays": False
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code in [200, 201]:
        print(f"Successfully logged {hours} hours to {ticket} on {date} with account {account} and component {component}.")
    else:
        print(f"Failed to log work for {ticket} on {date}: {response.status_code} {response.text}")

def process_worklog_file(file_path):
    with open(file_path, "r") as f:
        dates_processed = set()
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):  # Skip empty lines and comments
                continue
            try:
                parts = line.split()
                if len(parts) < 3:
                    print(f"Skipping invalid entry: {line}")
                    continue
                if len(parts) >= 3 and parts[1].lower() == "interview":
                    date, hours = parts[:2]
                    account = "002-ORGANI"
                    component = "OrganizationalMatters"
                    comment = " ".join(parts[2:])
                    ticket = "INTERVIEW"
                else:
                    date, ticket, hours, account, component = parts[:5]
                    comment = " ".join(parts[5:]) if len(parts) > 5 else ""
                if date not in dates_processed:
                    delete_worklogs_for_date(ticket, date)
                    dates_processed.add(date)
                add_worklog(ticket, float(hours), account, component, date, comment)
            except ValueError as e:
                print(f"Skipping malformed entry: {line}, error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add multiple worklogs to JIRA using Tempo from a structured text file.")
    parser.add_argument("file", help="Path to the text file containing worklog entries")
    
    args = parser.parse_args()
    process_worklog_file(args.file)

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

keywords = config["keyword"]

def get_working_days(start_date, end_date):
    url = f"{JIRA_URL}/rest/tempo-timesheets/4/private/days/search"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }
    data = {
        "from": start_date,
        "to": end_date,
        "userKeys": ["JIRAUSER55710"]
    }
    
    try:
        datetime.datetime.strptime(start_date, "%Y-%m-%d")
        datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        print(f"Invalid date format: {e}")
        return set()

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        days_info = response.json()
        working_days = {day['date'] for day in days_info[0]['days'] if day['type'] == "WORKING_DAY"}
        return working_days
    else:
        print(f"Failed to retrieve working days: {response.status_code} {response.text}")
        return set()
def delete_worklogs_for_date(date):
    url = f"{JIRA_URL}/rest/tempo-timesheets/4/worklogs/search"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "from": date,
        "to": date,
        "includeSubtasks": True
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        worklogs = response.json()
        for worklog in worklogs:
            delete_url = f"{JIRA_URL}/rest/tempo-timesheets/4/worklogs/{worklog['tempoWorklogId']}"
            delete_response = requests.delete(delete_url, headers=headers)
            if delete_response.status_code in [200, 204]:
                print(f"Deleted worklog {worklog['tempoWorklogId']} on {date}.")
            else:
                print(f"Failed to delete worklog {worklog['tempoWorklogId']}: {delete_response.status_code} {delete_response.text}")
    else:
        print(f"Failed to retrieve worklogs on {date}: {response.status_code} {response.text}")

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
        print(f"{date} Logged {hours}h to {ticket}, account {account}, component {component}, \"{comment}\".")
    else:
        print(f"Failed to log work for {ticket} on {date}: {response.status_code} {response.text}")

def process_worklog_file(file_path):
    with open(file_path, "r") as f:
        dates_processed = {}
        daily_hours = {}
        
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):  # Skip empty lines and comments
                continue
            parts = line.split()
            if len(parts) < 3:
                print(f"Skipping invalid entry: {line}")
                continue
            try:
                keyword = parts[2].lower()
                if keyword in keywords:
                    date, hours = parts[0], float(parts[1])
                    ticket = keywords[keyword]["ticket"]
                    account = keywords[keyword]["account"]
                    component = keywords[keyword]["component"]
                    comment = " ".join(parts[3:]).strip('"')
            except ValueError as e:
                print(f"Skipping malformed entry: {line}, error: {e}")
                continue

            # Accumulate hours for each date
            if date not in daily_hours:
                daily_hours[date] = 0
            daily_hours[date] += float(hours)
            
            # Store worklog details for later processing
            if date not in dates_processed:
                dates_processed[date] = []
            dates_processed[date].append((ticket, float(hours), account, component, comment))
    
    # Determine the date range for validation
    all_dates = list(daily_hours.keys())
    if all_dates:
        start_date = min(all_dates)
        end_date = max(all_dates)
        working_days = get_working_days(start_date, end_date)
    else:
        working_days = set()

    # Validate worklogs, ensuring no worklogs on non-working days
    valid_dates = []
    for date, total_hours in daily_hours.items():
        if date not in working_days:
            print(f"{date} is a non-working day. Skipping worklog application.")
        elif total_hours != 8:
            print(f"Total logged hours for {date} is {total_hours}, which is not equal to 8. Skipping worklog application.")
        else:
            valid_dates.append(date)
    
    # Process worklogs only for valid dates
    for date in valid_dates:
        delete_worklogs_for_date(date)
        for ticket, hours, account, component, comment in dates_processed[date]:
            add_worklog(ticket, hours, account, component, date, comment)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add multiple worklogs to JIRA using Tempo from a structured text file.")
    parser.add_argument("file", help="Path to the text file containing worklog entries")
    
    args = parser.parse_args()
    process_worklog_file(args.file)

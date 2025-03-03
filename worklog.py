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
def get_existing_worklogs_for_date(date):
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
        return response.json()
    else:
        print(f"Failed to retrieve worklogs on {date}: {response.status_code} {response.text}")
        return []

def delete_worklogs(worklogs):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    for worklog in worklogs:
        delete_url = f"{JIRA_URL}/rest/tempo-timesheets/4/worklogs/{worklog['tempoWorklogId']}"
        delete_response = requests.delete(delete_url, headers=headers)
        if delete_response.status_code in [200, 204]:
            print(f"Deleted worklog {worklog['tempoWorklogId']}.")
        else:
            print(f"Failed to delete worklog {worklog['tempoWorklogId']}: {delete_response.status_code} {delete_response.text}")

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

def generate_template(month):
    # Determine the first and last day of the month
    start_date = f"{month}-01"
    end_date = (datetime.datetime.strptime(start_date, "%Y-%m-%d") + datetime.timedelta(days=31)).replace(day=1) - datetime.timedelta(days=1)
    end_date = end_date.strftime("%Y-%m-%d")

    # Get working days for the month
    working_days = get_working_days(start_date, end_date)

    # Generate template
    template_lines = []
    for day in sorted(working_days):
        template_lines.append(f"{day} 8.0 jira-ticket \"comment\"")

    # Output template
    template_content = (
        "# date hours jira-ticket comment [account:<account>] [component:<component>]\n"
        "# or\n"
        "# date hours <keyword> comment [account:<account>] [component:<component>]\n"
        "#\n"
        "# where <keyword> is one of: interview, scrum, training, etc\n"
        "# See the definitions of keywords in config.toml\n\n"
        + "\n".join(template_lines)
    )
    
    file_name = f"{month}.jira"
    try:
        with open(file_name, "x") as f:
            f.write(template_content)
        print(f"Template written to {file_name}")
    except FileExistsError:
        print(f"File {file_name} already exists. Template not written to avoid overwriting.")

def parse_worklog_line(line):
    parts = line.split()
    if len(parts) < 3:
        raise ValueError(f"Invalid entry: {line}")
    
    date, hours = parts[0], float(parts[1])
    ticket_or_keyword = parts[2]
    project_key = ticket_or_keyword.split('-')[0] if '-' in ticket_or_keyword else None

    if project_key and project_key in config.get("project", {}):
        ticket = ticket_or_keyword
        project_config = config["project"][project_key]
        account = project_config["account"]
        component = project_config["component"]
        comment = " ".join(parts[3:]).strip('"') if len(parts) > 3 else ""
    elif ticket_or_keyword.lower() in keywords:
        keyword = parts[2].lower()
        ticket = keywords[keyword]["ticket"]
        account = keywords[keyword]["account"]
        component = keywords[keyword]["component"]
        comment = " ".join(parts[3:]).strip('"') if len(parts) > 3 else ""
    else:
        raise ValueError(f"Unknown project or keyword in entry: {line}.")

    # Check for account and component overrides
    if len(parts) > 3:
        for part in parts[3:]:
            if part.startswith("account:"):
                account = part.split(":", 1)[1]
            elif part.startswith("component:"):
                component = part.split(":", 1)[1]

    return date, hours, ticket, account, component, comment

def validate_worklogs(daily_hours, working_days):
    valid_dates = []
    for date, total_hours in daily_hours.items():
        if date not in working_days:
            print(f"{date} is a non-working day. Skipping worklog application.")
        elif total_hours != 8:
            raise ValueError(f"Total logged hours for {date} is {total_hours}, which is not equal to 8. Stopping worklog application.")
        else:
            valid_dates.append(date)
    return valid_dates

def process_worklog_file(file_path):
    dates_processed = {}
    daily_hours = {}
    
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):  # Skip empty lines and comments
                continue
            try:
                date, hours, ticket, account, component, comment = parse_worklog_line(line)
            except ValueError as e:
                print(f"Error processing line: {line}. {e}")
                return

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
    valid_dates = validate_worklogs(daily_hours, working_days)
    
    # Process worklogs only for valid dates
    for date in valid_dates:
        existing_worklogs = get_existing_worklogs_for_date(date)
        new_worklogs = dates_processed[date]

        # Compare existing and new worklogs by ticket, hours, account, component, and comment
        existing_worklogs_list = sorted([(wl['originTaskId'], wl['timeSpentSeconds'] / 3600, wl['attributes']['_Initiative_']['value'], wl['attributes']['_Componenttool_']['value'], wl['comment']) for wl in existing_worklogs])
        new_worklogs_list = sorted([(ticket, hours, account, component, comment) for ticket, hours, account, component, comment in new_worklogs])

        if existing_worklogs_list != new_worklogs_list:
            # Print differences
            existing_set = set(existing_worklogs_list)
            new_set = set(new_worklogs_list)
            print("Worklogs to be deleted:")
            for worklog in existing_set - new_set:
                print(worklog)
            print("Worklogs to be added:")
            for worklog in new_set - existing_set:
                print(worklog)
            delete_worklogs(existing_worklogs)
            for ticket, hours, account, component, comment in new_worklogs:
                add_worklog(ticket, hours, account, component, date, comment)
        else:
            print(f"No changes in worklogs for {date}. Skipping update.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage JIRA worklogs using Tempo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Apply command
    apply_parser = subparsers.add_parser("apply", help="Apply worklogs from a file")
    apply_parser.add_argument("file", help="Path to the text file containing worklog entries")

    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate a worklog template for a month")
    generate_parser.add_argument("month", help="Month in the format YYYY-MM")

    args = parser.parse_args()

    if args.command == "apply":
        process_worklog_file(args.file)
    elif args.command == "generate":
        generate_template(args.month)

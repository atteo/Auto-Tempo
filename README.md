# AutoTempo - JIRA Worklog Manager

This script helps manage JIRA worklogs using the Tempo Timesheets API. It allows you to generate worklog templates, validate worklog files, and apply worklogs to JIRA based on a simple text file format.

## Purpose

The primary goal of this tool is to simplify the process of logging time in JIRA, especially when dealing with recurring tasks, specific project/account/component combinations, or when needing to log time based on Git commit history. It provides a text-based interface for managing worklogs, which can be version-controlled and easily edited.

## Features

*   **Text-Based Worklog Management**: Manage your JIRA worklogs in a simple `.jira` text file, which is easy to edit and can be committed to version control.
*   **Template Generation**: The `generate` command creates a worklog template for any given month, pre-populated with all your working days as fetched from Tempo.
*   **Automatic Worklogs**: Define recurring tasks (like daily scrums or weekly meetings) in your `config.toml`. These are automatically added to your monthly template, saving you repetitive data entry. The day-of-week scheduling is flexible, supporting ranges (`Mon-Fri`) and lists (`Monday, Wednesday`).
*   **Keyword Shortcuts**: Create short keywords in `config.toml` for common tasks (e.g., `meeting`, `training`). Using a keyword in your worklog file automatically expands to the correct JIRA ticket, account, and component.
*   **Project-Based Defaults**: Simplify your worklog entries by defining default `account` and `component` values for specific JIRA projects in your configuration.
*   **Smart Validation**: Before applying, the script validates your worklog file to ensure that total non-overtime hours sum to 8 for each working day and that no time is logged on non-working days.
*   **Idempotent Sync**: The `apply` command intelligently compares your local file with existing worklogs in JIRA for each day. It only performs updates (delete and add) if it detects a difference, and prompts for confirmation.
*   **Overtime Logging**: Easily log overtime hours by prefixing the hours with a `+`. Overtime entries are exempt from the daily 8-hour validation.
*   **Git Integration**: Use the `inspect` command to generate a draft worklog based on your Git commit history for a specific repository.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```
2.  **Install dependencies:**
    This script requires Python 3 and the `requests` and `toml` libraries. You can install them using pip:
    ```bash
    pip install requests toml
    ```
    *(Consider using a virtual environment)*

## Configuration

The script requires a `config.toml` file in the same directory. Create this file with the following structure:

```toml
[JIRA]
JIRA_URL = "https://your-jira-instance.atlassian.net" # Replace with your JIRA URL
API_TOKEN = "your-api-token"                          # Replace with your JIRA API Token

[user]
email = "your-email@example.com"                      # Your email address (used for git inspect)

# Define keywords for common tasks (optional)
[keyword.meeting]
ticket = "INTERNAL-123"
account = "001-GEN"
component = "Meetings"

[keyword.training]
ticket = "INTERNAL-456"
account = "001-GEN"
component = "Learning"

# Define default account/component for specific JIRA projects (optional)
[project.PROJ]
account = "002-PROJ"
component = "Project"
```

**Explanation:**

*   `[JIRA]`: Contains your JIRA instance URL and API token.
*   `[user]`: Contains your email, primarily used by the `inspect` command to filter Git commits.
*   `[keyword.*]`: Defines shortcuts. When you use a keyword (e.g., `meeting`) in your worklog file instead of a JIRA ticket, the script uses the corresponding `ticket`, `account`, and `component`.
*   `[project.*]`: Defines default `account` and `component` for tickets belonging to a specific JIRA project key (e.g., `PROJ`, `ANOTHER`). If a worklog line uses a ticket like `PROJ-123`, these defaults will be used unless overridden in the worklog line itself.

## Usage

The script is run from the command line using `python autotempo.py <command> [options]`.

**Available Commands:**

*   **`generate <YYYY-MM>`**:
    *   Generates a template worklog file named `YYYY-MM.jira` for the specified month.
    *   The template includes entries for all working days (fetched from Tempo) with a default of 8.0 hours.
    *   Example: `python autotempo.py generate 2025-05`

*   **`validate <file>`**:
    *   Validates the specified worklog file (`.jira` file).
    *   Checks for correct line format.
    *   Ensures the total non-overtime hours logged for each working day equals 8 and no non-overtime hours on non-working days.
    *   Reports errors if validation fails. Does *not* interact with JIRA beyond fetching working days.
    *   Example: `python autotempo.py validate 2025-05.jira`

*   **`apply <file>`**:
    *   Parses, validates, and applies the worklogs from the specified file to JIRA.
    *   For each valid day in the file:
        *   Fetches existing worklogs from JIRA for that day.
        *   Compares existing worklogs with the entries in the file.
        *   If differences are found, it prompts for confirmation (`yes/no`) before deleting the existing worklogs and adding the new ones from the file.
        *   If no differences are found, it skips the update for that day.
    *   Example: `python autotempo.py apply 2025-05.jira`

*   **`inspect <repo_path>`**:
    *   (Experimental) Inspects a local Git repository at the given path.
    *   Finds commits authored by the email specified in `config.toml`.
    *   Prints a potential worklog file content to the console, using commit dates, hashes as tickets, and messages as comments. *This is a helper and the output likely needs manual adjustment.*
    *   Example: `python autotempo.py inspect /path/to/my/project`

**Worklog File Format (`.jira` file):**

Each line represents a single worklog entry. Comments start with `#`.

```
# Format: date hours ticket/keyword "comment" [account:<override>] [component:<override>]
YYYY-MM-DD H.H JIRA-TICKET "Description of work"
YYYY-MM-DD H.H keyword "Comment for keyword task"
YYYY-MM-DD H.H ANOTHER-TICKET "Work on another ticket" account:SpecificAccount component:SpecificComponent
YYYY-MM-DD +2.0 JIRA-TICKET "Overtime work"
```

*   `date`: `YYYY-MM-DD` format.
*   `hours`: Floating-point number (e.g., `8.0`, `1.5`). Prefix with `+` to mark as overtime (e.g., `+2.0`), which does not count towards the daily 8-hour total.
*   `ticket/keyword`: Either a full JIRA ticket key (e.g., `PROJ-123`) or a keyword defined in `config.toml` (e.g., `meeting`).
*   `"comment"`: The worklog comment, enclosed in double quotes.
*   `[account:<override>]` (Optional): Overrides the default or keyword account.
*   `[component:<override>]` (Optional): Overrides the default or keyword component.

**Important:** The script validates that the total *non-overtime* hours for each *working day* sum up to exactly 8.0 and that no non-overtime hours are logged on non-working days before applying changes. Overtime can be logged on any day.

## Typical Workflow

1.  **Generate Template:** Start a new month by generating a template:
    ```bash
    python autotempo.py generate 2025-05
    ```
2.  **Edit Worklog File:** Open `2025-05.jira` in a text editor. Fill in the JIRA tickets or keywords, adjust hours per entry (ensuring each day totals 8 hours), and add comments. Use project/keyword defaults or overrides as needed.
3.  **Apply:** Upload the worklogs to JIRA:
    ```bash
    python autotempo.py apply 2025-05.jira
    ```
    Review the proposed changes (deletions/additions) for each day and confirm with `yes` if correct.
4.  **(Optional) Version Control:** Commit the `.jira` file to Git to keep a history of your worklogs.

```

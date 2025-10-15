# app.py
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS 
import sqlite3
import re
from datetime import datetime, timedelta
import io

# --- Configuration ---
app = Flask(__name__)
CORS(app) 
DATABASE = 'mindfulme.db'

# --- Database Helper Functions ---

def get_db_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=()):
    """Execute a query and close connection (for INSERT, UPDATE, DELETE)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    return cursor

def fetch_all(query, params=()):
    """Fetch all results (for SELECT)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- Advanced Functionality ---

def calculate_streak(habit_name):
    """Calculates the current consecutive daily streak for a habit."""
    # Fetch all logged dates for this habit, sorted newest to oldest
    logs = fetch_all(
        "SELECT date FROM activities WHERE name = ? ORDER BY date DESC", 
        (habit_name.title(),)
    )
    
    if not logs:
        return 0
    
    current_streak = 0
    
    # Start checking from yesterday. We don't penalize for missing today yet.
    # Today's date is only part of the streak if it's already logged.
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Check if the habit was logged today
    logged_dates = {datetime.strptime(row['date'], "%Y-%m-%d").date() for row in logs}
    
    if today in logged_dates:
        current_streak = 1
        check_date = yesterday
    else:
        check_date = yesterday
        current_streak = 0
        
    while True:
        if check_date in logged_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
        # Stop if we hit a date that wasn't logged, or if we go too far back
        elif check_date < today - timedelta(days=365): 
             break 
        elif check_date < today:
             break 
        else:
            break
            
    return current_streak

def export_data_to_csv():
    """Exports all activity data to a CSV formatted string."""
    logs = fetch_all("SELECT name, date, category, status FROM activities ORDER BY date DESC")
    
    if not logs:
        return None
    
    # Use StringIO to build the CSV in memory
    output = io.StringIO()
    # CSV Header
    output.write("Activity,Date,Category,Status\n")
    
    for row in logs:
        output.write(f"{row['name']},{row['date']},{row['category']},{row['status']}\n")
        
    output.seek(0)
    return output

# --- Activity/Habit Management Functions ---

def log_activity(name):
    """Logs an activity with the current date."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if already logged today (Prevent duplicates for daily habits)
    is_duplicate = fetch_all(
        "SELECT * FROM activities WHERE name = ? AND date = ?",
        (name, today)
    )
    if is_duplicate:
        return f"Activity '**{name}**' was already logged today. I've noted it, but no duplicate record was created."

    execute_query(
        "INSERT INTO activities (name, date, category, status) VALUES (?, ?, ?, ?)",
        (name, today, 'general', 'completed')
    )
    
    # Check streak after logging
    streak = calculate_streak(name)
    
    response = f"Activity '**{name}**' logged for today. Well done! 🎉"
    if streak > 1:
        response += f"<br>🔥 **Streak Alert!** Your current streak for {name} is **{streak}** days!"
        
    return response

def add_habit(name, frequency="daily"):
    """Adds a new habit to the habits table."""
    # Input Validation: Check if name is too short
    if len(name) < 3:
        return "Habit names should be descriptive. Please use at least 3 characters."
        
    try:
        execute_query("INSERT INTO habits (name, frequency) VALUES (?, ?)", (name, frequency))
        return f"Habit '**{name}**' added with a 'daily' frequency. I'll keep track! 🗓️"
    except sqlite3.IntegrityError:
        return f"Habit '**{name}**' is already in your list. Try a different name."

def show_detailed_habits():
    """Shows all habits with their current streak."""
    habits = fetch_all("SELECT name, frequency FROM habits")
    if not habits:
        return "You don't have any habits set up yet. Try '**add habit [name]**'."
    
    report = "**Your current tracked habits and progress:**<br>"
    for habit in habits:
        name = habit['name']
        streak = calculate_streak(name)
        
        report += f"- **{name}** ({habit['frequency']}) | Current Streak: **{streak}** days { '🔥' if streak > 1 else '' }<br>"
    return report

# --- Core Chatbot Logic (Rule-Based NLP) ---

def chatbot_response(user_input):
    """Processes user input and returns a relevant response based on patterns."""
    text = user_input.lower().strip()

    # 1. Export Data Intent
    if re.search(r'export|download\s+data|save\s+logs', text):
        return "export_request" # Special code to trigger download route

    # 2. Log Activity Intent 
    match_log = re.search(r'log\s+(.+)', text)
    if match_log:
        activity_name = match_log.group(1).strip().title()
        return log_activity(activity_name)

    # 3. Add Habit Intent 
    match_add_habit = re.search(r'add\s+habit\s+(.+)', text)
    if match_add_habit:
        habit_name = match_add_habit.group(1).strip().title()
        return add_habit(habit_name) 

    # 4. Check Missed Activities Intent (reusing function from previous version)
    if re.search(r'check\s+missed|analyze|report|show\s+missed', text):
        # NOTE: Using the check_missed_activities from the previous response is fine here
        # For simplicity, we'll keep the logic inline here to avoid circular imports if this was split
        habits = fetch_all("SELECT name FROM habits WHERE frequency = 'daily'")
        if not habits:
            return "You haven't set up any daily habits yet. Try adding one with '**add habit [name]**'!"
        
        missed_report = "**Analysis of Missed Daily Habits (Last 7 Days):**\n"
        missed_count = 0
        today = datetime.now().date()
        
        for habit in habits:
            habit_name = habit['name']
            for i in range(1, 8):
                check_date = today - timedelta(days=i)
                date_str = check_date.strftime("%Y-%m-%d")
                log = fetch_all("SELECT * FROM activities WHERE name = ? AND date = ?", (habit_name, date_str))
                if not log:
                    missed_report += f"- Missed **'{habit_name}'** on {date_str}.\n"
                    missed_count += 1
                    
        if missed_count == 0:
            return "✅ **All Clear!** You haven't missed any of your daily habits in the last week!"
        else:
            return missed_report.strip('\n').replace('\n', '<br>')

    # 5. Show Detailed Habits Intent
    if re.search(r'show\s+habits|what\s+are\s+my\s+habits|show\s+streaks', text):
        return show_detailed_habits()

    # 6. Greeting/Simple Chit-Chat
    if re.search(r'hi|hello|hey', text):
        return "Hello! I'm **MindfulMe v2.0**, your Advanced Activity Analyzer. I track habits, calculate streaks, and validate your data. Type '**help**' for commands or '**export data**' to download your logs."
    
    # 7. Help/Unknown Intent (Default)
    return ("I'm MindfulMe, here to help you build great habits!<br>"
            "**Enhanced Commands:**<br>"
            "1. **Log [activity name]** (e.g., 'log 1 hour of study')<br>"
            "2. **Add habit [habit name]** (e.g., 'add habit drink 8 glasses of water')<br>"
            "3. **Show habits** (Shows your habits and **streaks**!)<br>"
            "4. **Check missed** (Analyzes the last week)<br>"
            "5. **Export data** (Downloads your full log as a CSV file)")

# --- Flask Routes ---

@app.route("/")
def index():
    """Renders the main chat interface page."""
    return render_template("index.html")

@app.route("/get", methods=["POST"])
def get_bot_response():
    """API endpoint to receive user input and return bot response."""
    user_text = request.form.get("msg")
    if user_text:
        response = chatbot_response(user_text)
        
        # Check for the special 'export_request' code
        if response == "export_request":
            # Tell the frontend to trigger the download route
            return jsonify({"response": "export_trigger"})
        
        return jsonify({"response": response})
        
    return jsonify({"response": "I didn't receive your message."})

@app.route("/download_logs")
def download_logs():
    """Handles the actual CSV file download."""
    csv_data = export_data_to_csv()
    
    if csv_data is None:
        return "No data to export.", 404
    
    return send_file(
        csv_data,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'MindfulMe_Logs_{datetime.now().strftime("%Y%m%d")}.csv'
    )

if __name__ == "__main__":
    app.run(debug=True)
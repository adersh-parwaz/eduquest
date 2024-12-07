import streamlit as st
import json
import datetime
import sqlite3
import hashlib
import os
import time
import openai

# Initialize OpenAI client
openai.api_key = st.secrets["openai_api_key"]  # Set your OpenAI API key in Streamlit secrets

# Initialize session state variables
def initialize_session_state():
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    if 'current_user_id' not in st.session_state:
        st.session_state.current_user_id = None
    if 'current_user_is_admin' not in st.session_state:
        st.session_state.current_user_is_admin = False
    if 'current_topic' not in st.session_state:
        st.session_state.current_topic = None
    if 'quiz_questions' not in st.session_state:
        st.session_state.quiz_questions = []
    if 'quiz_answers' not in st.session_state:
        st.session_state.quiz_answers = []
    if 'user_answers' not in st.session_state:
        st.session_state.user_answers = []
    if 'score' not in st.session_state:
        st.session_state.score = 0
    if 'session_log' not in st.session_state:
        st.session_state.session_log = {}
    if 'sign_in_time' not in st.session_state:
        st.session_state.sign_in_time = None
    if 'quiz_start_time' not in st.session_state:
        st.session_state.quiz_start_time = None
    if 'sign_in_elapsed_time' not in st.session_state:
        st.session_state.sign_in_elapsed_time = 0
    if 'reading_start_time' not in st.session_state:
        st.session_state.reading_start_time = None
    if 'writing_start_time' not in st.session_state:
        st.session_state.writing_start_time = None
    if 'quiz_time_limit' not in st.session_state:
        st.session_state.quiz_time_limit = 5 * 60  # 5 minutes
    if 'db_connection' not in st.session_state:
        st.session_state.db_connection = None
    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0

initialize_session_state()

# Hashing function for passcodes
def hash_passcode(passcode):
    return hashlib.sha256(passcode.encode()).hexdigest()

# Set up the database
def setup_database():
    if 'db_connection' in st.session_state and st.session_state.db_connection:
        return  # Database already set up

    # Database path in a writable directory
    db_path = os.path.join('/tmp', 'learning_app.db')

    # Check if the database exists
    db_exists = os.path.exists(db_path)

    st.session_state.db_connection = sqlite3.connect(db_path, check_same_thread=False)
    cursor = st.session_state.db_connection.cursor()

    # Create users table with updated schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            passcode_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Create sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            topic TEXT,
            lesson TEXT,
            user_input TEXT,
            score INTEGER,
            time_spent REAL,
            quiz_time REAL,
            reading_time REAL,
            writing_time REAL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Create quiz_questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            question TEXT,
            options TEXT,
            correct_answer TEXT,
            user_answer TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    ''')

    # Create topics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_name TEXT UNIQUE NOT NULL,
            lesson_text TEXT,
            quiz_questions TEXT,
            approved INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Check if default admin exists
    cursor.execute("SELECT id FROM users WHERE name = 'Parent'")
    if not cursor.fetchone():
        # Create default admin user
        default_passcode = 'Learningapp12345'  # Admin passcode
        passcode_hash = hash_passcode(default_passcode)
        cursor.execute(
            "INSERT INTO users (name, passcode_hash, is_admin) VALUES (?, ?, ?)",
            ('Parent', passcode_hash, 1)
        )
        st.session_state.db_connection.commit()

    st.session_state.db_connection.commit()

def close_database():
    if 'db_connection' in st.session_state and st.session_state.db_connection:
        st.session_state.db_connection.close()
        st.session_state.db_connection = None

# Parse the quiz
def parse_quiz(text):
    questions = []
    answers = []
    lines = text.strip().split('\n')
    question_data = {}
    question_started = False
    for line in lines:
        line = line.strip()
        if line.lower().startswith('question'):
            if question_data:
                if 'question' in question_data and 'options' in question_data and 'answer' in question_data:
                    questions.append(question_data)
                question_data = {}
            question_data['question'] = line
            question_data['options'] = []
            question_started = True
        elif line.startswith(('A)', 'B)', 'C)', 'D)')) and question_started:
            question_data.setdefault('options', []).append(line)
        elif line.lower().startswith('answer:') and question_started:
            answer = line.split(':', 1)[1].strip().upper()
            question_data['answer'] = answer
            answers.append(answer)
            question_started = False
    if question_data:
        if 'question' in question_data and 'options' in question_data and 'answer' in question_data:
            questions.append(question_data)
    return questions, answers

# Sign In Function
def sign_in():
    st.subheader("Sign In")

    cursor = st.session_state.db_connection.cursor()
    cursor.execute("SELECT id, name FROM users")
    users = cursor.fetchall()

    if users:
        users_dict = {user[1]: user[0] for user in users}
        name = st.selectbox("Select User", list(users_dict.keys()))
        passcode = st.text_input("Passcode", type="password")

        if st.button("Login"):
            if name and passcode:
                cursor.execute("SELECT id, passcode_hash, is_admin FROM users WHERE name = ?", (name,))
                result = cursor.fetchone()
                if result:
                    user_id, stored_passcode_hash, is_admin = result
                    if hash_passcode(passcode) == stored_passcode_hash:
                        st.session_state.current_user = name
                        st.session_state.current_user_id = user_id
                        st.session_state.current_user_is_admin = bool(is_admin)
                        st.session_state.session_log['user'] = st.session_state.current_user
                        st.session_state.sign_in_time = time.time()
                        st.success(f"Welcome {st.session_state.current_user}!")
                        st.experimental_rerun()
                    else:
                        st.error("Incorrect passcode.")
                else:
                    st.error("User not found.")
            else:
                st.error("Please enter passcode.")
    else:
        st.error("No users found. Please contact the administrator.")

# Sign Out Function
def sign_out():
    # Calculate total time spent signed in
    time_spent = time.time() - st.session_state.sign_in_time if st.session_state.sign_in_time else 0
    st.info(f"Goodbye {st.session_state.current_user}! You spent {int(time_spent)} seconds signed in.")
    st.session_state.current_user = None
    st.session_state.current_user_id = None
    st.session_state.current_user_is_admin = False
    st.session_state.sign_in_time = None
    st.experimental_rerun()

# Admin Functions
def admin_options():
    option = st.selectbox("Select an option", ["Add User", "View All Users", "Add New Topic", "View Topics", "View All Sessions"])
    if option == "Add User":
        add_user()
    elif option == "View All Users":
        view_all_users()
    elif option == "Add New Topic":
        add_new_topic()
    elif option == "View Topics":
        view_topics()
    elif option == "View All Sessions":
        view_all_sessions()

def add_user():
    st.subheader("Add User")
    name = st.text_input("Name")
    passcode = st.text_input("Passcode", type="password")
    user_type = st.selectbox("User Type", ["Child", "Parent"])

    if st.button("Add User"):
        if name and passcode:
            cursor = st.session_state.db_connection.cursor()
            passcode_hash = hash_passcode(passcode)
            is_admin = 1 if user_type == "Parent" else 0
            try:
                cursor.execute(
                    "INSERT INTO users (name, passcode_hash, is_admin) VALUES (?, ?, ?)",
                    (name, passcode_hash, is_admin)
                )
                st.session_state.db_connection.commit()
                st.success("User added successfully.")
            except sqlite3.IntegrityError:
                st.error("Username already exists.")
        else:
            st.error("Please enter all fields.")

def view_all_users():
    st.subheader("All Users")
    cursor = st.session_state.db_connection.cursor()
    cursor.execute("SELECT id, name FROM users WHERE name != ?", (st.session_state.current_user,))
    users = cursor.fetchall()

    if users:
        user_options = {f"ID: {user[0]}, Name: {user[1]}": user[0] for user in users}
        selected_user = st.selectbox("Select a user to delete", list(user_options.keys()))
        if st.button("Delete User"):
            user_id = user_options[selected_user]
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            st.session_state.db_connection.commit()
            st.success("User deleted successfully.")
            st.experimental_rerun()
    else:
        st.info("No other users found.")

def add_new_topic():
    st.subheader("Add New Topic")
    topic_name = st.text_input("Topic Name")
    age_level = st.text_input("Age Level")
    lesson_length = st.selectbox("Desired Lesson Length", ["short", "medium", "long"])

    if st.button("Generate Content"):
        if topic_name and age_level and lesson_length:
            cursor = st.session_state.db_connection.cursor()
            try:
                # Insert the topic with approved = 0
                cursor.execute(
                    "INSERT INTO topics (topic_name, approved) VALUES (?, ?)",
                    (topic_name, 0)
                )
                st.session_state.db_connection.commit()
                topic_id = cursor.lastrowid
                generate_lesson_and_quiz_for_topic(topic_id, topic_name, age_level, lesson_length)
            except sqlite3.IntegrityError:
                st.error("Topic already exists.")
        else:
            st.error("Please enter all fields.")

def generate_lesson_and_quiz_for_topic(topic_id, topic_name, age_level, lesson_length):
    st.info("Assistant is preparing the lesson and quiz...")
    # Create a prompt for the assistant to teach the topic and create a quiz
    prompt = f"""Teach about {topic_name} in an engaging and understandable way suitable for a child of age {age_level}.
Provide a {lesson_length} lesson with headings in bold and use bullet points where appropriate to enhance understanding.

After teaching, create a 5-question multiple-choice quiz about {topic_name} suitable for a child of age {age_level}.
Provide options A), B), C), D) for each question, and indicate the correct answer in the format 'Answer: X' where X is the correct option letter.

Ensure that the quiz starts with 'Quiz:' and that each question is formatted as follows:

Question X: [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Answer: [Correct option letter]

Do not include any additional text or explanations."""

    try:
        # Fetch the lesson and quiz together
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3500
        )
        response_text = response.choices[0].message.content.strip()

        # Split the response into lesson and quiz
        if 'Quiz:' in response_text:
            lesson_text, quiz_text = response_text.split('Quiz:', 1)
            quiz_text = 'Quiz:' + quiz_text  # Add back 'Quiz:' for parsing
        else:
            lesson_text = response_text
            quiz_text = ''

        # Store the lesson and quiz in the database
        cursor = st.session_state.db_connection.cursor()
        cursor.execute('''
            UPDATE topics SET lesson_text = ?, quiz_questions = ? WHERE id = ?
        ''', (lesson_text.strip(), quiz_text.strip(), topic_id))
        st.session_state.db_connection.commit()

        # Allow admin to review and approve the topic
        review_and_approve_topic(topic_id, topic_name, lesson_text.strip(), quiz_text.strip())

    except Exception as e:
        st.error(f"An error occurred: {e}")

def review_and_approve_topic(topic_id, topic_name, lesson_text, quiz_text):
    st.subheader(f"Review Topic - {topic_name}")
    st.write("### Lesson")
    st.markdown(lesson_text)
    st.write("### Quiz")
    st.text(quiz_text)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve"):
            cursor = st.session_state.db_connection.cursor()
            cursor.execute('''
                UPDATE topics SET approved = 1 WHERE id = ?
            ''', (topic_id,))
            st.session_state.db_connection.commit()
            st.success("Topic has been approved and is now available to kids.")
            st.experimental_rerun()
    with col2:
        if st.button("Reject"):
            cursor = st.session_state.db_connection.cursor()
            cursor.execute('''
                DELETE FROM topics WHERE id = ?
            ''', (topic_id,))
            st.session_state.db_connection.commit()
            st.info("Topic has been rejected and removed.")
            st.experimental_rerun()

def view_topics():
    st.subheader("Topics")
    cursor = st.session_state.db_connection.cursor()
    cursor.execute('''
        SELECT id, topic_name, approved FROM topics
    ''')
    topics = cursor.fetchall()
    if topics:
        topic_options = {f"ID: {topic[0]}, Name: {topic[1]}, Status: {'Approved' if topic[2] else 'Pending'}": topic[0] for topic in topics}
        selected_topic = st.selectbox("Select a topic to delete", list(topic_options.keys()))
        if st.button("Delete Topic"):
            topic_id = topic_options[selected_topic]
            cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
            st.session_state.db_connection.commit()
            st.success("Topic deleted successfully.")
            st.experimental_rerun()
    else:
        st.info("No topics found.")

def view_all_sessions():
    st.subheader("All Sessions")
    cursor = st.session_state.db_connection.cursor()
    cursor.execute('''
        SELECT sessions.id, users.name, sessions.date, sessions.topic, sessions.score
        FROM sessions
        JOIN users ON sessions.user_id = users.id
        ORDER BY sessions.date DESC
    ''')
    sessions = cursor.fetchall()
    if sessions:
        for session in sessions:
            st.write(f"Session ID: {session[0]}, User: {session[1]}, Date: {session[2]}, Topic: {session[3]}, Score: {session[4]}")
            if st.button(f"View Details {session[0]}"):
                show_session_detail_by_id(session[0])
            if st.button(f"Delete Session {session[0]}"):
                cursor.execute("DELETE FROM sessions WHERE id = ?", (session[0],))
                cursor.execute("DELETE FROM quiz_questions WHERE session_id = ?", (session[0],))
                st.session_state.db_connection.commit()
                st.success("Session deleted successfully.")
                st.experimental_rerun()
    else:
        st.info("No sessions found.")

def show_session_detail_by_id(session_id):
    cursor = st.session_state.db_connection.cursor()
    cursor.execute('''
        SELECT sessions.date, sessions.topic, sessions.lesson, sessions.user_input,
        sessions.score, sessions.time_spent, sessions.quiz_time, users.name,
        sessions.reading_time, sessions.writing_time
        FROM sessions
        JOIN users ON sessions.user_id = users.id
        WHERE sessions.id = ?
    ''', (session_id,))
    session = cursor.fetchone()
    if session:
        cursor.execute('''
            SELECT question, options, correct_answer, user_answer
            FROM quiz_questions WHERE session_id = ?
        ''', (session_id,))
        quiz = cursor.fetchall()

        st.write(f"**User:** {session[7]}")
        st.write(f"**Date:** {session[0]}")
        st.write(f"**Topic:** {session[1]}")
        st.write(f"**Time Spent Signed In:** {int(session[5])} seconds")
        st.write(f"**Time Spent Reading:** {int(session[8])} seconds")
        st.write(f"**Time Spent Writing:** {int(session[9])} seconds")
        st.write(f"**Time Spent on Quiz:** {int(session[6])} seconds")
        st.write("### Lesson")
        st.markdown(session[2])
        st.write(f"### {session[7]}'s Input")
        st.markdown(session[3])
        st.write(f"**Score:** {session[4]} out of {len(quiz)}")
        st.write("### Quiz Questions and Answers")
        for q in quiz:
            options = json.loads(q[1])
            st.write(f"**{q[0]}**")
            for option in options:
                st.write(option)
            st.write(f"**Correct Answer:** {q[2]}")
            st.write(f"**{session[7]}'s Answer:** {q[3]}")
    else:
        st.error("Session details not found.")

# User Functions
def user_options():
    cursor = st.session_state.db_connection.cursor()
    cursor.execute('SELECT id, topic_name FROM topics WHERE approved = 1')
    topics = cursor.fetchall()
    if topics:
        topics_dict = {topic[1]: topic[0] for topic in topics}
        topic_name = st.selectbox("Select Topic", list(topics_dict.keys()))
        if st.button("Load Topic"):
            topic_id = topics_dict[topic_name]
            load_lesson_and_quiz(topic_id)
    else:
        st.info("No approved topics available. Please check back later.")

def load_lesson_and_quiz(topic_id):
    cursor = st.session_state.db_connection.cursor()
    cursor.execute('SELECT topic_name, lesson_text, quiz_questions FROM topics WHERE id = ?', (topic_id,))
    topic_data = cursor.fetchone()
    if topic_data:
        st.session_state.current_topic = topic_data[0]
        lesson_text = topic_data[1]
        quiz_text = topic_data[2]
        st.session_state.session_log['topic'] = st.session_state.current_topic
        st.session_state.session_log['date'] = str(datetime.date.today())
        st.session_state.session_log['lesson'] = lesson_text
        # Display the lesson
        st.subheader(f"Lesson: {st.session_state.current_topic}")
        st.markdown(lesson_text)
        # Parse the quiz questions and answers
        st.session_state.quiz_questions, st.session_state.quiz_answers = parse_quiz(quiz_text)
        st.session_state.session_log['quiz'] = st.session_state.quiz_questions
        # Start Reading Timer
        st.session_state.reading_start_time = time.time()
        # Proceed to ask the user what they learned
        ask_user_input()
    else:
        st.error("Failed to load the selected topic.")

def ask_user_input():
    st.subheader("Your Turn")
    st.write(f"{st.session_state.current_user}, please write what you learned about {st.session_state.current_topic}:")
    user_input = st.text_area("Your Input")
    if st.button("Submit"):
        if user_input.strip():
            # Calculate Reading and Writing Time
            st.session_state.session_log['reading_time'] = time.time() - st.session_state.reading_start_time
            st.session_state.writing_start_time = time.time()
            st.session_state.session_log['writing_time'] = time.time() - st.session_state.writing_start_time
            st.session_state.session_log['user_input'] = user_input.strip()
            # Proceed to start the quiz
            start_quiz()
        else:
            st.error("Please write what you learned.")

def start_quiz():
    if not st.session_state.quiz_questions:
        st.error("No quiz questions are available.")
        return
    st.session_state.quiz_start_time = time.time()
    st.session_state.user_answers = []
    st.session_state.score = 0
    quiz()

def quiz():
    st.subheader("Quiz")
    with st.form("quiz_form"):
        answers = []
        for idx, question in enumerate(st.session_state.quiz_questions):
            st.write(f"**Question {idx + 1}:** {question['question']}")
            user_answer = st.radio("Select an option:", question['options'], key=f"q{idx}")
            answers.append(user_answer)
        submitted = st.form_submit_button("Submit Quiz")
        if submitted:
            st.session_state.user_answers = answers
            calculate_score()

def calculate_score():
    st.session_state.quiz_end_time = time.time()
    quiz_time_taken = st.session_state.quiz_end_time - st.session_state.quiz_start_time
    st.session_state.session_log['quiz_time'] = quiz_time_taken

    for i in range(len(st.session_state.quiz_answers)):
        correct_option = st.session_state.quiz_answers[i].strip().upper()
        user_option = st.session_state.user_answers[i]
        selected_option_letter = user_option.split(')')[0].strip().upper()  # Extract 'A', 'B', 'C', or 'D'
        if selected_option_letter == correct_option:
            st.session_state.score += 1
    # Log the score
    st.session_state.session_log['score'] = st.session_state.score

    st.success(f"Quiz Completed! Your Score: {st.session_state.score} out of {len(st.session_state.quiz_questions)}")
    # Save the session to the database
    save_session_to_db()

def save_session_to_db():
    cursor = st.session_state.db_connection.cursor()
    # Calculate total time spent signed in
    time_spent = time.time() - st.session_state.sign_in_time if st.session_state.sign_in_time else 0
    st.session_state.session_log['time_spent'] = time_spent

    cursor.execute('''
        INSERT INTO sessions (user_id, date, topic, lesson, user_input, score, time_spent, quiz_time, reading_time, writing_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        st.session_state.current_user_id,
        st.session_state.session_log['date'],
        st.session_state.session_log['topic'],
        st.session_state.session_log['lesson'],
        st.session_state.session_log['user_input'],
        st.session_state.session_log['score'],
        st.session_state.session_log['time_spent'],
        st.session_state.session_log['quiz_time'],
        st.session_state.session_log.get('reading_time', 0),
        st.session_state.session_log.get('writing_time', 0)
    ))
    session_id = cursor.lastrowid

    # Insert quiz questions
    for i, q in enumerate(st.session_state.quiz_questions):
        cursor.execute('''
            INSERT INTO quiz_questions (session_id, question, options, correct_answer, user_answer)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            session_id,
            q['question'],
            json.dumps(q['options']),
            q['answer'],
            st.session_state.user_answers[i] if i < len(st.session_state.user_answers) else None
        ))
    st.session_state.db_connection.commit()
    st.success("Your learning session has been saved.")
    # Reset variables
    st.session_state.quiz_questions = []
    st.session_state.quiz_answers = []
    st.session_state.user_answers = []
    st.session_state.score = 0

def view_past_sessions():
    st.subheader(f"{st.session_state.current_user}'s Past Sessions")
    cursor = st.session_state.db_connection.cursor()
    cursor.execute('''
        SELECT id, date, topic, score FROM sessions WHERE user_id = ?
        ORDER BY date DESC
    ''', (st.session_state.current_user_id,))
    sessions = cursor.fetchall()
    if sessions:
        for session in sessions:
            st.write(f"Session ID: {session[0]}, Date: {session[1]}, Topic: {session[2]}, Score: {session[3]}")
            if st.button(f"View Details {session[0]}"):
                show_session_detail_by_id(session[0])
    else:
        st.info("No past sessions found.")

# Main Application
def main():
    st.title("EduQuest")

    setup_database()

    if st.session_state.current_user:
        st.sidebar.success(f"Signed in as {st.session_state.current_user}")
        if st.sidebar.button("Sign Out"):
            sign_out()
        if st.session_state.current_user_is_admin:
            admin_options()
        else:
            user_options()
            if st.button("View Past Sessions"):
                view_past_sessions()
    else:
        if st.sidebar.button("Sign In"):
            sign_in()

    # Close the database when the app closes
    # Note: Streamlit apps don't have an explicit exit point, so we rely on session state
    # to manage the database connection.

if __name__ == "__main__":
    main()
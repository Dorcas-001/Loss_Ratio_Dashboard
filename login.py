import bcrypt
from pymongo import MongoClient, errors
import streamlit as st

# MongoDB setup
mongo_uri = "mongodb://localhost:27017/"
try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client.loss_ratio
    collection = db.dashboard_users
except errors.ServerSelectionTimeoutError as err:
    st.error("Could not connect to MongoDB server. Please check your connection settings.")
    st.stop()
except Exception as e:
    st.error(f"An unexpected error occurred: {e}")
    st.stop()

# Function to authenticate user
def authenticate(username, password):
    try:
        user = collection.find_one({"username": username})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            return True
    except errors.PyMongoError as e:
        st.error(f"An error occurred while accessing the database: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
    return False

# Function to render the login page
def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if authenticate(username, password):
            st.session_state.authenticated = True
            st.session_state.current_page = "loss_ratio"
        else:
            st.error("Invalid username or password")

import streamlit as st
import json
import bcrypt
import pandas as pd
import altair as alt
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
        page_title="Eden Care Loss Ratio Dashboard",
        page_icon=Image.open("logo.png"),
        layout="wide",
        initial_sidebar_state="expanded"
    )
# Function to load users from the JSON file
def load_users():
    with open('users.json', 'r') as file:
        return json.load(file)['users']

# Function to authenticate a user
def authenticate(username, password):
    users = load_users()
    for user in users:
        if user['username'] == username and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return True
    return False

# Streamlit app
def main():
    st.title("Login Page")

    username = st.text_input("Enter username")
    password = st.text_input("Enter password", type="password")

    if st.button("Login"):
        if authenticate(username, password):
            st.success("Authentication successful")
            st.write("Welcome, {}!".format(username))
        else:
            st.error("Authentication failed")

if __name__ == "__main__":
    main()

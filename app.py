import os
import streamlit as st
import pandas as pd
import requests
import time
from dotenv import load_dotenv  
import json

# Load environment variables for local development
load_dotenv()

# --- CONFIGURATION ---
# These are the placeholder URLs for Amit's n8n workflows
N8N_FILE_PROCESSING_WEBHOOK = "https://omikun.app.n8n.cloud/webhook/25e25bf7-7a4d-4016-9091-a03ac3310f0e"
N8N_CHAT_WEBHOOK = "https://your-n8n-instance/webhook/chat"

# --- HELPER FUNCTIONS ---

@st.cache_data(ttl=60) # Cache data for 60 seconds
def load_data_from_bin():
    """
    Fetches the latest record from a JSONBin.io bin and returns it as a DataFrame.
    """
    try:
        # Get credentials from Streamlit secrets
        bin_url = st.secrets.get("JSONBIN_URL")
        access_key = st.secrets.get("JSONBIN_ACCESS_KEY")

        if not bin_url or not access_key:
            st.error("JSONBin URL or Access Key is not set in secrets.")
            return pd.DataFrame()

        headers = {'X-Access-Key': access_key}
        response = requests.get(bin_url, headers=headers)
        response.raise_for_status()

        # The actual data is in the 'record' key of the JSONBin response
        data = response.json().get('record', [])
        
        if not data:
            return pd.DataFrame()
        
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error loading data from JSONBin: {str(e)}")
        return pd.DataFrame()

def send_file_to_n8n(uploaded_file):
    """Sends the uploaded file to the n8n processing webhook."""
    try:
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        response = requests.post(N8N_FILE_PROCESSING_WEBHOOK, files=files)
        return response.status_code == 200
    except Exception:
        return False

def get_chat_response_from_n8n(history):
    """Sends chat history to the n8n chat webhook and gets a response."""
    try:
        payload = {"history": history}
        response = requests.post(N8N_CHAT_WEBHOOK, json=payload)
        response.raise_for_status()
        return response.json().get("reply", "Sorry, I encountered an error.")
    except Exception:
        return "Sorry, I couldn't connect to the bot backend."

# --- UI AND APP LOGIC ---

def handle_file_upload():
    """Callback function to handle automatic file processing when a file is uploaded."""
    uploaded_file = st.session_state.file_uploader_widget
    
    if uploaded_file is not None:
        with st.spinner("Sending document to the backend for analysis..."):
            if send_file_to_n8n(uploaded_file):
                st.success("Document sent! The dashboard will update shortly.")
                st.session_state.is_processing = True
                # Store current row count to check for updates
                df = load_data_from_bin()
                st.session_state.row_count = len(df)
                time.sleep(2) # Give a moment before the first poll
                st.rerun()
            else:
                st.error("Failed to send document. Please try again.")

st.set_page_config(page_title="FinAgent", layout="wide")

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I am FinAgent. How can I help you today?"}]

# Sidebar for navigation and file uploads
with st.sidebar:
    st.title("Navigation")
    page = st.radio("Go to", ["Chat", "Dashboard"], index=0)
    st.divider()
    
    st.header("Upload a Document")
    uploaded_file = st.file_uploader(
        "Upload an invoice, statement, or CSV",
        type=['png', 'jpg', 'jpeg', 'pdf', 'csv'],
        key="file_uploader_widget",
        on_change=handle_file_upload
    )

# --- MAIN PAGE LOGIC ---

if page == "Chat":
    st.title("FinAgent Bot 🤖")

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if user_input := st.chat_input("Ask about your finances..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.spinner("FinAgent is thinking..."):
            assistant_response = get_chat_response_from_n8n(st.session_state.messages)
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        st.rerun()

elif page == "Dashboard":
    st.title("Your Financial Dashboard 📊")

    # Asynchronous polling logic to wait for updates after an upload
    if st.session_state.get("is_processing", False):
        st.info("Backend is processing your document. The dashboard will auto-refresh with new data.")
        initial_row_count = st.session_state.get("row_count", 0)
        
        with st.spinner("Waiting for data update..."):
            for i in range(10): # Poll up to 10 times (50 seconds)
                df = load_data_from_bin()
                if len(df) > initial_row_count:
                    st.session_state.is_processing = False
                    st.cache_data.clear() # Clear cache to ensure fresh data
                    st.success("Dashboard updated!")
                    st.rerun()
                time.sleep(5)
        
        # If it's still processing after the loop
        st.warning("Processing is taking longer than usual. Data may not be up to date.")
        st.session_state.is_processing = False

    # Display the dashboard
    transactions_df = load_data_from_bin()
    
    if transactions_df.empty:
        st.info("📊 Your financial insights will appear here once data is available.")
    else:
        try:
            df = transactions_df.copy()
            df['Amount'] = pd.to_numeric(df['Amount'])
            df['Date'] = pd.to_datetime(df['Date'])
            
            st.subheader("Spending by Category")
            category_spending = df.groupby('Category')['Amount'].sum()
            st.bar_chart(category_spending)
            
            st.subheader("Spending Over Time")
            spending_over_time = df.set_index('Date').resample('D')['Amount'].sum()
            st.line_chart(spending_over_time)

        except Exception as e:
            st.error(f"Could not display charts. Error: {e}")
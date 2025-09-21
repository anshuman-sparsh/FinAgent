import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from PIL import Image  

load_dotenv()

# System prompt for FinAgent
FINAGENT_SYSTEM_PROMPT = """
You are FinAgent, a friendly and intelligent personal finance co-pilot. Your primary role is to help users understand their finances and achieve their goals based *only* on the transaction data provided to you.
Your name is FinAgent.
Your core principles are:
1.  **Data-Driven:** Base all your answers and analysis strictly on the financial data given. Do not invent or assume any information.
2.  **Simple and Clear:** Avoid financial jargon. Explain concepts in a simple, easy-to-understand way.
3.  **Encouraging and Non-Judgmental:** Always maintain a positive and supportive tone. The goal is to empower the user, not to criticize them.
4.  **Action-Oriented:** Provide practical and actionable tips when asked for advice.

**CRITICAL SAFETY INSTRUCTION:** You are an AI assistant, NOT a licensed financial advisor. You MUST NOT provide any investment advice, stock recommendations, or financial advice that requires a professional license. If a user asks for such advice, you must politely decline and state that you can only provide analysis based on their past data and for educational purposes.
"""

# 1. Imports and Configuration
st.set_page_config(page_title="FinAgent", layout="wide")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# 2. Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! I am FinAgent, your personal financial co-pilot. How can I help you today?",
        }
    ]


# 3. Sidebar Navigation
with st.sidebar:
    st.title("Navigation")
    page = st.radio("Go to", ["Chat", "Dashboard"], index=0)


# 4. Chat Section
if page == "Chat":
    st.title("FinAgent Bot 🤖")

    # File uploader and context management
    with st.sidebar:
        st.header("Document Context")
        uploaded_file = st.file_uploader(
            "Upload an invoice or statement",
            type=['png', 'jpg', 'jpeg'],
            help="The bot will remember this document for the whole conversation."
        )
        if uploaded_file:
            st.session_state.uploaded_file = uploaded_file

        if "uploaded_file" in st.session_state:
            st.info(f"In Context: `{st.session_state.uploaded_file.name}`")
            if st.button("Clear Document Context"):
                del st.session_state.uploaded_file
                st.rerun()

    # Display existing chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if user_input := st.chat_input("Ask about the document or your finances..."):
        # Append and display user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # *** CORRECTED MERGED-CONTEXT LOGIC ***
        try:
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            
            # Prepare the full conversation history for the API
            chat_history_for_api = []
            for msg in st.session_state.messages:
                role = "model" if msg["role"] == "assistant" else msg["role"]
                chat_history_for_api.append({'role': role, 'parts': [msg['content']]})
            
            # Check if a file is in context and add it to the latest message
            if "uploaded_file" in st.session_state:
                image = Image.open(st.session_state.uploaded_file)
                # Modify the last message to include the image
                last_user_message = chat_history_for_api[-1]
                last_user_message['parts'].insert(0, image) # Insert image at the beginning of parts

            # Start a chat session with the full history
            chat_session = model.start_chat(history=chat_history_for_api[:-1])
            
            # Send the final message (which may contain an image)
            final_message_parts = chat_history_for_api[-1]['parts']
            response = chat_session.send_message(final_message_parts)
            
            assistant_text = response.text

        except Exception as e:
            assistant_text = f"An error occurred: {e}"

        # Append and display assistant message
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        st.rerun()


# 5. Dashboard Section
elif page == "Dashboard":
    st.title("Your Financial Dashboard 📊")

    # Chart 1: Monthly Spending by Category (bar chart)
    spending_df = pd.DataFrame(
        {
            "Category": ["Food", "Rent", "Travel", "Utilities", "Entertainment", "Healthcare"],
            "Amount": [350, 1200, 150, 200, 120, 90],
        }
    )
    st.subheader("Monthly Spending by Category")
    st.bar_chart(spending_df.set_index("Category"))

    # Spacing
    st.markdown("\n")

    # Chart 2: Savings Over Time (line chart)
    months = pd.date_range(end=pd.Timestamp.today(), periods=6, freq="M")
    savings = np.cumsum(np.random.randint(200, 800, size=6))
    savings_df = pd.DataFrame({"Month": months.strftime("%b %Y"), "Savings": savings})
    st.subheader("Savings Over Time (Last 6 Months)")
    st.line_chart(savings_df.set_index("Month"))




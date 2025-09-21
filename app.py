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

    # File uploader
    uploaded_file = st.file_uploader(
        "Upload an invoice, statement, or CSV",
        type=['png', 'jpg', 'jpeg', 'pdf', 'csv'],
        help="Upload images, PDFs, or CSV files to ask questions about their content"
    )
    
    # Store uploaded file in session state
    if uploaded_file is not None:
        st.session_state.uploaded_file = uploaded_file
        st.success("File uploaded! You can now ask questions about it.")
    
    # Display existing chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    user_input = st.chat_input("Ask about budgeting, investments, or expenses...")

    if user_input:
        # Append and display user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Generate assistant response using Gemini Pro
        assistant_text = ""
        if not GEMINI_API_KEY:
            assistant_text = (
                "I can't reach the model because GEMINI_API_KEY isn't set. "
                "Please set the environment variable and reload the app."
            )
        else:
            try:
                model = genai.GenerativeModel("gemini-1.5-flash-latest")
                
                # Check if there's an uploaded file for multimodal conversation
                if hasattr(st.session_state, 'uploaded_file') and st.session_state.uploaded_file is not None:
                    # Multimodal conversation with uploaded file
                    content_list = [st.session_state.uploaded_file, user_input]
                    response = model.generate_content(content_list)
                else:
                    # Text-only conversation
                    # Prepare the conversation with system prompt
                    conversation = [FINAGENT_SYSTEM_PROMPT]
                    for msg in st.session_state.messages:
                        if msg["role"] == "user":
                            conversation.append(f"User: {msg['content']}")
                        elif msg["role"] == "assistant":
                            conversation.append(f"Assistant: {msg['content']}")
                    
                    # Join the conversation into a single prompt
                    full_prompt = "\n\n".join(conversation)
                    
                    response = model.generate_content(full_prompt)
                
                assistant_text = getattr(response, "text", None) or "I'm sorry, I couldn't generate a response right now."
            except Exception as e:
                assistant_text = f"There was an error contacting the model: {e}"

        # Append and display assistant message
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        with st.chat_message("assistant"):
            st.markdown(assistant_text)

        # Ensure UI updates immediately
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




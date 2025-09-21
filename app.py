import os
import streamlit as st
import pandas as pd
import requests
import time
from dotenv import load_dotenv  
import json
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns

# Load environment variables for local development
load_dotenv()

# --- CONFIGURATION ---
# These are the placeholder URLs for Amit's n8n workflows
N8N_FILE_PROCESSING_WEBHOOK = "https://omikun.app.n8n.cloud/webhook/25e25bf7-7a4d-4016-9091-a03ac3310f0e"
N8N_CHAT_WEBHOOK = "https://omikun.app.n8n.cloud/webhook/f9a9689e-7288-49e3-a11f-2ce9cd75c50e"

# --- HELPER FUNCTIONS ---

@st.cache_data(ttl=60) # Cache data for 60 seconds
def load_data_from_bin():
    """
    Fetches data from the n8n GET endpoint and returns it as a DataFrame.
    """
    try:
        # Fetch data directly from the new n8n endpoint
        response = requests.get("https://omikun.app.n8n.cloud/webhook/288a5206-4c04-44dc-bc6d-716b07840ca5")
        response.raise_for_status()

        # The endpoint returns a direct JSON array of objects
        data = response.json()
        
        if not data:
            return pd.DataFrame()
        
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error loading data from n8n endpoint: {str(e)}")
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
    """Sends ONLY the last user message to the n8n chat webhook."""
    try:
        if not history:
            return "No message to send."

        last_user_message = history[-1]['content']
        payload = {"user_message": last_user_message}
        
        response = requests.post(N8N_CHAT_WEBHOOK, json=payload)
        response.raise_for_status()

        # *** CORRECTED LOGIC STARTS HERE ***
        response_data = response.json()
        
        # Check if the response is a list and is not empty
        if isinstance(response_data, list) and response_data:
            # Get the first dictionary from the list
            first_item = response_data[0]
            # Now, get the 'output' key from that dictionary
            return first_item.get("output", "Sorry, I received a response but couldn't find the message.")
        else:
            # Handle cases where the response is not in the expected list format
            return "Sorry, the backend returned an unexpected data format."
        
    except Exception as e:
        # Added the actual error 'e' to the message for better debugging
        return f"Sorry, I couldn't connect to the bot backend. Error: {e}"

# --- UI AND APP LOGIC ---

def handle_file_upload():
    """Callback function to handle automatic file processing when a file is uploaded."""
    uploaded_file = st.session_state.file_uploader_widget
    
    if uploaded_file is not None:
        if send_file_to_n8n(uploaded_file):
            st.session_state.is_processing = True
            st.session_state.upload_success = True
            # Store current row count to check for updates
            df = load_data_from_bin()
            st.session_state.row_count = len(df)
            # Switch to Dashboard page
            st.session_state.page = 'Dashboard'
        else:
            st.session_state.upload_success = False

st.set_page_config(page_title="FinAgent", layout="wide")

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I am FinAgent. How can I help you today?"}]

if 'page' not in st.session_state:
    st.session_state.page = 'Chat'

# Sidebar for navigation and file uploads
with st.sidebar:
    st.title("Navigation")
    page = st.radio("Go to", ["Chat", "Dashboard"], index=["Chat", "Dashboard"].index(st.session_state.page), key="radio_go_to")
    st.session_state.page = page
    st.divider()
    
    st.header("Upload a Document")
    uploaded_file = st.file_uploader(
        "Upload an invoice, statement, or CSV",
        type=['png', 'jpg', 'jpeg', 'pdf', 'csv'],
        key="file_uploader_widget",
        on_change=handle_file_upload
    )

# --- MAIN PAGE LOGIC ---

if st.session_state.page == "Chat":
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

elif st.session_state.page == "Dashboard":
    st.title("Your Financial Dashboard 📊")
    
    # Refresh button at the top
    if st.button('🔄 Refresh Data'):
        st.cache_data.clear()
        st.rerun()
    
    # Show upload status messages
    if hasattr(st.session_state, 'upload_success'):
        if st.session_state.upload_success:
            st.success("Document sent! The dashboard will update shortly.")
        else:
            st.error("Failed to send document. Please try again.")
        # Clear the upload status after showing it
        del st.session_state.upload_success

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
            
            # 1. Pie Chart (Spending Breakdown)
            st.subheader("Spending Breakdown by Category")
            category_spending = df.groupby('Category')['Amount'].sum()
            fig_pie = px.pie(values=category_spending.values, names=category_spending.index, title="Spending Breakdown by Category")
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # 2. Bar Chart (Total Spending)
            st.subheader("Total Spending by Category")
            st.bar_chart(category_spending)
            
            # 3. Line Chart (Monthly Spending Over Time)
            st.subheader("Monthly Spending Over Time")
            
            # Extract unique years from the Date column and sort them
            available_years = sorted(df['Date'].dt.year.unique())
            
            # Create year selection dropdown
            selected_year = st.selectbox("Select Year", available_years)
            
            # Filter data for the selected year
            df_filtered = df[df['Date'].dt.year == selected_year]
            
            # Check if filtered data is empty
            if df_filtered.empty:
                st.warning("No spending data available for the selected year.")
            else:
                # Resample by month and sum the Amount
                monthly_spending = df_filtered.set_index('Date').resample('M')['Amount'].sum()
                st.line_chart(monthly_spending)
            
            # 4. Stacked Bar Chart (Merchant Details)
            st.subheader("Spending by Merchant within each Category")
            if 'Merchant' in df.columns:
                pivot_merchant = df.pivot_table(index='Category', columns='Merchant', values='Amount', aggfunc='sum', fill_value=0)
                st.bar_chart(pivot_merchant)
            else:
                st.info("Merchant data not available for this visualization.")
            
            # 5. Heatmap (Monthly Patterns)
            st.subheader("Monthly Spending Heatmap")
            df['Month'] = df['Date'].dt.to_period('M').astype(str)
            pivot_monthly = df.pivot_table(index='Month', columns='Category', values='Amount', aggfunc='sum', fill_value=0)
            
            # Create heatmap using seaborn and matplotlib
            plt.figure(figsize=(12, 8))
            sns.heatmap(pivot_monthly, annot=True, fmt='.0f', cmap='YlOrRd', cbar_kws={'label': 'Amount'})
            plt.title('Monthly Spending Heatmap by Category')
            plt.xlabel('Category')
            plt.ylabel('Month')
            plt.xticks(rotation=45)
            plt.yticks(rotation=0)
            plt.tight_layout()
            st.pyplot(plt)
            
            # 6. Month-over-Month Comparison
            st.divider()
            st.subheader("Month-over-Month Spending Comparison")
            
            # Get available years and set default to most recent
            available_years = sorted(df['Date'].dt.year.unique())
            default_year = available_years[-1] if available_years else None
            
            if default_year:
                # Year selection
                selected_year = st.selectbox("Select Year for Comparison", available_years, index=available_years.index(default_year))
                
                # Get available months for selected year
                year_data = df[df['Date'].dt.year == selected_year]
                available_months = sorted(year_data['Date'].dt.month.unique())
                month_names = [pd.Timestamp(year=selected_year, month=month, day=1).strftime('%B') for month in available_months]
                
                if len(available_months) >= 2:
                    # Default to most recent and second most recent months
                    default_month1 = available_months[-2]
                    default_month2 = available_months[-1]
                    
                    # Create two columns for month selection
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        month1_idx = available_months.index(default_month1)
                        selected_month1 = st.selectbox("Month 1", month_names, index=month1_idx)
                        month1_num = available_months[month_names.index(selected_month1)]
                    
                    with col2:
                        month2_idx = available_months.index(default_month2)
                        selected_month2 = st.selectbox("Month 2", month_names, index=month2_idx)
                        month2_num = available_months[month_names.index(selected_month2)]
                    
                    # Filter data for both months
                    month1_data = year_data[year_data['Date'].dt.month == month1_num]
                    month2_data = year_data[year_data['Date'].dt.month == month2_num]
                    
                    # Create side-by-side pie charts
                    col1, col2, col3 = st.columns([2, 1, 2])
                    
                    with col1:
                        if not month1_data.empty:
                            month1_spending = month1_data.groupby('Category')['Amount'].sum()
                            fig1 = px.pie(values=month1_spending.values, names=month1_spending.index, 
                                         title=f"{selected_month1} {selected_year}")
                            st.plotly_chart(fig1, use_container_width=True)
                        else:
                            st.info("No data available")
                    
                    with col2:
                        st.markdown("<div style='text-align: center; font-size: 2em; font-weight: bold; margin-top: 100px;'>Vs.</div>", 
                                  unsafe_allow_html=True)
                    
                    with col3:
                        if not month2_data.empty:
                            month2_spending = month2_data.groupby('Category')['Amount'].sum()
                            fig2 = px.pie(values=month2_spending.values, names=month2_spending.index, 
                                         title=f"{selected_month2} {selected_year}")
                            st.plotly_chart(fig2, use_container_width=True)
                        else:
                            st.info("No data available")
                    
                    # Calculate and display statistical summary
                    if not month1_data.empty and not month2_data.empty:
                        total_month1 = month1_data['Amount'].sum()
                        total_month2 = month2_data['Amount'].sum()
                        
                        # Calculate percentage difference
                        if total_month1 > 0:
                            pct_change = ((total_month2 - total_month1) / total_month1) * 100
                        else:
                            pct_change = 100 if total_month2 > 0 else 0
                        
                        # Display metric
                        st.metric(
                            label=f"Total Spending Change ({selected_month1} → {selected_month2})",
                            value=f"${total_month2:,.2f}",
                            delta=f"{pct_change:+.1f}%"
                        )
                        
                        # Category-wise comparison
                        month1_cat = month1_data.groupby('Category')['Amount'].sum()
                        month2_cat = month2_data.groupby('Category')['Amount'].sum()
                        
                        # Calculate differences
                        all_categories = set(month1_cat.index) | set(month2_cat.index)
                        category_changes = {}
                        
                        for cat in all_categories:
                            amount1 = month1_cat.get(cat, 0)
                            amount2 = month2_cat.get(cat, 0)
                            change = amount2 - amount1
                            category_changes[cat] = change
                        
                        # Find biggest increase and decrease
                        if category_changes:
                            biggest_increase = max(category_changes.items(), key=lambda x: x[1])
                            biggest_decrease = min(category_changes.items(), key=lambda x: x[1])
                            
                            summary_text = f"""
                            **Category Analysis:**
                            - **Biggest Increase:** {biggest_increase[0]} (${biggest_increase[1]:+,.2f})
                            - **Biggest Decrease:** {biggest_decrease[0]} (${biggest_decrease[1]:+,.2f})
                            """
                            st.markdown(summary_text)
                
                elif len(available_months) == 1:
                    st.warning(f"Only one month of data available for {selected_year}. Cannot perform month-over-month comparison.")
                else:
                    st.warning(f"No monthly data available for {selected_year}.")
            else:
                st.warning("No data available for comparison.")

        except Exception as e:
            st.error(f"Could not display charts. Error: {e}")
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
import datetime

# Load environment variables for local development
load_dotenv()

# --- CONFIGURATION ---
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

def page_select_callback():
    st.session_state.page = st.session_state.radio_go_to

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
    st.session_state.messages = [{"role": "assistant", "content": "Hy! I am FinAgent. Your Personal AI Powered Finance Manager. How can I help you today?"}]

if 'page' not in st.session_state:
    st.session_state.page = 'Chat'

# Sidebar for navigation and file uploads
with st.sidebar:
    st.title("Navigation")
    st.radio("Go to", ["Chat", "Dashboard"], index=["Chat", "Dashboard"].index(st.session_state.page), key="radio_go_to", on_change=page_select_callback)
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
            
            # Key Metrics
            st.header("Key Metrics")
            col1, col2, col3 = st.columns(3)
            with col1:
                total_spend = df['Amount'].sum()
                st.metric(label="Total Spend", value=f"₹{total_spend:,.2f}")
            with col2:
                unique_months = df['Date'].dt.to_period('M').nunique()
                avg_monthly = (total_spend / unique_months) if unique_months > 0 else 0
                st.metric(label="Average Monthly Spend", value=f"₹{avg_monthly:,.2f}")
            with col3:
                total_transactions = len(df)
                st.metric(label="Total Transactions", value=f"{total_transactions:,}")
            
            # Interactive monthly total metric
            select_col1, select_col2 = st.columns(2)
            with select_col1:
                kpi_years = sorted(df['Date'].dropna().dt.year.astype(int).unique().tolist())
                today = datetime.date.today()
                current_year = int(today.year)
                default_kpi_year_index = kpi_years.index(current_year) if current_year in kpi_years else (len(kpi_years) - 1 if kpi_years else 0)
                selected_kpi_year = st.selectbox("Select Year", kpi_years, index=default_kpi_year_index, key='kpi_year_select')
                selected_kpi_year = int(selected_kpi_year)
            with select_col2:
                all_months_kpi = ['January', 'February', 'March', 'April', 'May', 'June',
                                  'July', 'August', 'September', 'October', 'November', 'December']
                current_month_name = all_months_kpi[today.month - 1] if 1 <= today.month <= 12 else None
                default_kpi_month_index = (all_months_kpi.index(current_month_name) if current_month_name in all_months_kpi else (len(all_months_kpi) - 1 if all_months_kpi else 0))
                selected_kpi_month = st.selectbox("Select Month", all_months_kpi, index=default_kpi_month_index, key='kpi_month_select')
                selected_kpi_month_num = all_months_kpi.index(selected_kpi_month) + 1
            
            kpi_period_df = df[(df['Date'].dt.year == selected_kpi_year) & (df['Date'].dt.month == selected_kpi_month_num)]
            kpi_period_total = float(kpi_period_df['Amount'].sum()) if not kpi_period_df.empty else 0.0
            st.metric(label=f"Total Spend for {selected_kpi_month} {selected_kpi_year}", value=f"₹{kpi_period_total:,.2f}")
            
            st.divider()
            
            # 1. Pie Chart (Spending Breakdown)
            st.subheader("Spending Breakdown by Category")
            category_spending = df.groupby('Category')['Amount'].sum()
            fig_pie = px.pie(values=category_spending.values, names=category_spending.index, title="Spending Breakdown by Category")
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # 2. Line Chart (Monthly Spending Over Time)
            st.subheader("Monthly Spending Over Time")
            
            # Extract unique years from the Date column and sort them
            valid_years = df['Date'].dropna().dt.year.astype(int).unique()
            available_years = sorted(valid_years)
            
            # Create year selection dropdown
            current_year_line = int(datetime.date.today().year)
            default_line_year_index = available_years.index(current_year_line) if current_year_line in available_years else (len(available_years) - 1 if available_years else 0)
            selected_year = st.selectbox("Select Year", available_years, index=default_line_year_index, key='line_chart_year_select')
            selected_year = int(selected_year)
            
            # Filter data for the selected year
            df_filtered = df[df['Date'].dt.year == selected_year]
            
            # Check if filtered data is empty
            if df_filtered.empty:
                st.warning("No spending data available for the selected year.")
            else:
                # Resample by month and sum the Amount
                monthly_spending = df_filtered.set_index('Date').resample('M')['Amount'].sum()
                st.line_chart(monthly_spending)
            
            # 3. Bar Chart (Total Spending)
            st.subheader("Total Spending by Category")
            top_10_spending = category_spending.nlargest(10)
            st.bar_chart(top_10_spending)
            
            
            # Monthly sunburst chart of spending by month, then category
            st.subheader("Monthly Spending Habits")
            years_for_sunburst = sorted(df['Date'].dropna().dt.year.astype(int).unique().tolist())
            default_index = years_for_sunburst.index(2025) if 2025 in years_for_sunburst else len(years_for_sunburst) - 1
            selected_sunburst_year = st.selectbox("Select Year", years_for_sunburst, index=default_index, key='sunburst_year_select')
            selected_sunburst_year = int(selected_sunburst_year)

            year_df = df[df['Date'].dt.year == selected_sunburst_year].copy()
            if year_df.empty:
                st.warning("No spending data available for the selected year.")
            else:
                year_df['Month'] = year_df['Date'].dt.month_name()
                fig_sunburst = px.treemap(
                    year_df,
                    path=[px.Constant(f"Spending in {selected_sunburst_year}"), 'Month', 'Category'],
                    values='Amount',
                    title=f"Monthly Spending Hierarchy for {selected_sunburst_year}"
                )
                st.plotly_chart(fig_sunburst, use_container_width=True)

                # Key statistic: top spending category for the selected year
                cat_totals = year_df.groupby('Category')['Amount'].sum()
                if not cat_totals.empty:
                    top_category = cat_totals.idxmax()
                    top_amount = cat_totals.max()
                    st.metric(
                        label=f"Top Category in {selected_sunburst_year}",
                        value=f"{top_category}",
                        delta=f"₹{top_amount:,.2f}"
                    )
            
            # 6. Month-over-Month Comparison
            st.divider()
            st.subheader("Month-over-Month Spending Comparison")
            
            # Clean data and ensure integer years
            df_mom = df.dropna(subset=['Date']).copy()
            df_mom['Date'] = pd.to_datetime(df_mom['Date'])
            df_mom['Year'] = df_mom['Date'].dt.year.astype(int)
            df_mom['Month'] = df_mom['Date'].dt.month.astype(int)
            
            available_years = sorted(df_mom['Year'].unique().tolist())
            if not available_years:
                st.warning("No data available for comparison.")
            else:
                # Determine two most recent unique months across entire dataset
                unique_periods = sorted(df_mom['Date'].dt.to_period('M').unique())
                if len(unique_periods) < 2:
                    st.warning("Not enough monthly data available to compare.")
                else:
                    last_period = unique_periods[-1]
                    prev_period = unique_periods[-2]
                    default_year = int(last_period.year)
                    
                    # Year selection with clean integer options
                    selected_year = st.selectbox(
                        "Select Year for Comparison",
                        available_years,
                        index=available_years.index(default_year) if default_year in available_years else len(available_years) - 1,
                        key='mom_year_select'
                    )
                    selected_year = int(selected_year)
                    
                    # Months available within selected year
                    year_data = df_mom[df_mom['Year'] == selected_year]
                    available_months = sorted(year_data['Month'].unique().tolist())
                    if len(available_months) < 2:
                        st.warning(f"Not enough monthly data available for {selected_year} to compare.")
                    else:
                        # Determine default months within selected year
                        defaults_in_year = [p.month for p in [prev_period, last_period] if int(p.year) == selected_year]
                        if len(defaults_in_year) < 2:
                            # Fallback to last two months available in the selected year
                            default_month1, default_month2 = available_months[-2], available_months[-1]
                        else:
                            default_month1, default_month2 = defaults_in_year[0], defaults_in_year[1]
                        # Full month list for selection
                        all_months = [
                            'January', 'February', 'March', 'April', 'May', 'June',
                            'July', 'August', 'September', 'October', 'November', 'December'
                        ]
                        default_month1_idx = default_month1 - 1
                        default_month2_idx = default_month2 - 1
                        
                        # Month selectors using full list
                        col1, col2 = st.columns(2)
                        with col1:
                            selected_month1 = st.selectbox("Month 1", all_months, index=default_month1_idx, key='mom_month1_select')
                            month1_num = all_months.index(selected_month1) + 1
                        with col2:
                            selected_month2 = st.selectbox("Month 2", all_months, index=default_month2_idx, key='mom_month2_select')
                            month2_num = all_months.index(selected_month2) + 1
                        
                        # Filter data for both months
                        month1_data = year_data[year_data['Month'] == month1_num]
                        month2_data = year_data[year_data['Month'] == month2_num]
                        
                        # Create side-by-side pie charts
                        col1, col2, col3 = st.columns([2, 1, 2])
                        
                        with col1:
                            if not month1_data.empty:
                                month1_spending = month1_data.groupby('Category')['Amount'].sum()
                                fig1 = px.pie(values=month1_spending.values, names=month1_spending.index, 
                                             title=f"Month 1: {selected_month1} {selected_year}")
                                st.plotly_chart(fig1, use_container_width=True)
                            else:
                                st.info("No data available for this month")
                        
                        with col2:
                            st.markdown("<div style='text-align: center; font-size: 2em; font-weight: bold; margin-top: 100px;'>Vs.</div>", 
                                      unsafe_allow_html=True)
                        
                        with col3:
                            if not month2_data.empty:
                                month2_spending = month2_data.groupby('Category')['Amount'].sum()
                                fig2 = px.pie(values=month2_spending.values, names=month2_spending.index, 
                                             title=f"Month 2: {selected_month2} {selected_year}")
                                st.plotly_chart(fig2, use_container_width=True)
                            else:
                                st.info("No data available for this month")
                        
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
                                value=f"₹{total_month2:,.2f}",
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
                                - **Biggest Increase:** {biggest_increase[0]} (₹{biggest_increase[1]:+,.2f})
                                - **Biggest Decrease:** {biggest_decrease[0]} (₹{biggest_decrease[1]:+,.2f})
                                """
                                st.markdown(summary_text)
            
            # 7. Average Monthly Spending Habits Summary
            st.divider()
            st.subheader("Your Average Monthly Spending Habits")
            
            # Calculate total number of unique months
            unique_months = df['Date'].dt.to_period('M').nunique()
            
            # Calculate total spending across all data
            total_spending = df['Amount'].sum()
            
            # Calculate average monthly spend
            if unique_months > 0:
                average_monthly_spend = total_spending / unique_months
                
                # Display the key metric
                st.metric(
                    label="Average Monthly Spend",
                    value=f"₹{average_monthly_spend:,.2f}",
                    help=f"Based on {unique_months} months of data"
                )
                
                # Calculate average spending by category
                category_totals = df.groupby('Category')['Amount'].sum()
                category_averages = category_totals / unique_months
                
                # Get top 5 categories by average spending
                top_5_categories = category_averages.nlargest(5)
                
                # Display horizontal bar chart
                st.bar_chart(top_5_categories)
                st.caption("Top 5 categories by average monthly spending")
            else:
                st.warning("Insufficient data to calculate average monthly spending habits.")

        except Exception as e:
            st.error(f"Could not display charts. Error: {e}")
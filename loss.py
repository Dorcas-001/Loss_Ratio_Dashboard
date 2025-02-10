import streamlit as st
import matplotlib.colors as mcolors
import plotly.express as px
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from itertools import chain
from matplotlib.ticker import FuncFormatter
from datetime import datetime
import matplotlib.dates as mdates


# Centered and styled main title using inline styles
st.markdown('''
    <style>
        .main-title {
            color: #e66c37; /* Title color */
            text-align: center; /* Center align the title */
            font-size: 3rem; /* Title font size */
            font-weight: bold; /* Title font weight */
            margin-bottom: .5rem; /* Space below the title */
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1); /* Subtle text shadow */
        }
        div.block-container {
            padding-top: 2rem; /* Padding for main content */
        }
    </style>
''', unsafe_allow_html=True)

st.markdown('<h1 class="main-title">LOSS RATIO with ACTUAL CLAIMS VIEW</h1>', unsafe_allow_html=True)

# Filepaths and sheet names
filepath_premiums = "JAN-NOV 2024 GWP.xlsx"
sheet_name_new_business = "2023"
sheet_name_endorsements = "2024"

filepath_claims = "Claims.xlsx"
sheet_name1 = "2023 claims"
sheet_name2 = "2024 claims"

# Read premium data
df_2023 = pd.read_excel(filepath_premiums, sheet_name=sheet_name_new_business)
df_2024 = pd.read_excel(filepath_premiums, sheet_name=sheet_name_endorsements)

# Read claims data
dfc_2023 = pd.read_excel(filepath_claims, sheet_name=sheet_name1)
dfc_2024 = pd.read_excel(filepath_claims, sheet_name=sheet_name2)

# Concatenate premiums and claims
df_premiums = pd.concat([df_2023, df_2024])
df_claims = pd.concat([dfc_2023, dfc_2024])

# Standardize date formats
df_premiums['Start Date'] = pd.to_datetime(df_premiums['Start Date'])
df_premiums['End Date'] = pd.to_datetime(df_premiums['End Date'])
df_claims['Claim Created Date'] = pd.to_datetime(df_claims['Claim Created Date'], errors='coerce')

# Add 'Month' and 'Year' columns
df_premiums['Month'] = df_premiums['Start Date'].dt.strftime('%B')
df_premiums['Year'] = df_premiums['Start Date'].dt.year
df_claims['Month'] = df_claims['Claim Created Date'].dt.strftime('%B')
df_claims['Year'] = df_claims['Claim Created Date'].dt.year

# Rename 'Employer Name' in claims data for consistency
df_claims.rename(columns={'Employer Name': 'Client Name'}, inplace=True)


# Function to prioritize cover types and mark prioritized rows
def prioritize_and_mark(group):
    if 'Renewal' in group['Cover Type'].values:
        return group[group['Cover Type'] == 'Renewal'].assign(Is_Prioritized=True)
    elif 'New' in group['Cover Type'].values:
        return group[group['Cover Type'] == 'New'].assign(Is_Prioritized=True)
    else:
        return group.assign(Is_Prioritized=False)

# Apply prioritization and marking
premiums_grouped = df_premiums.groupby(['Client Name', 'Product', 'Year']).apply(prioritize_and_mark).reset_index(drop=True)

# Filter endorsements
endorsements = premiums_grouped[premiums_grouped['Cover Type'] == 'Endorsement']

# Merge endorsements with prioritized premiums (Renewal or New)
merged_endorsements = pd.merge(
    endorsements,
    premiums_grouped[premiums_grouped['Cover Type'].isin(['New', 'Renewal'])],
    on=['Client Name', 'Product', 'Year'],
    suffixes=('_endorsement', '_prioritized')
)

# Filter valid endorsements (within the premium period)
valid_endorsements = merged_endorsements[
    (merged_endorsements['Start Date_endorsement'] >= merged_endorsements['Start Date_prioritized']) &
    (merged_endorsements['End Date_endorsement'] <= merged_endorsements['End Date_prioritized'])
]

# Aggregate endorsement premiums
endorsement_grouped = valid_endorsements.groupby(['Client Name', 'Product', 'Year']).agg({
    'Total_endorsement': 'sum'
}).reset_index().rename(columns={'Total_endorsement': 'Endorsement Premium'})

# Merge endorsement premiums back into prioritized premiums
final_premiums = pd.merge(
    premiums_grouped,
    endorsement_grouped,
    on=['Client Name', 'Product', 'Year'],
    how='left'
)

# Calculate total premium (base + endorsements)
final_premiums['Total Premium'] = (
    final_premiums['Total'] + 
    final_premiums['Endorsement Premium'].fillna(0)
)

# Add 'Month' column
final_premiums['Month'] = final_premiums['Start Date'].dt.strftime('%B')

# Compute time-based metrics
current_date = pd.Timestamp.now()
client_product_data = final_premiums.groupby(['Client Name', 'Product', 'Year']).agg({
    'Start Date': 'min',
    'End Date': 'max',
    'Total Premium': 'sum'
}).reset_index()

client_product_data['Days Since Start'] = (current_date - client_product_data['Start Date']).dt.days
client_product_data['days_on_cover'] = (client_product_data['End Date'] - client_product_data['Start Date']).dt.days
client_product_data['Earned Premium'] = (
    client_product_data['Total Premium'] * 
    client_product_data['Days Since Start'] / 
    client_product_data['days_on_cover']
)

# Merge earned premium calculations
premiums_with_earned = pd.merge(
    final_premiums,
    client_product_data[['Client Name', 'Product', 'Year', 'Days Since Start', 'days_on_cover', 'Earned Premium']],
    on=['Client Name', 'Product', 'Year'],
    how='left'
)

# Final premium DataFrame
premiums_final = premiums_with_earned[
    ['Client Name', 'Product', 'Year', 'Start Date', 'End Date', 'Month', 'Total Premium', 
     'Endorsement Premium', 'Cover Type', 'Is_Prioritized', 'Days Since Start', 'days_on_cover', 'Earned Premium']
]

# Filter only prioritized rows for claims matching
premiums_prioritized = premiums_final[premiums_final['Is_Prioritized']].reset_index(drop=True)

# Match claims to prioritized premiums
claims_within_range = pd.merge(
    df_claims,
    premiums_prioritized[['Client Name', 'Product', 'Year', 'Start Date', 'End Date']],
    on=['Client Name', 'Product', 'Year'],
    how='inner'
)

# Filter claims that fall within the premium period
claims_within_range = claims_within_range[
    (claims_within_range['Claim Created Date'] >= claims_within_range['Start Date']) &
    (claims_within_range['Claim Created Date'] <= claims_within_range['End Date'])
]

# Aggregate claims by client-product-year
claims_aggregated = claims_within_range.groupby(['Client Name', 'Product', 'Year']).agg({
    'Claim ID': 'count',  # Number of claims
    'Claim Amount': 'sum',  # Total claim amount
    'Approved Claim Amount': 'sum'  # Approved claim amount (if available)
}).reset_index()

# Rename columns for clarity
claims_aggregated.rename(columns={
    'Claim ID': 'Number of Claims',
    'Claim Amount': 'Total Claims',
    'Approved Claim Amount': 'Approved Claims'
}, inplace=True)

# Merge claims with premiums (outer join to include all premiums, even without claims)
final_data = pd.merge(
    premiums_final,
    claims_aggregated,
    on=['Client Name', 'Product', 'Year'],
    how='outer'
)

# Fill missing values (e.g., no claims for some clients/products)
final_data['Number of Claims'] = final_data['Number of Claims'].fillna(0).astype(int)
final_data['Total Claims'] = final_data['Total Claims'].fillna(0)
final_data['Approved Claims'] = final_data['Approved Claims'].fillna(0)

final_data

df=final_data


df['Client Name'] = df['Client Name'].astype(str)
df["Client Name"] = df["Client Name"].str.upper()


# Inspect the merged DataFrame

# Sidebar styling and logo
st.markdown("""
    <style>
    .sidebar .sidebar-content {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .sidebar .sidebar-content h2 {
        color: #007BFF; /* Change this color to your preferred title color */
        font-size: 1.5em;
        margin-bottom: 20px;
        text-align: center;
    }
    .sidebar .sidebar-content .filter-title {
        color: #e66c37;
        font-size: 1.2em;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
        text-align: center;
    }
    .sidebar .sidebar-content .filter-header {
        color: #e66c37; /* Change this color to your preferred header color */
        font-size: 2.5em;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 20px;
        text-align: center;
    }
    .sidebar .sidebar-content .filter-multiselect {
        margin-bottom: 15px;
    }
    .sidebar .sidebar-content .logo {
        text-align: center;
        margin-bottom: 20px;
    }
    .sidebar .sidebar-content .logo img {
        max-width: 80%;
        height: auto;
        border-radius: 50%;
    }
            
    </style>
    """, unsafe_allow_html=True)



# Dictionary to map month names to their order
month_order = {
    "January": 1, "February": 2, "March": 3, "April": 4, 
    "May": 5, "June": 6, "July": 7, "August": 8, 
    "September": 9, "October": 10, "November": 11, "December": 12
}

# Sort months based on their order
sorted_months = sorted(df['Month'].dropna().unique(), key=lambda x: month_order[x])

df['Quarter'] = "Q" + df['Start Date'].dt.quarter.astype(str)


# Sidebar for filters
st.sidebar.header("Filters")
year = st.sidebar.multiselect("Select Year", options=sorted(df['Year'].dropna().unique()))
month = st.sidebar.multiselect("Select Month", options=sorted_months)
quarter = st.sidebar.multiselect("Select Quarter", options=sorted(df['Quarter'].dropna().unique()))
product = st.sidebar.multiselect("Select Product", options=df['Product'].unique())
cover = st.sidebar.multiselect("Select Cover Type", options=df['Cover Type'].unique())
# segment = st.sidebar.multiselect("Select Client Segment", options=df['Client Segment'].unique())
client_names = sorted(df['Client Name'].unique())
client_name = st.sidebar.multiselect("Select Client Name", options=client_names)

# Apply filters to the DataFrame
if 'Year' in df.columns and year:
    df = df[df['Year'].isin(year)]
if 'Product' in df.columns and product:
    df = df[df['Product'].isin(product)]
if 'Month' in df.columns and month:
    df = df[df['Month'].isin(month)]
if 'Cover Type' in df.columns and cover:
    df = df[df['Cover Type'].isin(cover)]

if 'Client Name' in df.columns and client_name:
    df = df[df['Client Name'].isin(client_name)]

# Determine the filter description
filter_description = ""
if year:
    filter_description += f"{', '.join(map(str, year))} "
if cover:
    filter_description += f"{', '.join(map(str, cover))} "
if product:
     filter_description += f"{', '.join(map(str, product))} "
if month:
    filter_description += f"{', '.join(month)} "
if not filter_description:
    filter_description = "All data"


# Get minimum and maximum dates for the date input
startDate = df["Start Date"].min()
endDate = df["End Date"].max()

# Define CSS for the styled date input boxes
st.markdown("""
    <style>
    .date-input-box {
        border-radius: 10px;
        text-align: left;
        margin: 5px;
        font-size: 1.2em;
        font-weight: bold;
    }
    .date-input-title {
        font-size: 1.2em;
        margin-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)



# Create 2-column layout for date inputs
col1, col2 = st.columns(2)


# Function to display date input in styled boxes
def display_date_input(col, title, default_date, min_date, max_date):
    col.markdown(f"""
        <div class="date-input-box">
            <div class="date-input-title">{title}</div>
        </div>
        """, unsafe_allow_html=True)
    return col.date_input("", default_date, min_value=min_date, max_value=max_date)

# Display date inputs
with col1:
    date1 = pd.to_datetime(display_date_input(col1, "Start Date", startDate, startDate, endDate))

with col2:
    date2 = pd.to_datetime(display_date_input(col2, "End Date", endDate, startDate, endDate))




# Handle non-finite values in 'Start Year' column
df['Year'] = df['Year'].fillna(0).astype(int)  # Replace NaN with 0 or any specific value

# Handle non-finite values in 'Start Month' column
df['Month'] = df['Month'].fillna('Unknown')

# Create a 'Month-Year' column
df['Month-Year'] = df['Month'] + ' ' + df['Year'].astype(str)

# Function to sort month-year combinations
def sort_key(month_year):
    month, year = month_year.split()
    return (int(year), month_order.get(month, 0))  # Use .get() to handle 'Unknown' month

# Extract unique month-year combinations and sort them
month_years = sorted(df['Month-Year'].unique(), key=sort_key)

# Select slider for month-year range
selected_month_year_range = st.select_slider(
    "Select Month-Year Range",
    options=month_years,
    value=(month_years[0], month_years[-1])
)

# Filter DataFrame based on selected month-year range
start_month_year, end_month_year = selected_month_year_range
start_month, start_year = start_month_year.split()
end_month, end_year = end_month_year.split()

start_index = (int(start_year), month_order.get(start_month, 0))
end_index = (int(end_year), month_order.get(end_month, 0))

# Filter DataFrame based on month-year order indices
df = df[
    df['Month-Year'].apply(lambda x: (int(x.split()[1]), month_order.get(x.split()[0], 0))).between(start_index, end_index)
]

# Function to prioritize cover types and mark prioritized rows
def prioritize_and_mark(group):
    if 'Renewal' in group['Cover Type'].values:
        return group[group['Cover Type'] == 'Renewal'].assign(Is_Prioritized=True)
    elif 'New' in group['Cover Type'].values:
        return group[group['Cover Type'] == 'New'].assign(Is_Prioritized=True)
    else:
        return group.assign(Is_Prioritized=False)

# Apply prioritization and marking
df = df.groupby(['Client Name', 'Product', 'Year']).apply(prioritize_and_mark).reset_index(drop=True)


# Current date
current_date = pd.Timestamp.now()

# Compute time-based metrics for prioritized rows
df['Days Since Start'] = (
    df.apply(lambda row: (current_date - row['Start Date']).days if row['Is_Prioritized'] else 0, axis=1)
)
df['days_on_cover'] = (
    df.apply(lambda row: (row['End Date'] - row['Start Date']).days if row['Is_Prioritized'] else 0, axis=1)
)

# Calculate Earned Premium for each row
df['Earned Premium'] = (
    df.apply(
        lambda row: (row['Total Premium'] * row['Days Since Start']) / row['days_on_cover']
        if row['Is_Prioritized'] and row['days_on_cover'] != 0 else 0,
        axis=1
    )
)



df['Loss Ratio Rate'] = (
    df.apply(
        lambda row: (row['Approved Claims'] / row['Earned Premium']) * 100 
        if row['Is_Prioritized'] and row['Earned Premium'] != 0 else 0,
        axis=1
    )
)
# Set claims metrics to 0 for non-prioritized rows
df['Number of Claims'] = df.apply(lambda row: row['Number of Claims'] if row['Is_Prioritized'] else 0, axis=1)
df['Total Claims'] = df.apply(lambda row: row['Total Claims'] if row['Is_Prioritized'] else 0, axis=1)
df['Approved Claims'] = df.apply(lambda row: row['Approved Claims'] if row['Is_Prioritized'] else 0, axis=1)

if not df.empty:
    scale = 1_000_000  # For millions

    # Filter datasets based on cover types
    df_new = df[df['Cover Type'] == 'New']
    df_renew = df[df['Cover Type'] == 'Renewal']
    df_end = df[df['Cover Type'] == 'Endorsement']
    df_combined = df[df['Cover Type'].isin(['New', 'Renewal'])]


    # Total Claim Amount (Approved Claims)
    total_claim_amount = (df["Total Claims"].sum()) / scale
    average_claim_amount = (df["Total Claims"].mean()) / scale
    average_approved_claim_amount = (df["Approved Claims"].mean()) / scale

    # Client and Claim Metrics
    total_clients = df["Client Name"].nunique()
    total_claims = df["Number of Claims"].sum()  # Sum of unique claims
    num_new = df_new["Client Name"].nunique()
    num_renew = df_renew["Client Name"].nunique()
    num_end = df_end["Client Name"].nunique()


    # Premium Metrics (includes endorsements)
    total_new_premium = (df_new["Total Premium"].sum()) / scale
    total_renew_premium = (df_renew["Total Premium"].sum()) / scale
    total_premium = (df["Total Premium"].sum()) / scale  # Only New + Renewal
    total_endorsement_premium = (df_end["Total Premium"].sum()) / scale

    # Days Metrics (only from prioritized rows)
    prioritized_df = df[df['Is_Prioritized']]
    total_days_since_start = prioritized_df["Days Since Start"].sum()
    total_days_on_cover = prioritized_df["days_on_cover"].sum()
    average_days_since_start = prioritized_df["Days Since Start"].mean() if not prioritized_df.empty else 0

    # Approved Claims Metrics
    total_approved_claim_amount = (df["Approved Claims"].sum()) / scale
    percent_approved = (total_approved_claim_amount / total_claim_amount) * 100 if total_claim_amount != 0 else 0

    # Aggregate Earned Premium (only from prioritized rows)
    total_earned_premium = (prioritized_df["Earned Premium"].sum())/scale

    # Loss Ratio Calculation (aggregate level)
    loss_ratio_amount = (
        total_approved_claim_amount / total_earned_premium if total_earned_premium != 0 else 0
    )
    df['Loss Ratio'] = (total_approved_claim_amount / total_earned_premium)

    loss_ratio = loss_ratio_amount * 100



    # Create 4-column layout for metric cards# Define CSS for the styled boxes and tooltips
    st.markdown("""
        <style>
        .custom-subheader {
            color: #e66c37;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
            padding: 10px;
            border-radius: 5px;
            display: inline-block;
        }
        .metric-box {
            padding: 10px;
            border-radius: 10px;
            text-align: center;
            margin: 10px;
            font-size: 1.2em;
            font-weight: bold;
            box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.1);
            border: 1px solid #ddd;
            position: relative;
        }
        .metric-title {
            color: #e66c37; /* Change this color to your preferred title color */
            font-size: 0.9em;
            margin-bottom: 10px;
        }
        .metric-value {
            color: #009DAE;
            font-size: 1em;
        }

        </style>
        """, unsafe_allow_html=True)


    # Function to display metrics in styled boxes with tooltips
    def display_metric(col, title, value):
        col.markdown(f"""
            <div class="metric-box">
                <div class="metric-title">{title}</div>
                <div class="metric-value">{value}</div>
            </div>
            """, unsafe_allow_html=True)


    st.markdown('<h2 class="custom-subheader">For all Sales in Numbers</h2>', unsafe_allow_html=True)
    cols1, cols2, cols3 = st.columns(3)
    display_metric(cols1, "Number of Clients", f"{total_clients:,.0f}")
    display_metric(cols2, "Number of New Business", f"{num_new:,.0f}")
    display_metric(cols3, "Number of Renewals", f"{num_renew:,.0f}")
    display_metric(cols1, "Number of Endorsements", f"{num_end:,.0f} ")
    display_metric(cols2, "Number of Claims", f"{total_claims:,.0f}")

    st.markdown('<h2 class="custom-subheader">For all Sales Amount</h2>', unsafe_allow_html=True)
    cols1, cols2, cols3 = st.columns(3)
    display_metric(cols1, "Total Premium", f"{total_premium:,.0f} M")
    display_metric(cols2, "Total New Business Premium", f"{total_new_premium:,.0f} M")
    display_metric(cols3, "Total Renewal Premium", f"{total_renew_premium:,.0f} M")
    display_metric(cols1, "Total Endorsement Premium", f"{total_endorsement_premium:,.1f} M")
    display_metric(cols2, "Total Claim Amount", f"{total_claim_amount:,.0f} M")
    display_metric(cols3, "Total Approved Claim Amount", f"{total_approved_claim_amount:,.0f} M")
    display_metric(cols1, "Average Premium per Client", f"{total_premium / total_clients:,.0f} M" if total_clients != 0 else "N/A")
    display_metric(cols2, "Percentage Approved", f"{percent_approved:,.0f} %")

    st.markdown(f'<h2 class="custom-subheader">For all Claim Amounts</h2>', unsafe_allow_html=True)
    cols1, cols2, cols3 = st.columns(3)
    display_metric(cols1, "Total Claims", f"{total_claims:,.0f}")
    display_metric(cols2, "Total Claim Amount", f"{total_claim_amount:,.0f} M")
    display_metric(cols3, "Total Approved Claim Amount", f"{total_approved_claim_amount:,.0f} M")
    display_metric(cols1, "Average Claim Amount Per Client", f"{average_claim_amount:,.0f} M")
    display_metric(cols2, "Average Approved Claim Amount Per Client", f"{average_approved_claim_amount:,.0f} M")

    st.markdown('<h2 class="custom-subheader">For Loss Ratio</h2>', unsafe_allow_html=True)
    cols1, cols2, cols3 = st.columns(3)
    display_metric(cols1, "Days Since Premium Start", f"{total_days_since_start:,.0f} days")
    display_metric(cols2, "Premium Duration (Days)", f"{total_days_on_cover:,.0f} days")
    display_metric(cols3, "Average Days Since Premium Start per Client", f"{average_days_since_start:,.0f} days")
    display_metric(cols1, "Earned Premium", f"{total_earned_premium:,.0f} M")
    display_metric(cols2, "Loss Ratio", f"{loss_ratio_amount:,.1f} M")
    display_metric(cols3, "Percentage Loss Ratio", f"{loss_ratio:,.0f} %")




 
    # Sidebar styling and logo
    st.markdown("""
        <style>
        .sidebar .sidebar-content {
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        .sidebar .sidebar-content h3 {
            color: #007BFF; /* Change this color to your preferred title color */
            font-size: 1.5em;
            margin-bottom: 20px;
            text-align: center;
        }
        .sidebar .sidebar-content .filter-title {
            color: #e66c37;
            font-size: 1.2em;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 10px;
            text-align: center;
        }
        .sidebar .sidebar-content .filter-header {
            color: #e66c37; /* Change this color to your preferred header color */
            font-size: 2.5em;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 20px;
            text-align: center;
        }
        .sidebar .sidebar-content .filter-multiselect {
            margin-bottom: 15px;
        }
        .sidebar .sidebar-content .logo {
            text-align: center;
            margin-bottom: 20px;
        }
        .sidebar .sidebar-content .logo img {
            max-width: 80%;
            height: auto;
            border-radius: 50%;
        }
                
        </style>
        """, unsafe_allow_html=True)

    cols1, cols2 = st.columns(2)

    custom_colors = ["#009DAE", "#e66c37", "#461b09", "#f8a785", "#CC3636"]

    # Function to format y-axis labels in millions
    def millions(x, pos):
        """Format values in millions for better readability."""
        return '%1.0fM' % (x * 1e-6)

    # Group by Start Date and sum the totals for Total Premium, Approved Claims, and calculate Loss Ratio
    time_series_data = df.groupby(df["Start Date"].dt.strftime("%Y-%m-%d")).agg({
        'Total Premium': 'sum',
        'Approved Claims': 'sum',
        'Earned Premium': 'sum',
        'Loss Ratio Rate': 'mean'  
    }).reset_index()

    # Rename columns for clarity
    time_series_data.rename(columns={
        "Start Date": "Date",
        "Approved Claims": "Approved Claim Amount"
    }, inplace=True)

    # Convert 'Date' back to datetime format
    time_series_data['Date'] = pd.to_datetime(time_series_data['Date'])

    with cols1:
        # Create the time series chart using Matplotlib
        fig, ax1 = plt.subplots(figsize=(10, 5))

        # Plot Total Premium, Earned Premium, and Approved Claim Amount as stacked area chart
        ax1.fill_between(time_series_data['Date'], time_series_data['Total Premium'], color=custom_colors[0], alpha=0.5, label='Total Premium')
        ax1.fill_between(time_series_data['Date'], time_series_data['Earned Premium'], color=custom_colors[1], alpha=0.5, label='Earned Premium')
        ax1.fill_between(time_series_data['Date'], time_series_data['Approved Claim Amount'], color=custom_colors[2], alpha=0.5, label='Approved Claim Amount')

        # Set x-axis and y-axis labels
        ax1.set_xlabel("Date", fontsize=10, color="gray")
        ax1.set_ylabel("Amount (M)", fontsize=10, color="gray")

        # Format y-axis to display values in millions
        ax1.yaxis.set_major_formatter(FuncFormatter(millions))

        # Rotate x-axis labels for better readability
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        plt.xticks(rotation=45, fontsize=9, color="gray")
        plt.yticks(fontsize=9, color="gray")

        # Add secondary y-axis for Loss Ratio
        ax2 = ax1.twinx()
        ax2.plot(time_series_data['Date'], time_series_data['Loss Ratio Rate'], color='#CC3636', linewidth=1, linestyle='dashed', label="Loss Ratio (%)")
        ax2.set_ylabel("Loss Ratio (%)", fontsize=10, color="gray")
        ax2.tick_params(axis='y', labelsize=9, colors="gray")

        # Remove chart borders for a cleaner look
        for spine in ax1.spines.values():
            spine.set_visible(False)
        for spine in ax2.spines.values():
            spine.set_visible(False)

        # Set title and legend
        st.markdown('<h3 class="custom-subheader">Total Premium vs Earned Premium vs Approved Claim Amount vs Loss Ratio Over Time</h3>', unsafe_allow_html=True)
        ax1.legend(loc="upper left", fontsize=9)
        ax2.legend(loc="upper right", fontsize=9)

        # Display the chart in Streamlit
        st.pyplot(fig)
    # Group data by 'Year' and calculate the sum of Total Premium, Approved Claims, and Earned Premium
    yearly_data_combined = df.groupby('Year')['Total Premium'].sum().reset_index(name='Total Premium')
    yearly_data_earned = df.groupby('Year')['Approved Claims'].sum().reset_index(name='Approved Claim Amount')
    yearly_data_endorsements = df.groupby('Year')['Earned Premium'].sum().reset_index(name='Earned Premium')

    # Merge the data frames on 'Year'
    yearly_data = pd.merge(yearly_data_combined, yearly_data_earned, on='Year', how='outer')
    yearly_data = pd.merge(yearly_data, yearly_data_endorsements, on='Year', how='outer')


    with cols2:
        # Fill NaN values with 0
        yearly_data = yearly_data.fillna(0)

        # Create the grouped bar chart for Total Premium and Endorsements
        fig_yearly_avg_premium = go.Figure()

        # Add Total Premium bar trace
        fig_yearly_avg_premium.add_trace(go.Bar(
            x=yearly_data['Year'],
            y=yearly_data['Total Premium'],
            name='Total Premium',
            textposition='inside',
            textfont=dict(color='white'),
            hoverinfo='x+y+name',
            marker_color=custom_colors[0]
        ))
        # Add Total Premium bar trace
        fig_yearly_avg_premium.add_trace(go.Bar(
            x=yearly_data['Year'],
            y=yearly_data['Earned Premium'],
            name='Earned Premium',
            textposition='inside',
            textfont=dict(color='white'),
            hoverinfo='x+y+name',
            marker_color=custom_colors[1]
        ))
        # Add Total Endorsements bar trace
        fig_yearly_avg_premium.add_trace(go.Bar(
            x=yearly_data['Year'],
            y=yearly_data['Approved Claim Amount'],
            name='Approved Claim Amount',
            textposition='inside',
            textfont=dict(color='white'),
            hoverinfo='x+y+name',
            marker_color=custom_colors[2]
        ))

        fig_yearly_avg_premium.update_layout(
            barmode='group',  # Grouped bar chart
            xaxis_title="Year",
            yaxis_title="Total Amount",
            font=dict(color='Black'),
            xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12), type='category'),
            yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            margin=dict(l=0, r=0, t=30, b=50),
            height=450
        )

        # Display the chart in Streamlit
        st.markdown('<h3 class="custom-subheader">Yearly Distribution of Total Premium, Earned Premium and Approved Claim Amount</h3>', unsafe_allow_html=True)
        st.plotly_chart(fig_yearly_avg_premium, use_container_width=True)


    # Group data by 'Year' and calculate the sum/mean of relevant metrics
    yearly_data_earned = df.groupby('Year')['Earned Premium'].sum().reset_index(name='Earned_Premium')
    yearly_data_claims = df.groupby('Year')['Approved Claims'].sum().reset_index(name='Approved_Claim_Amount')
    yearly_data_loss_ratio = df.groupby('Year')['Loss Ratio Rate'].mean().reset_index(name='Loss_Ratio_Rate')

    # Merge the data frames on the 'Year'
    yearly_data = (
        yearly_data_earned
        .merge(yearly_data_claims, on='Year', how='outer')
        .merge(yearly_data_loss_ratio, on='Year', how='outer')
    )

    # Fill NaN values with 0 for numerical columns
    yearly_data[['Earned_Premium', 'Approved_Claim_Amount']] = yearly_data[['Earned_Premium', 'Approved_Claim_Amount']].fillna(0)
    yearly_data['Loss_Ratio_Rate'] = yearly_data['Loss_Ratio_Rate'].fillna(0)

    with cols1:
            
        # Create a subplot with dual y-axes
        fig_yearly_distribution = make_subplots(specs=[[{"secondary_y": True}]])  # Secondary y-axis for Loss Ratio Rate

        # Add Earned Premium bar trace (on primary y-axis)
        fig_yearly_distribution.add_trace(go.Bar(
            x=yearly_data['Year'],
            y=yearly_data['Earned_Premium'],
            name='Earned Premium',
            text=yearly_data['Earned_Premium'].apply(lambda x: f"${x / 1_000_000:.1f}M"),
            textposition='outside',  # Display values outside the bars
            textfont=dict(color='black', size=12),
            marker_color=custom_colors[0],
            offsetgroup=0
        ), secondary_y=False)

        # Add Approved Claim Amount bar trace (on primary y-axis)
        fig_yearly_distribution.add_trace(go.Bar(
            x=yearly_data['Year'],
            y=yearly_data['Approved_Claim_Amount'],
            name='Approved Claim Amount',
            text=yearly_data['Approved_Claim_Amount'].apply(lambda x: f"${x / 1_000_000:.1f}M"),
            textposition='outside',  # Display values outside the bars
            textfont=dict(color='black', size=12),
            marker_color=custom_colors[1],
            offsetgroup=1
        ), secondary_y=False)

        # Add Loss Ratio Rate line trace (on secondary y-axis)
        fig_yearly_distribution.add_trace(go.Scatter(
            x=yearly_data['Year'],
            y=yearly_data['Loss_Ratio_Rate'],  # Loss Ratio Rate on secondary y-axis
            name='Loss Ratio Rate (%)',
            mode='lines+markers+text',
            text=yearly_data['Loss_Ratio_Rate'].apply(lambda x: f"{x:.1f}%"),  # Format as percentage
            textposition='top center',  # Display values above the line
            textfont=dict(color='black', size=12),
            line=dict(color=custom_colors[2], width=2),
            marker=dict(size=8, color=custom_colors[2]),
            hoverinfo='x+y+name'
        ), secondary_y=True)

        # Update layout for grouped bars and dual axes
        fig_yearly_distribution.update_layout(
            barmode='group',  # Grouped bar chart
            xaxis_title="Year",
            yaxis_title="Amount (M)",
            font=dict(color='Black'),
            xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12), type='category'),
            yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            margin=dict(l=0, r=0, t=50, b=50),
            height=500,
            legend=dict(x=0.01, y=1.1, orientation="h")  # Place legend above the chart
        )

        # Set secondary y-axis for Loss Ratio Rate
        fig_yearly_distribution.update_yaxes(
            title_text="Loss Ratio Rate (%)",
            secondary_y=True,
            title_font=dict(size=14),
            tickfont=dict(size=12),
            range=[0, max(yearly_data['Loss_Ratio_Rate']) * 1.2]  # Adjust range dynamically
        )

        # Rotate x-axis labels for better readability
        fig_yearly_distribution.update_xaxes(tickangle=45)

        # Display the chart in Streamlit
        st.markdown('<h3 class="custom-subheader">Yearly Distribution of Earned Premium, Approved Claims, and Loss Ratio Rate</h3>', unsafe_allow_html=True)
        st.plotly_chart(fig_yearly_distribution, use_container_width=True)


    # Group data by 'Month' and calculate the sum/mean of relevant metrics
    monthly_data_earned = df.groupby('Month')['Earned Premium'].sum().reset_index(name='Earned_Premium')
    monthly_data_claims = df.groupby('Month')['Approved Claims'].sum().reset_index(name='Approved_Claim_Amount')
    monthly_data_loss_ratio = df.groupby('Month')['Loss Ratio Rate'].mean().reset_index(name='Loss_Ratio_Rate')

    # Merge the data frames on the 'Month'
    monthly_data = (
        monthly_data_earned
        .merge(monthly_data_claims, on='Month', how='outer')
        .merge(monthly_data_loss_ratio, on='Month', how='outer')
    )

    # Fill NaN values with 0 for numerical columns
    monthly_data[['Earned_Premium', 'Approved_Claim_Amount']] = monthly_data[['Earned_Premium', 'Approved_Claim_Amount']].fillna(0)
    monthly_data['Loss_Ratio_Rate'] = monthly_data['Loss_Ratio_Rate'].fillna(0)

    with cols2:
        # Create a subplot with dual y-axes
        fig_monthly_distribution = make_subplots(specs=[[{"secondary_y": True}]])  # Secondary y-axis for Loss Ratio Rate

        # Add Earned Premium bar trace (on primary y-axis)
        fig_monthly_distribution.add_trace(go.Bar(
            x=monthly_data['Month'],
            y=monthly_data['Earned_Premium'],
            name='Earned Premium',
            text=monthly_data['Earned_Premium'].apply(lambda x: f"${x / 1_000_000:.1f}M"),
            textposition='outside',  # Display values outside the bars
            textfont=dict(color='black', size=12),
            marker_color=custom_colors[0],
            offsetgroup=0
        ), secondary_y=False)

        # Add Approved Claim Amount bar trace (on primary y-axis)
        fig_monthly_distribution.add_trace(go.Bar(
            x=monthly_data['Month'],
            y=monthly_data['Approved_Claim_Amount'],
            name='Approved Claim Amount',
            text=monthly_data['Approved_Claim_Amount'].apply(lambda x: f"${x / 1_000_000:.1f}M"),
            textposition='outside',  # Display values outside the bars
            textfont=dict(color='black', size=12),
            marker_color=custom_colors[1],
            offsetgroup=1
        ), secondary_y=False)

        # Add Loss Ratio Rate line trace (on secondary y-axis)
        fig_monthly_distribution.add_trace(go.Scatter(
            x=monthly_data['Month'],
            y=monthly_data['Loss_Ratio_Rate'],  # Loss Ratio Rate on secondary y-axis
            name='Loss Ratio Rate (%)',
            mode='lines+markers+text',
            text=monthly_data['Loss_Ratio_Rate'].apply(lambda x: f"{x:.1f}%"),  # Format as percentage
            textposition='top center',  # Display values above the line
            textfont=dict(color='black', size=12),
            line=dict(color=custom_colors[2], width=2),
            marker=dict(size=8, color=custom_colors[2]),
            hoverinfo='x+y+name'
        ), secondary_y=True)

        # Update layout for grouped bars and dual axes
        fig_monthly_distribution.update_layout(
            barmode='group',  # Grouped bar chart
            xaxis_title="Month",
            yaxis_title="Amount (M)",
            font=dict(color='Black'),
            xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12), type='category'),
            yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            margin=dict(l=0, r=0, t=50, b=50),
            height=500,
            legend=dict(x=0.01, y=1.1, orientation="h")  # Place legend above the chart
        )

        # Set secondary y-axis for Loss Ratio Rate
        fig_monthly_distribution.update_yaxes(
            title_text="Loss Ratio Rate (%)",
            secondary_y=True,
            title_font=dict(size=14),
            tickfont=dict(size=12),
            range=[0, max(monthly_data['Loss_Ratio_Rate']) * 1.2]  # Adjust range dynamically
        )

        # Rotate x-axis labels for better readability
        fig_monthly_distribution.update_xaxes(tickangle=45)

        # Display the chart in Streamlit
        st.markdown('<h3 class="custom-subheader">Monthly Distribution of Earned Premium, Approved Claims, and Loss Ratio Rate</h3>', unsafe_allow_html=True)
        st.plotly_chart(fig_monthly_distribution, use_container_width=True)


    cols1, cols2 = st.columns(2)
    # Group by product and calculate the mean loss ratio
    product_data = df.groupby('Product')['Loss Ratio Rate'].mean().reset_index(name='Loss_Ratio_Rate')

    with cols1:
        # Create a bar chart
        fig_loss_ratio_by_product = go.Figure()

        for idx, (product, loss_ratio) in enumerate(zip(product_data['Product'], product_data['Loss_Ratio_Rate'])):
            fig_loss_ratio_by_product.add_trace(go.Bar(
                x=[product],  # Single product per trace to allow individual coloring
                y=[loss_ratio],
                name=product,  # Product name in legend
                text=f"{loss_ratio:.1f}%",
                textposition='outside',
                marker_color=custom_colors[idx % len(custom_colors)]  # Cycle through custom colors
            ))

        # Update layout
        fig_loss_ratio_by_product.update_layout(
            xaxis_title="Product",
            yaxis_title="Loss Ratio Rate (%)",
            font=dict(color='Black'),
            xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            margin=dict(l=0, r=0, t=50, b=50),
            height=500
        )

        st.markdown('<h3 class="custom-subheader">Loss Ratio Rate by Product</h3>', unsafe_allow_html=True)
        st.plotly_chart(fig_loss_ratio_by_product, use_container_width=True)

    # Group by client and calculate the mean loss ratio
    client_data = df.groupby('Client Name')['Loss Ratio Rate'].mean().reset_index(name='Loss_Ratio_Rate')

    # Sort by loss ratio rate for better visualization
    client_data = client_data.sort_values(by='Loss_Ratio_Rate', ascending=False).head(10)
    
    with cols2:

        # Create a bar chart
        fig_loss_ratio_by_client = go.Figure()

        fig_loss_ratio_by_client.add_trace(go.Bar(
            x=client_data['Client Name'],
            y=client_data['Loss_Ratio_Rate'],
            name='Loss Ratio Rate (%)',
            text=client_data['Loss_Ratio_Rate'].apply(lambda x: f"{x:.1f}%"),
            textposition='outside',
            marker_color='#009DAE'
        ))

        # Update layout
        fig_loss_ratio_by_client.update_layout(
            xaxis_title="Client Name",
            yaxis_title="Loss Ratio Rate (%)",
            font=dict(color='Black'),
            xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12), tickangle=45),
            yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            margin=dict(l=0, r=0, t=50, b=50),
            height=500,
        )
        st.markdown('<h3 class="custom-subheader">Top 10 Employer Groups by Loss Ratio Rate"</h3>', unsafe_allow_html=True)
        st.plotly_chart(fig_loss_ratio_by_client, use_container_width=True)
    
    with cols1:

        # Create a scatter plot
        fig_loss_vs_premium = go.Figure()

        fig_loss_vs_premium.add_trace(go.Scatter(
            x=df['Earned Premium'],
            y=df['Loss Ratio Rate'],
            mode='markers',
            name='Loss Ratio vs Earned Premium',
            marker=dict(color='#009DAE', size=10),
            text=df.apply(lambda row: f"Year: {row['Year']}<br>Product: {row['Product']}", axis=1),
            hoverinfo='text+x+y'
        ))

        # Update layout
        fig_loss_vs_premium.update_layout(
            xaxis_title="Earned Premium (M)",
            yaxis_title="Loss Ratio Rate (%)",
            font=dict(color='Black'),
            xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            margin=dict(l=0, r=0, t=50, b=50),
            height=500,
        )
        st.markdown('<h3 class="custom-subheader">Loss Ratio Rate vs Earned Premium"</h3>', unsafe_allow_html=True)
        st.plotly_chart(fig_loss_vs_premium, use_container_width=True)

    with cols2:
        # Pivot the data to create a heatmap
        heatmap_data = df.pivot_table(
            index='Year',
            columns='Product',
            values='Loss Ratio Rate',
            aggfunc='mean'
        ).fillna(0)

        # Create a heatmap
        fig_loss_heatmap = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='RdBu',
            colorbar=dict(title="Loss Ratio Rate (%)"),
            text=heatmap_data.applymap(lambda x: f"{x:.1f}%"),
            hoverinfo='text+z'
        ))

        # Update layout
        fig_loss_heatmap.update_layout(
            xaxis_title="Product",
            yaxis_title="Year",
            font=dict(color='Black'),
            xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
            margin=dict(l=0, r=0, t=50, b=50),
            height=500,
        )
        st.markdown('<h3 class="custom-subheader">Loss Ratio Rate Heatmap by Year and Product"</h3>', unsafe_allow_html=True)

        st.plotly_chart(fig_loss_heatmap, use_container_width=True)
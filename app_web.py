# app_web.py - Complete Streamlit Web Application
import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import calendar
import json
from io import BytesIO, StringIO
import base64
import plotly.express as px
import plotly.graph_objects as go

# Page config
st.set_page_config(
    page_title="EOBI Wage & Pension Calculation System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
APP_TITLE = "EOBI Wage & Pension Calculation System"
APP_VERSION = "Web Edition v6.0"
SCHEME_START_DATE = datetime(1976, 7, 1)
MIN_PENSION = 11500
OAP_REQUIRED_YEARS = 14.5
OAG_PARTIAL_YEAR_MONTHS = 6
SURVIVOR_CONTINUOUS_MONTHS = 36
SURVIVOR_REQUIRED_YEARS_BEFORE_60 = 5
SURVIVOR_REQUIRED_YEARS_AFTER_60 = 15
DAYS_IN_SERVICE_YEAR = 365.0

# Rate table
rates = [
    ('1976-07','1985-06',1000),('1985-07','1993-09',1500),
    ('1993-10','2001-06',3000),('2001-07','2005-06',3000),
    ('2005-07','2006-06',3000),('2006-07','2007-06',4000),
    ('2007-07','2008-06',4600),('2008-07','2010-06',6000),
    ('2010-07','2012-06',7000),('2012-07','2013-06',8000),
    ('2013-07','2014-06',10000),('2014-07','2015-06',12000),
    ('2015-07','2016-06',13000),('2016-07','2017-06',14000),
    ('2017-07','2018-06',15000),('2018-07','2019-06',16500),
    ('2019-07','2021-06',17500),('2021-07','2022-06',20000),
    ('2022-07','2023-06',25000),('2023-07','2024-06',32000),
    ('2024-07','2025-06',37000),('2025-07','2026-06',40000)
]

rate_dates = [(datetime.strptime(f,"%Y-%m"), datetime.strptime(t,"%Y-%m"), w) for f,t,w in rates]

def get_min(date_str):
    d = datetime.strptime(date_str, "%Y-%m")
    for f, t, w in rate_dates:
        if f <= d <= t:
            return w
    return 0

def add_month(date_obj):
    if date_obj.month == 12:
        return date_obj.replace(year=date_obj.year + 1, month=1)
    return date_obj.replace(month=date_obj.month + 1)

def get_month_key_from_date(date_obj):
    return f"{date_obj.year}-{str(date_obj.month).zfill(2)}"

def normalize_date_to_month(date_obj):
    return date_obj.replace(day=1)

def iter_month_starts(from_date, to_date):
    current = normalize_date_to_month(from_date)
    end_month = normalize_date_to_month(to_date)
    while current <= end_month:
        yield current
        current = add_month(current)

def service_years_from_days(days):
    return round(days / DAYS_IN_SERVICE_YEAR, 4) if days > 0 else 0.0

def get_days_in_month(year, month):
    return calendar.monthrange(year, month)[1]

def get_wage_status_label(month_key, wage):
    min_wage = get_min(month_key)
    if wage == 0:
        return "No Contribution"
    if min_wage and wage < min_wage:
        return "Lesser Rate"
    if min_wage and wage == min_wage:
        return "Minimum Wage"
    return "Above Minimum"

# Initialize session state
if 'employers' not in st.session_state:
    st.session_state.employers = []
if 'wages' not in st.session_state:
    st.session_state.wages = {}
if 'employment_periods' not in st.session_state:
    st.session_state.employment_periods = []
if 'temporary_changes' not in st.session_state:
    st.session_state.temporary_changes = {}
if 'selected_employer' not in st.session_state:
    st.session_state.selected_employer = None
if 'claimant_name' not in st.session_state:
    st.session_state.claimant_name = ""
if 'father_name' not in st.session_state:
    st.session_state.father_name = ""
if 'eobi_no' not in st.session_state:
    st.session_state.eobi_no = ""
if 'cnic_no' not in st.session_state:
    st.session_state.cnic_no = ""
if 'claim_type' not in st.session_state:
    st.session_state.claim_type = "self"
if 'survivor_type' not in st.session_state:
    st.session_state.survivor_type = "died_during_service"
if 'death_date' not in st.session_state:
    st.session_state.death_date = None
if 'work_percentage' not in st.session_state:
    st.session_state.work_percentage = 100
if 'remarks' not in st.session_state:
    st.session_state.remarks = ""
if 'calculation_results' not in st.session_state:
    st.session_state.calculation_results = None
if 'calculated_records' not in st.session_state:
    st.session_state.calculated_records = []
if 'yearly_data' not in st.session_state:
    st.session_state.yearly_data = []

# Load initial data
@st.cache_data
def load_employers():
    try:
        df = pd.read_csv("employer list.csv", encoding='utf-8', low_memory=False)
        df.columns = df.columns.str.lower()
        df = df.drop_duplicates(subset=['main code', 'sub code'])
        employers = []
        for _, r in df.iterrows():
            main_code = str(r['main code']).strip() if pd.notna(r['main code']) else ''
            sub_code = str(r['sub code']).strip() if pd.notna(r['sub code']) else ''
            name = str(r['name of establishment']).strip() if pd.notna(r['name of establishment']) else ''
            city = str(r.get('city', '')).strip() if pd.notna(r.get('city', '')) else ''
            app = str(r.get('date of applicability of act', '')).strip() if pd.notna(r.get('date of applicability of act', '')) else ''
            beat = str(r.get('beat', '')).strip() if pd.notna(r.get('beat', '')) else ''
            employers.append({
                'main_code': main_code,
                'sub_code': sub_code,
                'name': name,
                'city': city,
                'applicability': app,
                'beat': beat
            })
        return employers
    except Exception as e:
        return []

if not st.session_state.employers:
    st.session_state.employers = load_employers()

# ---- Main UI ----
st.title(f"{APP_TITLE}")
st.caption(f"{APP_VERSION} - EOBI Wage & Pension Calculator | Special thanks to Mr. Nasrullah Shah")

# Sidebar
with st.sidebar:
    st.header("📊 Navigation")
    tab = st.radio("Select Section", ["Search Employer", "Manage Wages", "Calculate", "Reports", "Records"])
    
    st.divider()
    st.subheader("👤 Claimant Details")
    st.session_state.claimant_name = st.text_input("Claimant Name", value=st.session_state.claimant_name)
    st.session_state.father_name = st.text_input("Father's Name", value=st.session_state.father_name)
    st.session_state.eobi_no = st.text_input("EOBI No", value=st.session_state.eobi_no)
    st.session_state.cnic_no = st.text_input("CNIC No", value=st.session_state.cnic_no)
    
    st.divider()
    st.subheader("📋 Claim Type")
    claim_type = st.radio("Select Claim Type", ["Insured Person (Self)", "Survivor"], 
                         index=0 if st.session_state.claim_type == "self" else 1)
    st.session_state.claim_type = "self" if claim_type == "Insured Person (Self)" else "survivor"
    
    if st.session_state.claim_type == "survivor":
        st.session_state.death_date = st.date_input("Death Date", 
                                                   value=datetime.now().date() if not st.session_state.death_date else st.session_state.death_date,
                                                   format="DD/MM/YYYY")
        survivor_type_options = {
            "died_during_service": "Died during service before 60",
            "died_not_in_service": "Died before 60 not in service",
            "died_after_60": "Died after 60"
        }
        selected_label = st.selectbox("Death Circumstances", 
                                     list(survivor_type_options.values()),
                                     index=0)
        for key, label in survivor_type_options.items():
            if label == selected_label:
                st.session_state.survivor_type = key
                break
        
        st.caption("📌 Eligibility Rules:")
        st.caption("• Died during service before 60: 36 continuous paid months OR 5 paid service years")
        st.caption("• Died before 60 not in service: 5 paid service years")
        st.caption("• Died after 60: 15 paid service years")

# ---- Tabs ----
if tab == "Search Employer":
    st.header("🔍 Search Employer")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("Search by Name or Code", placeholder="Type to search...")
    with col2:
        st.write("")
        if st.button("🔄 Refresh List"):
            st.cache_data.clear()
            st.session_state.employers = load_employers()
            st.rerun()
    
    filtered = st.session_state.employers
    if search_term:
        filtered = [e for e in filtered if search_term.lower() in e['name'].lower() or search_term.lower() in e['main_code'].lower()]
    
    st.write(f"Found {len(filtered)} employer(s)")
    
    if filtered:
        df = pd.DataFrame(filtered)
        st.dataframe(df, use_container_width=True, height=400)
        
        selected = st.selectbox("Select Employer", 
                               [f"{e['name']} ({e['main_code']}-{e['sub_code']})" for e in filtered],
                               key="employer_select")
        if selected:
            parts = selected.split("(")
            code_part = parts[1].replace(")", "")
            main_code, sub_code = code_part.split("-")
            for e in filtered:
                if e['main_code'] == main_code and e['sub_code'] == sub_code:
                    st.session_state.selected_employer = e
                    break
            st.success(f"✅ Selected: {st.session_state.selected_employer['name']}")
            
            # Show quick stats
            emp = st.session_state.selected_employer
            key_prefix = f"{emp['main_code']}|{emp['sub_code']}|"
            emp_wages = {k: v for k, v in st.session_state.wages.items() if k.startswith(key_prefix)}
            if emp_wages:
                st.info(f"📊 {len(emp_wages)} wage records found for this employer")
            else:
                st.warning("No wage records found for this employer. Go to 'Manage Wages' to add.")
    else:
        st.info("No employers found. Make sure employer list.csv is in the directory.")

elif tab == "Manage Wages":
    st.header("💰 Manage Wages")
    
    if st.session_state.selected_employer:
        emp = st.session_state.selected_employer
        st.subheader(f"Employer: {emp['name']} ({emp['main_code']}-{emp['sub_code']})")
        
        # Wage entry form
        with st.expander("➕ Add New Wage Record", expanded=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                wage_month = st.date_input("Month", datetime.now().replace(day=1), format="DD/MM/YYYY")
            with col2:
                wage_amount = st.number_input("Wage (PKR) - 0 = No Contribution", min_value=0.0, step=100.0, value=0.0)
            with col3:
                st.write("")
                st.write("")
                if st.button("Add Record", type="primary"):
                    key = f"{emp['main_code']}|{emp['sub_code']}|{wage_month.strftime('%Y-%m')}"
                    st.session_state.wages[key] = wage_amount
                    st.success(f"✅ Added wage for {wage_month.strftime('%B %Y')}: Rs. {wage_amount:,.2f}")
                    st.rerun()
        
        # Auto-add minimum wages
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Auto-Add Minimum Wages"):
                start = SCHEME_START_DATE
                if emp['applicability']:
                    try:
                        app_date = datetime.strptime(emp['applicability'], "%d-%b-%y")
                        if app_date > start:
                            start = app_date
                    except:
                        pass
                start = normalize_date_to_month(start)
                end = normalize_date_to_month(datetime.now())
                added = 0
                current = start
                while current <= end:
                    key = f"{emp['main_code']}|{emp['sub_code']}|{current.strftime('%Y-%m')}"
                    min_wage = get_min(current.strftime("%Y-%m"))
                    if min_wage > 0 and key not in st.session_state.wages:
                        st.session_state.wages[key] = min_wage
                        added += 1
                    current = add_month(current)
                st.success(f"✅ Added {added} minimum wage records.")
                st.rerun()
        
        # Display existing wages
        st.subheader("📋 Existing Wages")
        emp_wages = []
        for key, wage in st.session_state.wages.items():
            main, sub, month = key.split("|")
            if main == emp['main_code'] and sub == emp['sub_code']:
                d = datetime.strptime(month, "%Y-%m")
                status = get_wage_status_label(month, wage)
                emp_wages.append({
                    'Month': d.strftime('%B %Y'),
                    'Wage': f"Rs. {wage:,.2f}",
                    'Status': status,
                    'Key': key
                })
        
        if emp_wages:
            df_wages = pd.DataFrame(emp_wages)
            st.dataframe(df_wages[['Month', 'Wage', 'Status']], use_container_width=True)
            
            # Delete option
            delete_key = st.selectbox("Select record to delete", [w['Key'] for w in emp_wages])
            if st.button("🗑️ Delete Selected Record", type="secondary"):
                if delete_key in st.session_state.wages:
                    del st.session_state.wages[delete_key]
                    st.success("Record deleted!")
                    st.rerun()
        else:
            st.info("No wages added for this employer yet.")
    else:
        st.warning("⚠️ Please select an employer first in the Search tab.")

elif tab == "Calculate":
    st.header("📊 Calculation")
    
    # Employment periods
    st.subheader("📅 Employment Periods")
    
    col1, col2 = st.columns(2)
    with col1:
        period_from = st.date_input("Period From", datetime(2000, 1, 1), format="DD/MM/YYYY")
    with col2:
        period_to = st.date_input("Period To", datetime.now(), format="DD/MM/YYYY")
    
    if st.button("➕ Add Employment Period", type="primary"):
        if period_from <= period_to:
            if period_from < SCHEME_START_DATE:
                st.error(f"Period cannot start before {SCHEME_START_DATE.strftime('%d/%m/%Y')}")
            else:
                st.session_state.employment_periods.append({
                    'from': period_from,
                    'to': period_to
                })
                st.success(f"✅ Added period: {period_from.strftime('%d/%m/%Y')} to {period_to.strftime('%d/%m/%Y')}")
                st.rerun()
        else:
            st.error("From date must be before To date")
    
    # Display periods
    if st.session_state.employment_periods:
        st.write("**Current Periods:**")
        for i, p in enumerate(st.session_state.employment_periods):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                days = (p['to'] - p['from']).days + 1
                st.write(f"Period {i+1}: {p['from'].strftime('%d/%m/%Y')} - {p['to'].strftime('%d/%m/%Y')} ({days} days)")
            with col2:
                st.write("")
            with col3:
                if st.button(f"Remove", key=f"remove_{i}"):
                    del st.session_state.employment_periods[i]
                    st.rerun()
        
        # Total days
        total_days = sum((p['to'] - p['from']).days + 1 for p in st.session_state.employment_periods)
        st.info(f"📊 Total Period Days: {total_days}")
    else:
        st.info("No employment periods added. Add a period to start calculation.")
    
    st.divider()
    
    # Work percentage
    st.subheader("⚙️ Work Percentage")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.session_state.work_percentage = st.slider("Work Percentage", 1, 100, st.session_state.work_percentage)
    with col2:
        total_days = sum((p['to'] - p['from']).days + 1 for p in st.session_state.employment_periods) if st.session_state.employment_periods else 0
        actual_days = int(total_days * st.session_state.work_percentage / 100)
        st.metric("Actual Work Days", actual_days)
    
    st.session_state.remarks = st.text_area("📝 Remarks (Optional)", value=st.session_state.remarks)
    
    # Calculate button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🚀 Calculate Wages", type="primary", use_container_width=True):
            if not st.session_state.employment_periods:
                st.error("Please add at least one employment period")
            else:
                results = perform_calculation()
                st.session_state.calculation_results = results
                st.session_state.yearly_data = results['yearly_data']
                st.success("✅ Calculation complete!")
                st.rerun()
    
    with col2:
        if st.button("🔄 Clear Results", use_container_width=True):
            st.session_state.calculation_results = None
            st.session_state.yearly_data = []
            st.rerun()
    
    # Display results
    if st.session_state.calculation_results:
        res = st.session_state.calculation_results
        
        st.divider()
        st.subheader("📈 Calculation Results")
        
        # Summary cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("OAG Average Wage", f"Rs. {res['final_avg']:,.2f}")
        with col2:
            st.metric("OAP Average (Last 12 Months)", f"Rs. {res['last12_avg']:,.2f}")
        with col3:
            st.metric("Service Period", f"{res['service_years']:.2f} years")
        with col4:
            if res['claim_type'] == 'survivor':
                if res['survivor_eligible']:
                    st.metric("Survivor Pension", f"Rs. {res['survivor_pension']:,.2f}/month", "✅ ELIGIBLE")
                else:
                    st.metric("Survivor Eligibility", "NOT ELIGIBLE", "❌")
            else:
                if res['oap_eligible']:
                    st.metric("OAP Pension", f"Rs. {res['oap_pension']:,.2f}/month", "✅ ELIGIBLE")
                else:
                    st.metric("OAP Eligibility", "NOT ELIGIBLE", "❌")
        
        # Additional metrics for survivor
        if res['claim_type'] == 'survivor':
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("36 Continuous Paid Months", "✅ YES" if res['last_36_months_continuous'] else "❌ NO")
            with col2:
                st.metric("Paid Service Years", f"{res['survivor_service_years']:.2f}")
            with col3:
                st.metric("Survivor Eligible", "✅ YES" if res['survivor_eligible'] else "❌ NO")
        
        # Yearly breakdown
        st.subheader("📊 Yearly Breakdown")
        if res['yearly_data']:
            df_yearly = pd.DataFrame(res['yearly_data'])
            df_yearly['Start'] = df_yearly['Start'].dt.strftime('%d/%m/%Y')
            df_yearly['End'] = df_yearly['End'].dt.strftime('%d/%m/%Y')
            df_yearly['Avg Wage'] = df_yearly['Avg Wage'].apply(lambda x: f"Rs. {x:,.2f}")
            st.dataframe(df_yearly[['Year', 'Start', 'End', 'Avg Wage', 'Months', 'Status', 'Days']], 
                        use_container_width=True)
            
            # Chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[f"Year {y['Year']}" for y in res['yearly_data']],
                y=[y['Avg Wage'] for y in res['yearly_data']],
                text=[f"Rs. {y['Avg Wage']:,.2f}" for y in res['yearly_data']],
                textposition='auto',
                marker_color=['#4CAF50' if y['Qualifies'] else '#FF9800' for y in res['yearly_data']]
            ))
            fig.update_layout(
                title="Yearly Average Wages",
                xaxis_title="Year",
                yaxis_title="Average Wage (PKR)",
                height=300,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        
        # Detailed results
        with st.expander("📋 Detailed Calculation Results", expanded=False):
            st.write(f"**Total Period Days:** {res['total_days']}")
            st.write(f"**Zero Wage Months:** {res['zero_months']}")
            st.write(f"**Lesser Rate Months:** {res['lesser_months']}")
            st.write(f"**Qualifying Years:** {res['qualifying_years']}")
            st.write(f"**OAP Formula Years:** {res['formula_years']:.2f}")
            st.write(f"**Claim Type:** {res['claim_type'].upper()}")
            if res['claim_type'] == 'survivor':
                st.write(f"**Death Date:** {res.get('death_date', 'N/A')}")
                st.write(f"**Survivor Type:** {res.get('survivor_type', 'N/A')}")
                st.write(f"**Survivor Eligible:** {'Yes' if res['survivor_eligible'] else 'No'}")
                if res['survivor_eligible']:
                    st.write(f"**Survivor Pension:** Rs. {res['survivor_pension']:,.2f}/month")
                st.write(f"**Paid Service Years:** {res['survivor_service_years']:.2f}")
                st.write(f"**36 Continuous Paid Months:** {'Yes' if res['last_36_months_continuous'] else 'No'}")
            
            if st.session_state.remarks:
                st.write(f"**Remarks:** {st.session_state.remarks}")

elif tab == "Reports":
    st.header("📄 Generate Reports")
    
    if st.session_state.calculation_results:
        res = st.session_state.calculation_results
        
        # Record ID and metadata
        record_id = len(st.session_state.calculated_records) + 1
        
        col1, col2 = st.columns(2)
        with col1:
            region = st.text_input("Region Name", "Multan")
        with col2:
            st.write(f"📌 Record ID: {record_id}")
            st.write(f"👤 Claimant: {st.session_state.claimant_name or 'N/A'}")
        
        st.subheader("📑 Select Report Type")
        
        report_types = []
        if res['claim_type'] == 'survivor':
            report_types.append("Survivor Pension Report")
        else:
            report_types.append("OAG Calculation Report")
            if res['oap_eligible']:
                report_types.append("OAP Pension Report")
            report_types.append("Average Wage Report (Wages Sheet)")
            report_types.append("Consolidated Report")
            if st.session_state.work_percentage < 100:
                report_types.append("Days-Based Report (Percentage)")
        
        selected_report = st.selectbox("Report Type", report_types)
        
        if st.button("📄 Generate Report", type="primary", use_container_width=True):
            # Save record
            record = {
                'id': record_id,
                'claimant': st.session_state.claimant_name,
                'father': st.session_state.father_name,
                'eobi': st.session_state.eobi_no,
                'cnic': st.session_state.cnic_no,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'report_type': selected_report,
                'claim_type': res['claim_type'],
                'oag_avg': res['final_avg'],
                'oap_avg': res['last12_avg'],
                'service_years': res['service_years'],
                'oap_eligible': res['oap_eligible'],
                'oap_pension': res['oap_pension'],
                'region': region,
                'work_percentage': st.session_state.work_percentage,
                'remarks': st.session_state.remarks
            }
            if res['claim_type'] == 'survivor':
                record['survivor_eligible'] = res['survivor_eligible']
                record['survivor_pension'] = res['survivor_pension']
                record['survivor_service_years'] = res['survivor_service_years']
                record['last_36_months_continuous'] = res['last_36_months_continuous']
                record['death_date'] = res.get('death_date', 'N/A')
                record['survivor_type'] = res.get('survivor_type', 'N/A')
            st.session_state.calculated_records.append(record)
            
            # Generate report
            report_content = generate_report(selected_report, res, region, record_id)
            
            st.success(f"✅ {selected_report} generated successfully!")
            
            st.download_button(
                label="📥 Download Report",
                data=report_content,
                file_name=f"{st.session_state.claimant_name.replace(' ', '_')}_{selected_report.replace(' ', '_')}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
            st.success(f"✅ Record ID: {record_id} saved to database")
    else:
        st.warning("⚠️ Please calculate wages first before generating reports.")

elif tab == "Records":
    st.header("📚 Saved Records")
    
    if st.session_state.calculated_records:
        df_records = pd.DataFrame(st.session_state.calculated_records)
        
        # Search
        search = st.text_input("🔍 Search by Claimant Name")
        if search:
            df_records = df_records[df_records['claimant'].str.contains(search, case=False)]
        
        st.dataframe(df_records, use_container_width=True)
        
        selected_record = st.selectbox("Select Record to View", 
                                       [f"ID: {r['id']} - {r['claimant']} ({r['date'][:10]})" for r in st.session_state.calculated_records])
        if selected_record:
            idx = int(selected_record.split(" - ")[0].replace("ID: ", "")) - 1
            if 0 <= idx < len(st.session_state.calculated_records):
                record = st.session_state.calculated_records[idx]
                with st.expander("📋 Record Details", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Claimant:** {record['claimant']}")
                        st.write(f"**Father:** {record['father']}")
                        st.write(f"**EOBI No:** {record['eobi']}")
                        st.write(f"**CNIC:** {record['cnic']}")
                    with col2:
                        st.write(f"**Date:** {record['date']}")
                        st.write(f"**Report Type:** {record['report_type']}")
                        st.write(f"**Region:** {record.get('region', 'N/A')}")
                    
                    st.divider()
                    st.write(f"**OAG Average:** Rs. {record['oag_avg']:,.2f}")
                    st.write(f"**OAP Average:** Rs. {record['oap_avg']:,.2f}")
                    st.write(f"**Service Years:** {record['service_years']:.2f}")
                    st.write(f"**OAP Eligible:** {'Yes' if record['oap_eligible'] else 'No'}")
                    if record.get('survivor_eligible'):
                        st.write(f"**Survivor Eligible:** Yes")
                        st.write(f"**Survivor Pension:** Rs. {record['survivor_pension']:,.2f}")
                    if record.get('work_percentage') and record['work_percentage'] < 100:
                        st.write(f"**Work Percentage:** {record['work_percentage']}%")
                    if record.get('remarks'):
                        st.write(f"**Remarks:** {record['remarks']}")
    else:
        st.info("No records saved yet. Generate reports to save records.")

# ---- Helper Functions ----
def perform_calculation():
    """Perform the full calculation based on all inputs"""
    combined_wages = {}
    zero_months = []
    lesser_months = []
    yearly_data = []
    monthly_wages = []
    
    # Collect wages from all periods
    for period in st.session_state.employment_periods:
        for month_start in iter_month_starts(period['from'], period['to']):
            key = month_start.strftime("%Y-%m")
            # Check if any employer has wage for this month
            for emp in st.session_state.employers:
                wage_key = f"{emp['main_code']}|{emp['sub_code']}|{key}"
                if wage_key in st.session_state.wages:
                    wage = st.session_state.wages[wage_key]
                    if wage > 0:
                        if key in combined_wages:
                            combined_wages[key] += wage
                        else:
                            combined_wages[key] = wage
                        monthly_wages.append((month_start, wage))
                    else:
                        zero_months.append(key)
                    break
    
    # Apply temporary changes
    for temp_key, temp_wage in st.session_state.temporary_changes.items():
        parts = temp_key.split("|")
        if len(parts) == 3:
            main, sub, month = parts
            for emp in st.session_state.employers:
                if emp['main_code'] == main and emp['sub_code'] == sub:
                    combined_wages[month] = temp_wage
                    break
    
    # Calculate yearly averages
    active_wages = sorted([(datetime.strptime(k, "%Y-%m"), v) for k, v in combined_wages.items() if v > 0], key=lambda x: x[0])
    total_months = len(active_wages)
    
    # Build yearly data
    wage_index = 0
    year_num = 1
    yearly_averages = []
    qualifying_years = 0
    yearly_data = []
    
    while wage_index < len(active_wages):
        year_wages = []
        months_collected = 0
        temp_index = wage_index
        year_start_actual = None
        year_end_actual = None
        year_days = 0
        
        while temp_index < len(active_wages) and months_collected < 12:
            d, w = active_wages[temp_index]
            if year_start_actual is None:
                year_start_actual = d
            year_end_actual = d
            year_wages.append(w)
            months_collected += 1
            year_days += get_days_in_month(d.year, d.month)
            temp_index += 1
        
        if months_collected > 0:
            year_avg = sum(year_wages) / months_collected
            qualifies = months_collected >= OAG_PARTIAL_YEAR_MONTHS
            if qualifies:
                qualifying_years += 1
                yearly_averages.append(year_avg)
            
            yearly_data.append({
                'Year': year_num,
                'Start': year_start_actual,
                'End': year_end_actual,
                'Avg Wage': round(year_avg, 2),
                'Months': months_collected,
                'Qualifies': qualifies,
                'Status': f"Complete ({months_collected}/12)" if qualifies else f"Partial ({months_collected}/12) - Not Qualify",
                'Days': year_days
            })
        
        wage_index = temp_index
        year_num += 1
    
    final_avg_value = round(sum(yearly_averages)/len(yearly_averages), 2) if yearly_averages else 0
    
    # Last 12 months
    last12 = active_wages[-12:] if len(active_wages) >= 12 else active_wages
    last12_avg = sum(w for _, w in last12) / len(last12) if last12 else 0
    
    # Service years with percentage
    total_days = sum((p['to'] - p['from']).days + 1 for p in st.session_state.employment_periods)
    actual_days = int(total_days * st.session_state.work_percentage / 100)
    service_years = service_years_from_days(actual_days)
    
    # OAP eligibility
    # Calculate lesser rate and zero wage years for formula
    lesser_rate_years = 0
    zero_wage_years = 0
    for d, w in active_wages:
        month_key = d.strftime("%Y-%m")
        min_wage = get_min(month_key)
        if min_wage and w < min_wage:
            lesser_rate_years += 1 / 12
        elif w == 0:
            zero_wage_years += 1 / 12
    
    formula_years = max(0, service_years - lesser_rate_years - zero_wage_years)
    oap_eligible = service_years >= OAP_REQUIRED_YEARS
    oap_pension = 0
    if oap_eligible and last12_avg > 0:
        raw_oap = (last12_avg * formula_years) / 50
        oap_pension = max(MIN_PENSION, round(raw_oap, 2))
    
    # Survivor check
    survivor_eligible = False
    survivor_pension = 0
    survivor_service_years = service_years
    last_36_months_continuous = False
    
    if st.session_state.claim_type == "survivor" and st.session_state.death_date:
        death_dt = st.session_state.death_date
        if isinstance(death_dt, datetime):
            death_dt = death_dt.date()
        
        # Check last 36 months
        months_continuous = 0
        month_check = datetime(death_dt.year, death_dt.month, 1)
        for i in range(SURVIVOR_CONTINUOUS_MONTHS):
            key = month_check.strftime("%Y-%m")
            if key in combined_wages and combined_wages[key] > 0:
                months_continuous += 1
            else:
                break
            # Move to previous month
            if month_check.month == 1:
                month_check = month_check.replace(year=month_check.year - 1, month=12)
            else:
                month_check = month_check.replace(month=month_check.month - 1)
        
        # Check if 36 months continuous (count from death date backwards)
        last_36_months_continuous = months_continuous >= SURVIVOR_CONTINUOUS_MONTHS
        
        survivor_type = st.session_state.survivor_type
        if survivor_type == "died_during_service":
            # Either 36 continuous months OR 5 cumulative years
            survivor_eligible = last_36_months_continuous or service_years >= SURVIVOR_REQUIRED_YEARS_BEFORE_60
        elif survivor_type == "died_not_in_service":
            survivor_eligible = service_years >= SURVIVOR_REQUIRED_YEARS_BEFORE_60
        elif survivor_type == "died_after_60":
            survivor_eligible = service_years >= SURVIVOR_REQUIRED_YEARS_AFTER_60
        
        survivor_pension = MIN_PENSION if survivor_eligible else 0
    
    return {
        'final_avg': final_avg_value,
        'last12_avg': round(last12_avg, 2),
        'qualifying_years': qualifying_years,
        'service_years': service_years,
        'formula_years': formula_years,
        'oap_eligible': oap_eligible,
        'oap_pension': oap_pension,
        'yearly_data': yearly_data,
        'total_days': total_days,
        'actual_days': actual_days,
        'zero_months': len(zero_months),
        'lesser_months': len(lesser_months),
        'claim_type': st.session_state.claim_type,
        'survivor_eligible': survivor_eligible,
        'survivor_pension': survivor_pension,
        'survivor_service_years': survivor_service_years,
        'last_36_months_continuous': last_36_months_continuous,
        'death_date': st.session_state.death_date.strftime('%d/%m/%Y') if st.session_state.death_date else 'N/A',
        'survivor_type': st.session_state.survivor_type.replace('_', ' ').title() if st.session_state.survivor_type else 'N/A',
        'work_percentage': st.session_state.work_percentage,
        'lesser_rate_years': lesser_rate_years,
        'zero_wage_years': zero_wage_years
    }

def generate_report(report_type, results, region, record_id):
    """Generate formatted report content"""
    lines = []
    lines.append("=" * 75)
    lines.append("EMPLOYEES' OLD-AGE BENEFITS INSTITUTION")
    lines.append("Ministry of Overseas Pakistanis & Human Resource Development")
    lines.append(f"REGIONAL OFFICE - {region.upper()}")
    lines.append("=" * 75)
    lines.append("")
    
    claimant = st.session_state.claimant_name or "N/A"
    father = st.session_state.father_name or "N/A"
    eobi = st.session_state.eobi_no or "N/A"
    cnic = st.session_state.cnic_no or "N/A"
    
    lines.append(f"Claimant Name: {claimant}")
    lines.append(f"Father's Name: {father}")
    lines.append(f"EOBI No: {eobi}")
    lines.append(f"CNIC No: {cnic}")
    lines.append(f"Record ID: {record_id}")
    lines.append(f"Report Type: {report_type}")
    lines.append(f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    lines.append("")
    lines.append("-" * 75)
    
    if report_type == "Survivor Pension Report":
        lines.append("SURVIVOR PENSION REPORT")
        lines.append("-" * 75)
        lines.append(f"Death Date: {results.get('death_date', 'N/A')}")
        lines.append(f"Death Circumstances: {results.get('survivor_type', 'N/A')}")
        lines.append(f"Work Percentage Applied: {results.get('work_percentage', 100)}%")
        lines.append(f"Total Period Days: {results['total_days']}")
        lines.append(f"Actual Work Days: {results.get('actual_days', results['total_days'])}")
        lines.append(f"Paid Service Years: {results['survivor_service_years']:.2f}")
        lines.append(f"36 Continuous Paid Months: {'YES' if results['last_36_months_continuous'] else 'NO'}")
        lines.append("")
        lines.append("ELIGIBILITY CRITERIA:")
        survivor_type = st.session_state.survivor_type
        if survivor_type == "died_during_service":
            lines.append("  • Died during service before 60")
            lines.append(f"  • Required: {SURVIVOR_CONTINUOUS_MONTHS} continuous paid months OR {SURVIVOR_REQUIRED_YEARS_BEFORE_60} paid service years")
            if results['last_36_months_continuous']:
                lines.append("  ✅ 36 continuous months condition MET")
            if results['survivor_service_years'] >= SURVIVOR_REQUIRED_YEARS_BEFORE_60:
                lines.append(f"  ✅ {SURVIVOR_REQUIRED_YEARS_BEFORE_60} years service condition MET")
        elif survivor_type == "died_not_in_service":
            lines.append("  • Died before 60 not in service")
            lines.append(f"  • Required: {SURVIVOR_REQUIRED_YEARS_BEFORE_60} paid service years")
            if results['survivor_service_years'] >= SURVIVOR_REQUIRED_YEARS_BEFORE_60:
                lines.append(f"  ✅ {SURVIVOR_REQUIRED_YEARS_BEFORE_60} years service condition MET")
        elif survivor_type == "died_after_60":
            lines.append("  • Died after 60")
            lines.append(f"  • Required: {SURVIVOR_REQUIRED_YEARS_AFTER_60} paid service years")
            if results['survivor_service_years'] >= SURVIVOR_REQUIRED_YEARS_AFTER_60:
                lines.append(f"  ✅ {SURVIVOR_REQUIRED_YEARS_AFTER_60} years service condition MET")
        lines.append("")
        lines.append(f"Survivor Eligible: {'YES' if results['survivor_eligible'] else 'NO'}")
        if results['survivor_eligible']:
            lines.append(f"Survivor Pension: PKR {results['survivor_pension']:,.2f} per month")
            lines.append(f"(Minimum Pension: PKR {MIN_PENSION:,.0f})")
    
    elif report_type == "OAG Calculation Report":
        lines.append("OAG CALCULATION REPORT")
        lines.append("-" * 75)
        lines.append(f"Work Percentage Applied: {results.get('work_percentage', 100)}%")
        lines.append(f"Total Period Days: {results['total_days']}")
        lines.append(f"Actual Work Days: {results.get('actual_days', results['total_days'])}")
        lines.append("")
        lines.append("YEARLY BREAKDOWN:")
        lines.append("-" * 60)
        lines.append(f"{'Year':<6} {'Period':<25} {'Avg Wage':<15} {'Months':<8} {'Status':<20}")
        lines.append("-" * 60)
        for y in results['yearly_data']:
            period = f"{y['Start'].strftime('%d/%m/%Y')} - {y['End'].strftime('%d/%m/%Y')}"
            lines.append(f"{y['Year']:<6} {period:<25} Rs. {y['Avg Wage']:>10,.2f}  {y['Months']}/12    {y['Status']:<20}")
        lines.append("-" * 60)
        lines.append(f"Qualifying Years: {results['qualifying_years']}")
        lines.append(f"OAG Average Wage: PKR {results['final_avg']:,.2f}")
        lines.append("")
        lines.append(f"Total Zero Wage Months: {results['zero_months']}")
        lines.append(f"Total Lesser Rate Months: {results['lesser_months']}")
        lines.append(f"Lesser Rate Years: {results.get('lesser_rate_years', 0):.2f}")
        lines.append(f"Zero Wage Years: {results.get('zero_wage_years', 0):.2f}")
        lines.append(f"OAP Formula Years: {results['formula_years']:.2f}")
    
    elif report_type == "OAP Pension Report":
        lines.append("OAP PENSION REPORT")
        lines.append("-" * 75)
        lines.append(f"Work Percentage Applied: {results.get('work_percentage', 100)}%")
        lines.append(f"Total Period Days: {results['total_days']}")
        lines.append(f"Actual Work Days: {results.get('actual_days', results['total_days'])}")
        lines.append("")
        lines.append("LAST 12 MONTHS WAGES:")
        lines.append("-" * 50)
        # Get last 12 months
        active_wages = []
        for period in st.session_state.employment_periods:
            for month_start in iter_month_starts(period['from'], period['to']):
                key = month_start.strftime("%Y-%m")
                for emp in st.session_state.employers:
                    wage_key = f"{emp['main_code']}|{emp['sub_code']}|{key}"
                    if wage_key in st.session_state.wages and st.session_state.wages[wage_key] > 0:
                        active_wages.append((month_start, st.session_state.wages[wage_key]))
                        break
        active_wages = sorted(active_wages, key=lambda x: x[0])
        last12 = active_wages[-12:] if len(active_wages) >= 12 else active_wages
        for d, w in last12:
            lines.append(f"  {d.strftime('%B %Y')}: Rs. {w:,.2f}")
        lines.append("-" * 50)
        lines.append(f"Last 12 Months Average: PKR {results['last12_avg']:,.2f}")
        lines.append("")
        lines.append("OAP ELIGIBILITY:")
        lines.append(f"  Service Years: {results['service_years']:.2f}")
        lines.append(f"  Required: {OAP_REQUIRED_YEARS} years")
        lines.append(f"  OAP Eligible: {'YES' if results['oap_eligible'] else 'NO'}")
        if results['oap_eligible']:
            lines.append("")
            lines.append("OAP PENSION CALCULATION:")
            lines.append(f"  Formula: (Last 12 Month Avg x Formula Years) / 50")
            lines.append(f"  Formula Years: {results['formula_years']:.2f}")
            lines.append(f"  ({results['last12_avg']:.2f} x {results['formula_years']:.2f}) / 50 = {results['oap_pension']:.2f}")
            lines.append(f"  Minimum Pension: PKR {MIN_PENSION:,.0f}")
            lines.append(f"  OAP Pension: PKR {results['oap_pension']:,.2f} per month")
    
    elif report_type == "Average Wage Report (Wages Sheet)":
        lines.append("AVERAGE WAGE REPORT (WAGES SHEET)")
        lines.append("-" * 75)
        lines.append(f"Work Percentage Applied: {results.get('work_percentage', 100)}%")
        lines.append(f"Total Period Days: {results['total_days']}")
        lines.append(f"Actual Work Days: {results.get('actual_days', results['total_days'])}")
        lines.append("")
        lines.append("MONTHLY WAGE BREAKDOWN:")
        lines.append("-" * 50)
        lines.append(f"{'Month':<15} {'Wage':<15} {'Status':<20}")
        lines.append("-" * 50)
        
        # Get all wages
        all_wages = []
        for period in st.session_state.employment_periods:
            for month_start in iter_month_starts(period['from'], period['to']):
                key = month_start.strftime("%Y-%m")
                for emp in st.session_state.employers:
                    wage_key = f"{emp['main_code']}|{emp['sub_code']}|{key}"
                    if wage_key in st.session_state.wages:
                        wage = st.session_state.wages[wage_key]
                        all_wages.append((month_start, wage, get_wage_status_label(key, wage)))
                        break
        
        all_wages = sorted(all_wages, key=lambda x: x[0])
        total_wage = 0
        wage_count = 0
        for d, w, status in all_wages:
            lines.append(f"{d.strftime('%B %Y'):<15} Rs. {w:>10,.2f}  {status:<20}")
            if w > 0:
                total_wage += w
                wage_count += 1
        
        lines.append("-" * 50)
        avg_wage = total_wage / wage_count if wage_count > 0 else 0
        lines.append(f"Total Active Months: {wage_count}")
        lines.append(f"Total Wages Sum: Rs. {total_wage:,.2f}")
        lines.append(f"Average Wage: Rs. {avg_wage:,.2f}")
        lines.append("")
        lines.append(f"OAG Average (Yearly): PKR {results['final_avg']:,.2f}")
        lines.append(f"OAP Average (Last 12 Months): PKR {results['last12_avg']:,.2f}")
    
    elif report_type == "Days-Based Report (Percentage)":
        lines.append("DAYS-BASED REPORT")
        lines.append("-" * 75)
        lines.append(f"Work Percentage: {results.get('work_percentage', 100)}%")
        lines.append(f"Total Period Days: {results['total_days']}")
        lines.append(f"Actual Work Days: {results.get('actual_days', results['total_days'])}")
        lines.append(f"Adjusted Service Years: {results['service_years']:.2f}")
        lines.append("")
        lines.append("MONTHLY WAGE BREAKDOWN (Days-Based):")
        lines.append("-" * 50)
        lines.append(f"{'Month':<15} {'Wage':<15} {'Status':<20}")
        lines.append("-" * 50)
        
        # Get all wages
        all_wages = []
        for period in st.session_state.employment_periods:
            for month_start in iter_month_starts(period['from'], period['to']):
                key = month_start.strftime("%Y-%m")
                for emp in st.session_state.employers:
                    wage_key = f"{emp['main_code']}|{emp['sub_code']}|{key}"
                    if wage_key in st.session_state.wages:
                        wage = st.session_state.wages[wage_key]
                        all_wages.append((month_start, wage, get_wage_status_label(key, wage)))
                        break
        
        all_wages = sorted(all_wages, key=lambda x: x[0])
        for d, w, status in all_wages:
            lines.append(f"{d.strftime('%B %Y'):<15} Rs. {w:>10,.2f}  {status:<20}")
        
        lines.append("-" * 50)
        lines.append("")
        lines.append("ADJUSTED CALCULATIONS:")
        adjusted_oag = results['final_avg'] * results.get('work_percentage', 100) / 100
        adjusted_oap = results['last12_avg'] * results.get('work_percentage', 100) / 100
        lines.append(f"Adjusted OAG Average: Rs. {adjusted_oag:,.2f}")
        lines.append(f"Adjusted OAP Average: Rs. {adjusted_oap:,.2f}")
        lines.append(f"Adjusted Service Years: {results['service_years']:.2f}")
    
    elif report_type == "Consolidated Report":
        lines.append("CONSOLIDATED REPORT")
        lines.append("-" * 75)
        lines.append(f"Work Percentage Applied: {results.get('work_percentage', 100)}%")
        lines.append(f"Total Period Days: {results['total_days']}")
        lines.append(f"Actual Work Days: {results.get('actual_days', results['total_days'])}")
        lines.append("")
        lines.append("SUMMARY:")
        lines.append("-" * 50)
        lines.append(f"OAG Average Wage: PKR {results['final_avg']:,.2f}")
        lines.append(f"OAP Average Wage: PKR {results['last12_avg']:,.2f}")
        lines.append(f"Service Years: {results['service_years']:.2f}")
        lines.append(f"Qualifying Years: {results['qualifying_years']}")
        lines.append(f"Zero Wage Months: {results['zero_months']}")
        lines.append(f"Lesser Rate Months: {results['lesser_months']}")
        lines.append(f"OAP Formula Years: {results['formula_years']:.2f}")
        lines.append(f"OAP Eligible: {'YES' if results['oap_eligible'] else 'NO'}")
        if results['oap_eligible']:
            lines.append(f"OAP Pension: PKR {results['oap_pension']:,.2f}/month")
        if results['claim_type'] == 'survivor':
            lines.append(f"Survivor Eligible: {'YES' if results['survivor_eligible'] else 'NO'}")
            if results['survivor_eligible']:
                lines.append(f"Survivor Pension: PKR {results['survivor_pension']:,.2f}/month")
        lines.append("")
        if results['yearly_data']:
            lines.append("YEARLY BREAKDOWN:")
            lines.append("-" * 60)
            lines.append(f"{'Year':<6} {'Period':<25} {'Avg Wage':<15} {'Status':<20}")
            lines.append("-" * 60)
            for y in results['yearly_data']:
                period = f"{y['Start'].strftime('%d/%m/%Y')} - {y['End'].strftime('%d/%m/%Y')}"
                lines.append(f"{y['Year']:<6} {period:<25} Rs. {y['Avg Wage']:>10,.2f}  {y['Status']:<20}")
    
    lines.append("")
    lines.append("-" * 75)
    lines.append("CERTIFICATION")
    lines.append(f"Signature: _______________  Date: {datetime.now().strftime('%d-%m-%Y')}")
    lines.append("")
    lines.append(f"EOBI-Regional Office {region}")
    lines.append(f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    lines.append("Zee Shah | EOBI Wage & Pension Calculation System")
    lines.append("Special thanks to Mr. Nasrullah Shah")
    lines.append("=" * 75)
    
    return "\n".join(lines)

# ---- Run ----
if __name__ == "__main__":
    st.write("")
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import customtkinter as ctk
from tkinter import ttk, messagebox
import tkinter as tk
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from PIL import Image, ImageDraw
import os
import sys
import calendar
import json

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def create_avatar():
    img = Image.new('RGBA', (100, 100), (26, 35, 126, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([20, 20, 80, 80], fill='#FF6F00', outline='#FF8F00', width=3)
    draw.ellipse([35, 40, 45, 50], fill='white')
    draw.ellipse([55, 40, 65, 50], fill='white')
    draw.ellipse([38, 43, 42, 47], fill='#1a237e')
    draw.ellipse([58, 43, 62, 47], fill='#1a237e')
    draw.arc([40, 55, 60, 70], start=0, end=180, fill='white', width=3)
    return ctk.CTkImage(img, size=(80, 80))

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

COLORS = {
    'primary': '#1a237e', 'primary_light': '#283593', 'primary_dark': '#0d1652',
    'secondary': '#00897B', 'secondary_light': '#26A69A', 'accent': '#FF6F00',
    'success': '#2E7D32', 'warning': '#F57C00', 'error': '#C62828',
    'bg_dark': '#0f0f0f', 'bg_card': '#1a1a1a', 'bg_hover': '#252525',
    'survivor': '#6A1B9A'
}

APP_TITLE = "EOBI Wage & Pension Calculation System"
APP_VERSION = "Professional Edition v6.0"
SCHEME_START_DATE = datetime(1976, 7, 1)
MIN_PENSION = 11500
OAP_REQUIRED_YEARS = 14.5
OAG_PARTIAL_YEAR_MONTHS = 6
SURVIVOR_CONTINUOUS_MONTHS = 36
SURVIVOR_REQUIRED_YEARS_BEFORE_60 = 5
SURVIVOR_REQUIRED_YEARS_AFTER_60 = 15
DAYS_IN_SERVICE_YEAR = 365.0

def get_db_path():
    if getattr(sys, 'frozen', False):
        app_data = os.path.join(os.environ['APPDATA'], 'EOBI_Wage_Calculator')
        os.makedirs(app_data, exist_ok=True)
        return os.path.join(app_data, "wages.db")
    return "wages.db"

db_path = get_db_path()
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS employers (
    main_code TEXT, sub_code TEXT, name TEXT,
    city TEXT, applicability TEXT, beat TEXT,
    PRIMARY KEY(main_code, sub_code))""")

cursor.execute("""CREATE TABLE IF NOT EXISTS wages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    main_code TEXT, sub_code TEXT,
    month TEXT, wage REAL,
    UNIQUE(main_code, sub_code, month))""")

cursor.execute("""CREATE TABLE IF NOT EXISTS temporary_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    main_code TEXT, sub_code TEXT,
    month TEXT, wage REAL,
    claimant_name TEXT,
    reason TEXT,
    UNIQUE(main_code, sub_code, month, claimant_name))""")

cursor.execute("""CREATE TABLE IF NOT EXISTS calculated_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claimant_name TEXT,
    father_name TEXT,
    eobi_no TEXT,
    cnic_no TEXT,
    calculation_date TEXT,
    oag_average REAL,
    oap_average REAL,
    total_oag_amount REAL,
    total_oap_amount REAL,
    total_months INTEGER,
    total_months_in_period INTEGER,
    qualifying_years INTEGER,
    total_days INTEGER,
    zero_wage_months_count INTEGER,
    lesser_months_count INTEGER,
    periods_data TEXT,
    temporary_changes_data TEXT,
    report_type TEXT,
    oap_eligible INTEGER DEFAULT 0,
    work_percentage REAL DEFAULT 100,
    actual_work_days INTEGER DEFAULT 0,
    adjusted_oag_average REAL DEFAULT 0,
    adjusted_years REAL DEFAULT 0,
    remarks TEXT DEFAULT '',
    claim_type TEXT DEFAULT 'self',
    survivor_type TEXT DEFAULT '',
    death_date TEXT DEFAULT '',
    last_36_months_continuous INTEGER DEFAULT 0,
    survivor_eligible INTEGER DEFAULT 0,
    survivor_pension REAL DEFAULT 0
)""")

cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_report_type ON calculated_records(report_type)")
conn.commit()

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

def get_rate_coverage_text():
    last_from, last_to, last_rate = rates[-1]
    return f"{last_from} to {last_to}: PKR {last_rate:,.0f}"

def add_month(date_obj):
    if date_obj.month == 12:
        return date_obj.replace(year=date_obj.year + 1, month=1)
    return date_obj.replace(month=date_obj.month + 1)

def service_years_from_days(days):
    return round(days / DAYS_IN_SERVICE_YEAR, 4) if days > 0 else 0.0

def get_wage_status_label(month_key, wage):
    min_wage = get_min(month_key)
    if wage == 0:
        return "No Contribution"
    if min_wage and wage < min_wage:
        return "Lesser Rate"
    if min_wage and wage == min_wage:
        return "Minimum Wage"
    return "Above Minimum"

def iter_month_starts(from_date, to_date):
    current = normalize_date_to_month(from_date)
    end_month = normalize_date_to_month(to_date)
    while current <= end_month:
        yield current
        current = add_month(current)

def get_month_end_date(dt):
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    return dt.replace(day=last_day)

def get_month_start_date(dt):
    return dt.replace(day=1)

def get_month_key_from_date(date_obj):
    return f"{date_obj.year}-{str(date_obj.month).zfill(2)}"

def normalize_date_to_month(date_obj):
    return date_obj.replace(day=1)

def get_month_range_dates(from_date, to_date):
    month_start = normalize_date_to_month(from_date)
    month_end = get_month_end_date(to_date)
    return month_start, month_end

def load_csv():
    try:
        csv_path = resource_path("employer list.csv")
        if os.path.exists(csv_path):
            cursor.execute("SELECT COUNT(*) FROM employers")
            count = cursor.fetchone()[0]
            if count > 0:
                return
            df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
            df.columns = df.columns.str.lower()
            df = df.drop_duplicates(subset=['main code', 'sub code'])
            data = []
            for _, r in df.iterrows():
                main_code = str(r['main code']).strip() if pd.notna(r['main code']) else ''
                sub_code = str(r['sub code']).strip() if pd.notna(r['sub code']) else ''
                name = str(r['name of establishment']).strip() if pd.notna(r['name of establishment']) else ''
                city = str(r.get('city', '')).strip() if pd.notna(r.get('city', '')) else ''
                app = str(r.get('date of applicability of act', '')).strip() if pd.notna(r.get('date of applicability of act', '')) else ''
                beat = str(r.get('beat', '')).strip() if pd.notna(r.get('beat', '')) else ''
                data.append((main_code, sub_code, name, city, app, beat))
            cursor.executemany("INSERT OR IGNORE INTO employers VALUES (?,?,?,?,?,?)", data)
            conn.commit()
    except Exception as e:
        print(f"CSV load error: {e}")

selected_main = selected_sub = selected_name = selected_app = ""
yearly_data = []
less_months = 0
edit_id = None
final_avg_value = last12_avg_value = 0
total_months_worked = 0
total_months_in_period = 0
qualifying_years = 0
employment_periods = []
duplicate_warnings = []
missing_periods = []
zero_wage_months = []
lesser_rate_months = []
temporary_changes = {}
total_oag_amount = 0
total_oap_amount = 0
oap_eligible = False
combined_wages = {}
oap_qualifying_period_years = 0.0
oap_formula_years = 0.0
lesser_rate_years = 0.0
zero_wage_years = 0.0
survivor_service_years = 0.0
current_record_id = None
work_percentage = 100.0
actual_work_days = 0
adjusted_oag_average = 0
adjusted_years = 0.0
remarks_text = ""
claim_type = "self"
survivor_type = ""
death_date = ""
last_36_months_continuous = False
survivor_eligible = False
survivor_pension = 0

guide_messages = [
    "👋 Hello! I'm your EOBI Assistant!",
    "🔍 Start by searching for an employer!",
    "💰 Add wage records for calculation!",
    "📊 Add employment periods with multiple employers!",
    "⚡ Use Temporary Wages for special cases!",
    "📄 Generate professional PDF reports!",
    "👤 Choose Self or Survivor claim type!",
    "✨ Special thanks to Mr. Nasrullah Shah!"
]

current_message_index = 0

class CalendarDialog:
    def __init__(self, parent, entry_widget):
        self.parent = parent
        self.entry_widget = entry_widget
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Select Date")
        self.dialog.geometry("400x450")
        self.dialog.grab_set()
        self.current_date = datetime.now()
        self.selected_date = None
        self.setup_ui()

    def setup_ui(self):
        header_frame = ctk.CTkFrame(self.dialog, fg_color=COLORS['primary'], height=60)
        header_frame.pack(fill="x", padx=10, pady=10)
        header_frame.pack_propagate(False)
        self.month_year_label = ctk.CTkLabel(header_frame, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.month_year_label.pack(expand=True)
        nav_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(nav_frame, text="◀", width=50, command=self.prev_month, fg_color=COLORS['primary']).pack(side="left", padx=5)
        ctk.CTkButton(nav_frame, text="▶", width=50, command=self.next_month, fg_color=COLORS['primary']).pack(side="right", padx=5)
        self.cal_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        self.cal_frame.pack(fill="both", expand=True, padx=10, pady=10)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            ctk.CTkLabel(self.cal_frame, text=day, font=ctk.CTkFont(size=12, weight="bold"), width=45).grid(row=0, column=i, padx=2, pady=2)
        self.update_calendar()
        btn_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(btn_frame, text="OK", command=self.select_date, fg_color=COLORS['success'], width=100).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.dialog.destroy, fg_color=COLORS['error'], width=100).pack(side="right", padx=5)

    def update_calendar(self):
        for widget in self.cal_frame.winfo_children():
            if isinstance(widget, ctk.CTkButton) and widget.winfo_y() > 30:
                widget.destroy()
        self.month_year_label.configure(text=self.current_date.strftime("%B %Y"))
        first_day = self.current_date.replace(day=1)
        first_day_weekday = first_day.weekday()
        num_days = calendar.monthrange(self.current_date.year, self.current_date.month)[1]
        row, col = 1, first_day_weekday
        for day in range(1, num_days+1):
            date = self.current_date.replace(day=day)
            btn = ctk.CTkButton(self.cal_frame, text=str(day), width=45, height=35,
                               fg_color=COLORS['primary'] if date.date() == datetime.now().date() else COLORS['bg_hover'],
                               hover_color=COLORS['primary_light'], command=lambda d=date: self.set_date(d))
            btn.grid(row=row, column=col, padx=2, pady=2)
            col += 1
            if col > 6:
                col = 0
                row += 1

    def set_date(self, date):
        self.selected_date = date

    def select_date(self):
        if self.selected_date:
            self.entry_widget.delete(0, 'end')
            self.entry_widget.insert(0, self.selected_date.strftime("%d/%m/%Y"))
        self.dialog.destroy()

    def prev_month(self):
        self.current_date = self.current_date.replace(month=self.current_date.month-1) if self.current_date.month > 1 else self.current_date.replace(year=self.current_date.year-1, month=12)
        self.update_calendar()

    def next_month(self):
        self.current_date = self.current_date.replace(month=self.current_date.month+1) if self.current_date.month < 12 else self.current_date.replace(year=self.current_date.year+1, month=1)
        self.update_calendar()

def show_calendar(entry_widget):
    CalendarDialog(app, entry_widget)

def update_avatar_message():
    global current_message_index
    avatar_label.configure(text=guide_messages[current_message_index])
    current_message_index = (current_message_index + 1) % len(guide_messages)
    app.after(5000, update_avatar_message)

def search():
    k = entry_search.get().lower()
    table_emp.delete(*table_emp.get_children())
    cursor.execute("SELECT * FROM employers")
    for r in cursor.fetchall():
        if k in str(r[2]).lower() or k in str(r[0]).lower():
            table_emp.insert("", "end", values=r)

def select_emp(e):
    global selected_main, selected_sub, selected_name, selected_app
    d = table_emp.item(table_emp.focus(), 'values')
    if not d: return
    selected_main, selected_sub, selected_name, selected_app = d[0], d[1], d[2], d[4]
    label_emp.configure(text=f"{selected_name} ({selected_main}-{selected_sub})")
    load_wages()
    update_wage_status()

def load_wages():
    table_wages.delete(*table_wages.get_children())
    if selected_main and selected_sub:
        cursor.execute("SELECT id,month,wage FROM wages WHERE main_code=? AND sub_code=? ORDER BY month", (selected_main, selected_sub))
        for r in cursor.fetchall():
            d = datetime.strptime(r[1], "%Y-%m")
            wage_status = get_wage_status_label(r[1], r[2])
            table_wages.insert("", "end", values=(r[0], d.strftime("%d/%m/%Y"), f"Rs. {r[2]:,.2f}", wage_status))

def update_wage_status():
    if selected_main and selected_sub:
        cursor.execute("""
            SELECT month, wage FROM wages 
            WHERE main_code=? AND sub_code=? 
            ORDER BY month
        """, (selected_main, selected_sub))
        wages = cursor.fetchall()
        
        status_text = "📊 WAGE STATUS SUMMARY\n\n"
        status_text += f"Employer: {selected_name}\n"
        status_text += f"Code: {selected_main}-{selected_sub}\n"
        status_text += f"Rate Coverage: {get_rate_coverage_text()}\n\n"
        
        if wages:
            sorted_wages = sorted(wages, key=lambda x: x[0])
            first_date = datetime.strptime(sorted_wages[0][0], "%Y-%m")
            last_date = datetime.strptime(sorted_wages[-1][0], "%Y-%m")
            
            first_display = get_month_start_date(first_date)
            last_display = get_month_end_date(last_date)
            
            status_text += f"📅 Wages Added From:\n"
            status_text += f"   {first_display.strftime('%d/%m/%Y')} to {last_display.strftime('%d/%m/%Y')}\n\n"
            
            existing_months = set()
            zero_months_list = []
            active_months_list = []
            lesser_rate_months_list = []
            
            for m, w in sorted_wages:
                d = datetime.strptime(m, "%Y-%m")
                existing_months.add(d)
                if w == 0:
                    zero_months_list.append(d)
                else:
                    active_months_list.append(d)
                    if w < get_min(m):
                        lesser_rate_months_list.append(d)
            
            all_months = []
            current = first_date
            while current <= last_date:
                all_months.append(current)
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            
            missing_months = [m for m in all_months if m not in existing_months]
            
            status_text += f"✅ Active Wages: {len(active_months_list)} months\n"
            if active_months_list:
                recent_active = sorted(active_months_list)[-3:]
                status_text += f"   Latest: {', '.join([m.strftime('%b %Y') for m in recent_active])}\n\n"
            
            status_text += f"⚠️ Zero Wages: {len(zero_months_list)} months\n"
            if zero_months_list:
                zero_display = sorted(zero_months_list)[:3]
                status_text += f"   {', '.join([m.strftime('%m/%Y') for m in zero_display])}"
                if len(zero_months_list) > 3:
                    status_text += f"\n   ... and {len(zero_months_list)-3} more (click See More)"
            status_text += "\n\n"
            
            if lesser_rate_months_list:
                status_text += f"🔻 Lesser Rate: {len(lesser_rate_months_list)} months\n"
                lesser_display = sorted(lesser_rate_months_list)[:3]
                status_text += f"   {', '.join([m.strftime('%m/%Y') for m in lesser_display])}"
                if len(lesser_rate_months_list) > 3:
                    status_text += f"\n   ... and {len(lesser_rate_months_list)-3} more"
            else:
                status_text += f"✅ No lesser rate months\n"
            status_text += "\n\n"
            
            if missing_months:
                status_text += f"❌ Missing Wages: {len(missing_months)} months\n"
                missing_display = sorted(missing_months)[:3]
                status_text += f"   {', '.join([m.strftime('%m/%Y') for m in missing_display])}"
                if len(missing_months) > 3:
                    status_text += f"\n   ... and {len(missing_months)-3} more"
            else:
                status_text += "✅ All months have wages!"
        else:
            status_text += "No wages found for this employer."
        
        wage_status_label.configure(text=status_text)
    else:
        wage_status_label.configure(text="Select an employer to view wage status")

def show_full_wage_status():
    if not selected_main or not selected_sub:
        return
    
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("750x650")
    dialog.title("Complete Wage Status")
    dialog.grab_set()
    
    header = ctk.CTkFrame(dialog, fg_color=COLORS['primary'], height=60, corner_radius=10)
    header.pack(fill="x", padx=15, pady=15)
    ctk.CTkLabel(header, text=f"WAGE STATUS: {selected_name}", font=ctk.CTkFont(size=18, weight="bold"), 
                text_color="white").pack(expand=True)
    
    content_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
    content_frame.pack(fill="both", expand=True, padx=15, pady=10)
    
    cursor.execute("""
        SELECT month, wage FROM wages 
        WHERE main_code=? AND sub_code=? 
        ORDER BY month
    """, (selected_main, selected_sub))
    wages = cursor.fetchall()
    
    if wages:
        sorted_wages = sorted(wages, key=lambda x: x[0])
        first_date = datetime.strptime(sorted_wages[0][0], "%Y-%m")
        last_date = datetime.strptime(sorted_wages[-1][0], "%Y-%m")
        
        existing_months = {}
        zero_months = []
        active_months = []
        lesser_rate_months_list = []
        
        for m, w in sorted_wages:
            d = datetime.strptime(m, "%Y-%m")
            existing_months[d] = w
            if w == 0:
                zero_months.append(d)
            else:
                active_months.append(d)
                if w < get_min(m):
                    lesser_rate_months_list.append(d)
        
        all_months = []
        current = first_date
        while current <= last_date:
            all_months.append(current)
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        missing_months = [m for m in all_months if m not in existing_months]
        
        if lesser_rate_months_list:
            lesser_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['bg_hover'])
            lesser_frame.pack(fill="x", pady=10)
            ctk.CTkLabel(lesser_frame, text="🔻 LESSER RATE MONTHS", 
                        font=ctk.CTkFont(size=13, weight="bold"), 
                        text_color=COLORS['warning']).pack(pady=10)
            
            lesser_text = ctk.CTkTextbox(lesser_frame, height=120, font=ctk.CTkFont(size=11),
                                        fg_color=COLORS['bg_dark'], text_color="white")
            lesser_text.pack(fill="both", expand=True, padx=15, pady=10)
            
            for i, d in enumerate(sorted(lesser_rate_months_list), 1):
                w = existing_months[d]
                min_w = get_min(d.strftime("%Y-%m"))
                lesser_text.insert("end", f"{i:3}. {d.strftime('%B %Y')} - Paid: Rs. {w:,.2f} | Minimum: Rs. {min_w:,.2f}\n")
            lesser_text.insert("end", f"\n📊 Total Lesser Rate Months: {len(lesser_rate_months_list)}")
            lesser_text.configure(state="disabled")
        
        zero_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['bg_hover'])
        zero_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(zero_frame, text="⚠️ ZERO WAGE MONTHS", 
                    font=ctk.CTkFont(size=14, weight="bold"), 
                    text_color=COLORS['warning']).pack(pady=10)
        
        if zero_months:
            zero_text = ctk.CTkTextbox(zero_frame, height=200, font=ctk.CTkFont(size=11),
                                       fg_color=COLORS['bg_dark'], text_color="white")
            zero_text.pack(fill="both", expand=True, padx=15, pady=10)
            
            for i, d in enumerate(sorted(zero_months), 1):
                zero_text.insert("end", f"{i:3}. {d.strftime('%B %Y')} - No contribution paid (Skipped)\n")
            zero_text.insert("end", f"\n📊 Total Zero Wage Months: {len(zero_months)}")
            zero_text.configure(state="disabled")
        else:
            ctk.CTkLabel(zero_frame, text="✅ No zero wage months found!", 
                        font=ctk.CTkFont(size=12), text_color=COLORS['success']).pack(pady=10)
        
        missing_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['bg_hover'])
        missing_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(missing_frame, text="❌ MISSING MONTHS", 
                    font=ctk.CTkFont(size=14, weight="bold"), 
                    text_color=COLORS['error']).pack(pady=10)
        
        if missing_months:
            missing_text = ctk.CTkTextbox(missing_frame, height=200, font=ctk.CTkFont(size=11),
                                         fg_color=COLORS['bg_dark'], text_color="white")
            missing_text.pack(fill="both", expand=True, padx=15, pady=10)
            
            for i, d in enumerate(sorted(missing_months), 1):
                missing_text.insert("end", f"{i:3}. {d.strftime('%B %Y')} - Not in database\n")
            missing_text.insert("end", f"\n📊 Total Missing Months: {len(missing_months)}")
            missing_text.configure(state="disabled")
        else:
            ctk.CTkLabel(missing_frame, text="✅ No missing months found!", 
                        font=ctk.CTkFont(size=12), text_color=COLORS['success']).pack(pady=10)
        
        summary_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['primary'])
        summary_frame.pack(fill="x", pady=10)
        
        summary_text = f"""📊 SUMMARY
• Total Months in Range: {len(all_months)}
• Active Wage Months: {len(active_months)}
• Lesser Rate Months: {len(lesser_rate_months_list)}
• Zero Wage Months: {len(zero_months)}
• Missing Months: {len(missing_months)}"""
        
        ctk.CTkLabel(summary_frame, text=summary_text, 
                    font=ctk.CTkFont(size=12), text_color="white",
                    justify="left").pack(padx=15, pady=15)
    
    ctk.CTkButton(dialog, text="Close", command=dialog.destroy, 
                 fg_color=COLORS['primary'], height=35, width=100).pack(pady=10)

def edit_wage():
    global edit_id
    d = table_wages.item(table_wages.focus(), 'values')
    if not d: return
    edit_id = d[0]
    m = datetime.strptime(d[1], "%d/%m/%Y")
    wage_val = d[2].replace("Rs. ", "").replace(",", "")
    entry_wage_date.delete(0, 'end'); entry_wage_date.insert(0, m.strftime("%d/%m/%Y"))
    entry_wage_amount.delete(0, 'end'); entry_wage_amount.insert(0, wage_val)
    add_btn.configure(text="💾 Save Changes", fg_color=COLORS['warning'])
    entry_wage_date_to.delete(0, 'end')

def add_approved():
    if not selected_main:
        messagebox.showwarning("Warning", "Please select an employer first")
        return
    start = SCHEME_START_DATE
    try:
        app_date = datetime.strptime(selected_app, "%d-%b-%y")
    except:
        try:
            app_date = datetime.strptime(selected_app, "%d/%m/%Y")
        except:
            app_date = start
    if app_date > start:
        start = app_date
    start = normalize_date_to_month(start)
    end = normalize_date_to_month(datetime.now())
    data = []
    current = start
    while current <= end:
        key = f"{current.year}-{str(current.month).zfill(2)}"
        min_wage = get_min(key)
        if min_wage > 0:
            data.append((selected_main, selected_sub, key, min_wage))
        current = add_month(current)
    cursor.executemany("INSERT OR IGNORE INTO wages VALUES(NULL,?,?,?,?)", data)
    conn.commit()
    load_wages()
    update_wage_status()
    update_stats()
    messagebox.showinfo("Success", f"Minimum wage records added through {end.strftime('%B %Y')}.\nRate coverage: {get_rate_coverage_text()}")

def check_wage_exists(main_code, sub_code, month_key):
    cursor.execute("SELECT id, wage FROM wages WHERE main_code=? AND sub_code=? AND month=?", 
                  (main_code, sub_code, month_key))
    return cursor.fetchone()

def add_wage():
    global edit_id
    if not selected_main:
        messagebox.showwarning("Warning", "Please select an employer first")
        return
    try:
        if entry_wage_date_to.get():
            start_date = datetime.strptime(entry_wage_date.get(), "%d/%m/%Y")
            end_date = datetime.strptime(entry_wage_date_to.get(), "%d/%m/%Y")
            wage_val = float(entry_wage_amount.get())
            if wage_val < 0:
                messagebox.showerror("Error", "Wage cannot be negative.")
                return
            if start_date > end_date:
                messagebox.showerror("Error", "From Date cannot be after To Date.")
                return
            if start_date < SCHEME_START_DATE:
                messagebox.showerror("Error", "Wage records cannot start before 01/07/1976.")
                return
            if end_date.date() > datetime.now().date():
                messagebox.showerror("Error", "Wage records cannot be added after today.")
                return
            
            month_start = normalize_date_to_month(start_date)
            month_end = normalize_date_to_month(end_date)
            
            skipped = []
            added = []
            
            current = month_start
            while current <= month_end:
                key = get_month_key_from_date(current)
                
                existing = check_wage_exists(selected_main, selected_sub, key)
                if existing:
                    skipped.append((key, existing[1]))
                else:
                    cursor.execute("INSERT INTO wages VALUES(NULL,?,?,?,?)", 
                                 (selected_main, selected_sub, key, wage_val))
                    added.append(key)
                
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            
            conn.commit()
            load_wages()
            update_wage_status()
            
            msg = f"✅ Added {len(added)} wage records."
            if wage_val == 0:
                msg += "\n⚠️ Note: Zero wage months will be skipped in calculations."
            if skipped:
                msg += f"\n⚠️ Skipped {len(skipped)} already existing."
            messagebox.showinfo("Success", msg)
                
        else:
            wage_date = datetime.strptime(entry_wage_date.get(), "%d/%m/%Y")
            wage_val = float(entry_wage_amount.get())
            if wage_val < 0:
                messagebox.showerror("Error", "Wage cannot be negative.")
                return
            if wage_date < SCHEME_START_DATE:
                messagebox.showerror("Error", "Wage records cannot start before 01/07/1976.")
                return
            if wage_date.date() > datetime.now().date():
                messagebox.showerror("Error", "Wage records cannot be added after today.")
                return
            key = get_month_key_from_date(wage_date)
            
            if edit_id:
                cursor.execute("UPDATE wages SET month=?, wage=? WHERE id=?", (key, wage_val, edit_id))
                edit_id = None
                add_btn.configure(text="➕ Add", fg_color=COLORS['primary'])
                messagebox.showinfo("Success", "Wage updated successfully")
            else:
                existing = check_wage_exists(selected_main, selected_sub, key)
                if existing:
                    messagebox.showerror("Error", f"Wage for {entry_wage_date.get()} already exists!")
                    return
                
                cursor.execute("INSERT INTO wages VALUES(NULL,?,?,?,?)", 
                             (selected_main, selected_sub, key, wage_val))
                msg = "Wage added successfully"
                if wage_val == 0:
                    msg += "\n⚠️ Note: Zero wage months will be skipped."
                messagebox.showinfo("Success", msg)
                    
    except Exception as e:
        messagebox.showerror("Error", f"Invalid input: {e}")
        return
    conn.commit()
    load_wages()
    update_wage_status()
    update_stats()
    clear_wage_fields()

def clear_wage_fields():
    entry_wage_date.delete(0, 'end'); entry_wage_date_to.delete(0, 'end'); entry_wage_amount.delete(0, 'end')
    global edit_id
    edit_id = None
    add_btn.configure(text="➕ Add", fg_color=COLORS['primary'])

def delete():
    d = table_wages.item(table_wages.focus(), 'values')
    if not d: return
    if messagebox.askyesno("Confirm", "Delete this wage record?"):
        cursor.execute("DELETE FROM wages WHERE id=?", (d[0],))
        conn.commit()
        load_wages()
        update_wage_status()
        update_stats()
        clear_wage_fields()

def bulk_delete_wages():
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("700x650")
    dialog.title("Bulk Delete Wages")
    dialog.grab_set()
    
    header = ctk.CTkFrame(dialog, fg_color=COLORS['error'], height=55, corner_radius=8)
    header.pack(fill="x", padx=15, pady=15)
    ctk.CTkLabel(header, text="BULK DELETE WAGES", font=ctk.CTkFont(size=18, weight="bold"), 
                text_color="white").pack(expand=True)
    
    search_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    search_frame.pack(fill="x", padx=20, pady=5)
    search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search employer...", width=300, height=35)
    search_entry.pack(side="left", padx=5)
    
    list_frame = ctk.CTkFrame(dialog, fg_color=COLORS['bg_dark'])
    list_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
    wage_listbox = tk.Listbox(list_frame, bg="#2b2b2b", fg="white", 
                             selectbackground=COLORS['primary_light'],
                             selectmode=tk.MULTIPLE,
                             font=('Segoe UI', 10),
                             exportselection=False)
    wage_listbox.pack(side="left", fill="both", expand=True)
    wage_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=wage_listbox.yview)
    wage_listbox.configure(yscrollcommand=wage_scroll.set)
    wage_scroll.pack(side="right", fill="y")
    
    quick_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    quick_frame.pack(fill="x", padx=20, pady=10)
    
    def load_all_wages():
        wage_listbox.delete(0, tk.END)
        cursor.execute("""
            SELECT w.id, e.name, w.main_code, w.sub_code, w.month, w.wage 
            FROM wages w 
            JOIN employers e ON e.main_code = w.main_code AND e.sub_code = w.sub_code 
            ORDER BY w.month
        """)
        for row in cursor.fetchall():
            d = datetime.strptime(row[4], "%Y-%m")
            status = "NO CONTRIB" if row[5] == 0 else "ACTIVE"
            wage_listbox.insert(tk.END, f"[{status}] {row[1][:25]} | {d.strftime('%b %Y')} | Rs. {row[5]:,.2f} | ID:{row[0]}")
    
    def search_wages():
        wage_listbox.delete(0, tk.END)
        search_term = search_entry.get().lower()
        cursor.execute("""
            SELECT w.id, e.name, w.main_code, w.sub_code, w.month, w.wage 
            FROM wages w 
            JOIN employers e ON e.main_code = w.main_code AND e.sub_code = w.sub_code 
            WHERE LOWER(e.name) LIKE ? OR LOWER(w.main_code) LIKE ?
            ORDER BY w.month
        """, (f'%{search_term}%', f'%{search_term}%'))
        for row in cursor.fetchall():
            d = datetime.strptime(row[4], "%Y-%m")
            status = "NO CONTRIB" if row[5] == 0 else "ACTIVE"
            wage_listbox.insert(tk.END, f"[{status}] {row[1][:25]} | {d.strftime('%b %Y')} | Rs. {row[5]:,.2f} | ID:{row[0]}")
    
    def select_all():
        wage_listbox.select_set(0, tk.END)
    
    def confirm_delete():
        selected = wage_listbox.curselection()
        if not selected:
            messagebox.showwarning("Warning", "Please select wages to delete!")
            return
        
        count = len(selected)
        if messagebox.askyesno("Confirm Delete", f"Delete {count} selected wage records?"):
            for i in selected:
                item = wage_listbox.get(i)
                wage_id = item.split("ID:")[1]
                cursor.execute("DELETE FROM wages WHERE id=?", (wage_id,))
            conn.commit()
            dialog.destroy()
            load_wages()
            update_wage_status()
            update_stats()
            messagebox.showinfo("Success", f"Deleted {count} wage records!")
    
    ctk.CTkButton(search_frame, text="🔍 Search", command=search_wages, width=80, height=35).pack(side="left", padx=5)
    ctk.CTkButton(quick_frame, text="Select All", command=select_all, width=100, height=35, fg_color=COLORS['secondary']).pack(side="left", padx=5)
    ctk.CTkButton(quick_frame, text="🗑️ Delete Selected", command=confirm_delete, width=130, height=35, fg_color=COLORS['error']).pack(side="right", padx=5)
    
    load_all_wages()

def manage_temporary_wages():
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("800x700")
    dialog.title("⚡ Temporary Wage Changes (Claimant Specific)")
    dialog.grab_set()
    
    header = ctk.CTkFrame(dialog, fg_color=COLORS['accent'], height=60, corner_radius=10)
    header.pack(fill="x", padx=15, pady=15)
    ctk.CTkLabel(header, text="⚡ TEMPORARY WAGE CHANGES FOR CLAIMANT", font=ctk.CTkFont(size=18, weight="bold"), 
                text_color="white").pack(expand=True)
    
    ctk.CTkLabel(dialog, text="⚠️ These changes are temporary and only affect this claimant's calculation. No changes to main database.", 
                font=ctk.CTkFont(size=11), text_color=COLORS['warning']).pack(pady=5)
    
    claimant_frame = ctk.CTkFrame(dialog, fg_color=COLORS['bg_hover'])
    claimant_frame.pack(fill="x", padx=15, pady=10)
    
    ctk.CTkLabel(claimant_frame, text="Claimant Name:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
    claimant_entry = ctk.CTkEntry(claimant_frame, width=250, height=35, font=ctk.CTkFont(size=12))
    claimant_entry.grid(row=0, column=1, padx=10, pady=5)
    claimant_entry.insert(0, entry_claimant.get())
    
    add_frame = ctk.CTkFrame(dialog, fg_color=COLORS['bg_hover'])
    add_frame.pack(fill="x", padx=15, pady=10)
    
    ctk.CTkLabel(add_frame, text="ADD TEMPORARY WAGE CHANGE", font=ctk.CTkFont(size=14, weight="bold"), 
                text_color=COLORS['accent']).pack(pady=10)
    
    emp_select_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
    emp_select_frame.pack(fill="x", padx=15, pady=5)
    
    ctk.CTkLabel(emp_select_frame, text="Select Employer:", font=ctk.CTkFont(size=11)).pack(side="left", padx=5)
    
    emp_list = []
    for p in employment_periods:
        for e in p['employers']:
            emp_list.append(f"{e[2]} ({e[0]}-{e[1]})")
    
    emp_var = tk.StringVar(value="Select Employer" if not emp_list else emp_list[0])
    emp_dropdown = ctk.CTkOptionMenu(emp_select_frame, values=emp_list if emp_list else ["No employers"], 
                                     variable=emp_var, width=300, height=35)
    emp_dropdown.pack(side="left", padx=5)
    
    date_wage_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
    date_wage_frame.pack(fill="x", padx=15, pady=10)
    
    ctk.CTkLabel(date_wage_frame, text="Month:", font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=5, pady=5)
    temp_date_entry = ctk.CTkEntry(date_wage_frame, width=150, placeholder_text="DD/MM/YYYY", height=35)
    temp_date_entry.grid(row=0, column=1, padx=5, pady=5)
    ctk.CTkButton(date_wage_frame, text="📅", width=40, height=35, 
                 command=lambda: show_calendar(temp_date_entry)).grid(row=0, column=2, padx=5, pady=5)
    
    ctk.CTkLabel(date_wage_frame, text="Wage (PKR):", font=ctk.CTkFont(size=11)).grid(row=0, column=3, padx=5, pady=5)
    temp_wage_entry = ctk.CTkEntry(date_wage_frame, width=150, placeholder_text="Wage Amount", height=35)
    temp_wage_entry.grid(row=0, column=4, padx=5, pady=5)
    
    ctk.CTkLabel(date_wage_frame, text="Reason:", font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=5, pady=5)
    temp_reason_entry = ctk.CTkEntry(date_wage_frame, width=400, placeholder_text="e.g., Half month worked", height=35)
    temp_reason_entry.grid(row=1, column=1, columnspan=4, padx=5, pady=5)
    
    list_frame = ctk.CTkFrame(dialog, fg_color=COLORS['bg_hover'])
    list_frame.pack(fill="both", expand=True, padx=15, pady=10)
    
    ctk.CTkLabel(list_frame, text="CURRENT TEMPORARY CHANGES", font=ctk.CTkFont(size=14, weight="bold"), 
                text_color=COLORS['warning']).pack(pady=10)
    
    temp_listbox = tk.Listbox(list_frame, bg="#2b2b2b", fg="white", 
                              selectbackground=COLORS['accent'],
                              font=('Segoe UI', 10), height=8)
    temp_listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
    temp_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=temp_listbox.yview)
    temp_listbox.configure(yscrollcommand=temp_scroll.set)
    temp_scroll.pack(side="right", fill="y")
    
    def refresh_temp_list():
        temp_listbox.delete(0, tk.END)
        for key, value in temporary_changes.items():
            main, sub, month, claimant = key
            cursor.execute("SELECT name FROM employers WHERE main_code=? AND sub_code=?", (main, sub))
            emp_name = cursor.fetchone()
            emp_name = emp_name[0][:20] if emp_name else f"{main}-{sub}"
            d = datetime.strptime(month, "%Y-%m")
            temp_listbox.insert(tk.END, f"{emp_name} | {d.strftime('%b %Y')} | Rs. {value['wage']:,.2f} | {value['reason'][:30]}")
    
    def add_temp_change():
        claimant = claimant_entry.get().strip()
        if not claimant:
            messagebox.showwarning("Warning", "Please enter claimant name!")
            return
        
        if emp_var.get() in ["Select Employer", "No employers"]:
            messagebox.showwarning("Warning", "Please select an employer!")
            return
        
        try:
            date = datetime.strptime(temp_date_entry.get(), "%d/%m/%Y")
            wage = float(temp_wage_entry.get())
            reason = temp_reason_entry.get().strip()
            
            if not reason:
                messagebox.showwarning("Warning", "Please enter a reason!")
                return
            
            emp_str = emp_var.get()
            main = emp_str.split("(")[1].split("-")[0].strip()
            sub = emp_str.split("-")[1].split(")")[0].strip()
            
            month_key = get_month_key_from_date(date)
            key = (main, sub, month_key, claimant)
            
            temporary_changes[key] = {'wage': wage, 'reason': reason}
            
            refresh_temp_list()
            messagebox.showinfo("Success", f"Temporary wage change added!\nMonth: {date.strftime('%B %Y')}\nWage: Rs. {wage:,.2f}")
            
            temp_date_entry.delete(0, 'end')
            temp_wage_entry.delete(0, 'end')
            temp_reason_entry.delete(0, 'end')
            
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
    
    def remove_temp_change():
        selection = temp_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a temporary change to remove!")
            return
        
        index = selection[0]
        keys = list(temporary_changes.keys())
        if index < len(keys):
            del temporary_changes[keys[index]]
            refresh_temp_list()
            messagebox.showinfo("Success", "Temporary change removed!")
    
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(fill="x", padx=15, pady=10)
    
    ctk.CTkButton(btn_frame, text="➕ Add Temporary Change", command=add_temp_change,
                 fg_color=COLORS['accent'], height=40, width=180).pack(side="left", padx=5)
    ctk.CTkButton(btn_frame, text="❌ Remove Selected", command=remove_temp_change,
                 fg_color=COLORS['error'], height=40, width=150).pack(side="left", padx=5)
    ctk.CTkButton(btn_frame, text="✅ Save & Close", command=dialog.destroy,
                 fg_color=COLORS['success'], height=40, width=130).pack(side="right", padx=5)
    
    refresh_temp_list()

def add_employment_period():
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("750x700")
    dialog.title("Add Employment Period")
    dialog.grab_set()

    main_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)

    header = ctk.CTkFrame(main_frame, fg_color=COLORS['primary'], height=60, corner_radius=10)
    header.pack(fill="x", pady=(0,15))
    ctk.CTkLabel(header, text="ADD EMPLOYMENT PERIOD", font=ctk.CTkFont(size=20, weight="bold"), 
                text_color="white").pack(expand=True)

    step1_frame = ctk.CTkFrame(main_frame, fg_color=COLORS['bg_hover'], corner_radius=10)
    step1_frame.pack(fill="x", pady=10)
    ctk.CTkLabel(step1_frame, text="STEP 1: SELECT DATE RANGE", font=ctk.CTkFont(size=16, weight="bold"), 
                text_color=COLORS['primary']).pack(pady=(10,5))
    ctk.CTkLabel(step1_frame, text="Actual dates are used for service days; wages are still recorded month-wise.", 
                font=ctk.CTkFont(size=10), text_color="gray").pack()
    
    date_container = ctk.CTkFrame(step1_frame, fg_color="transparent")
    date_container.pack(pady=10)
    
    from_frame = ctk.CTkFrame(date_container, fg_color=COLORS['bg_card'], corner_radius=8)
    from_frame.pack(side="left", padx=20, pady=10)
    ctk.CTkLabel(from_frame, text="START DATE", font=ctk.CTkFont(size=13, weight="bold"), 
                text_color=COLORS['success']).pack(pady=(8,3))
    entry_from_period = ctk.CTkEntry(from_frame, width=180, placeholder_text="DD/MM/YYYY", height=45, 
                                     font=ctk.CTkFont(size=15), justify="center")
    entry_from_period.pack(padx=15, pady=5)
    ctk.CTkButton(from_frame, text="Pick Start Date", command=lambda: show_calendar(entry_from_period),
                 fg_color=COLORS['primary'], height=35, width=150).pack(pady=(0,10), padx=15)
    
    to_frame = ctk.CTkFrame(date_container, fg_color=COLORS['bg_card'], corner_radius=8)
    to_frame.pack(side="left", padx=20, pady=10)
    ctk.CTkLabel(to_frame, text="END DATE", font=ctk.CTkFont(size=13, weight="bold"), 
                text_color=COLORS['error']).pack(pady=(8,3))
    entry_to_period = ctk.CTkEntry(to_frame, width=180, placeholder_text="DD/MM/YYYY", height=45,
                                   font=ctk.CTkFont(size=15), justify="center")
    entry_to_period.pack(padx=15, pady=5)
    ctk.CTkButton(to_frame, text="Pick End Date", command=lambda: show_calendar(entry_to_period),
                 fg_color=COLORS['primary'], height=35, width=150).pack(pady=(0,10), padx=15)

    step2_frame = ctk.CTkFrame(main_frame, fg_color=COLORS['bg_hover'], corner_radius=10)
    step2_frame.pack(fill="x", pady=10)
    ctk.CTkLabel(step2_frame, text="STEP 2: SELECT EMPLOYER(S)", font=ctk.CTkFont(size=16, weight="bold"), 
                text_color=COLORS['secondary']).pack(pady=(10,5))
    
    ctk.CTkLabel(step2_frame, text="Tip: Hold Ctrl to select multiple employers", 
                font=ctk.CTkFont(size=11), text_color="gray").pack()
    
    search_frame = ctk.CTkFrame(step2_frame, fg_color="transparent")
    search_frame.pack(fill="x", padx=15, pady=10)
    entry_search_period = ctk.CTkEntry(search_frame, placeholder_text="Filter employers...", 
                                       height=38, font=ctk.CTkFont(size=13))
    entry_search_period.pack(side="left", fill="x", expand=True, padx=(0,10))
    ctk.CTkButton(search_frame, text="Clear", width=70, height=38,
                 command=lambda: entry_search_period.delete(0, 'end') or update_emp_list(),
                 fg_color=COLORS['secondary']).pack(side="right")
    
    counter_label = ctk.CTkLabel(step2_frame, text="Selected: 0 employer(s)", 
                                 font=ctk.CTkFont(size=12, weight="bold"), 
                                 text_color=COLORS['warning'])
    counter_label.pack(pady=5)
    
    emp_list_frame = ctk.CTkFrame(step2_frame, fg_color=COLORS['bg_dark'])
    emp_list_frame.pack(fill="both", padx=15, pady=10)
    
    emp_listbox = tk.Listbox(emp_list_frame, bg="#2b2b2b", fg="white", 
                            selectbackground=COLORS['primary_light'],
                            selectmode=tk.MULTIPLE,
                            font=('Segoe UI', 11), height=8,
                            exportselection=False, activestyle='none')
    emp_listbox.pack(side="left", fill="both", expand=True)
    emp_scrollbar = ttk.Scrollbar(emp_list_frame, orient="vertical", command=emp_listbox.yview)
    emp_listbox.configure(yscrollcommand=emp_scrollbar.set)
    emp_scrollbar.pack(side="right", fill="y")

    all_employers = cursor.execute("SELECT main_code, sub_code, name FROM employers ORDER BY name").fetchall()
    employer_map = {}

    def update_emp_list(*args):
        emp_listbox.delete(0, tk.END)
        employer_map.clear()
        search_term = entry_search_period.get().lower()
        for main, sub, name in all_employers:
            if search_term in name.lower() or search_term in main.lower() or search_term in sub.lower():
                display = f"{name} ({main}-{sub})"
                emp_listbox.insert(tk.END, display)
                employer_map[display] = (main, sub, name)
        update_counter()
    
    def update_counter(*args):
        count = len(emp_listbox.curselection())
        counter_label.configure(text=f"Selected: {count} employer(s)")

    emp_listbox.bind('<<ListboxSelect>>', update_counter)
    update_emp_list()
    entry_search_period.bind('<KeyRelease>', update_emp_list)

    step3_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    step3_frame.pack(fill="x", pady=15)
    
    def add_period():
        try:
            from_d = datetime.strptime(entry_from_period.get(), "%d/%m/%Y")
            to_d = datetime.strptime(entry_to_period.get(), "%d/%m/%Y")
        except:
            messagebox.showerror("Error", "Invalid date format! Use DD/MM/YYYY")
            return
        
        if from_d > to_d:
            messagebox.showerror("Error", "Start date must be before End date!")
            return

        if from_d < SCHEME_START_DATE:
            messagebox.showerror("Error", "EOBI wage calculation starts from 01/07/1976.")
            return

        if to_d.date() > datetime.now().date():
            messagebox.showerror("Error", "End date cannot be after today.")
            return
        
        selected_indices = emp_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Error", "Please select at least one employer!")
            return
        
        selected_emps = []
        for i in selected_indices:
            display = emp_listbox.get(i)
            selected_emps.append(employer_map[display])
        
        period_start = from_d
        period_end = to_d
        
        period = {'from': period_start, 'to': period_end, 'employers': selected_emps}
        employment_periods.append(period)
        update_periods_display()
        update_wage_status()
        
        total_days = (period_end - period_start).days + 1
        dialog.destroy()
        messagebox.showinfo("Period Added Successfully!", 
            f"Period: {period_start.strftime('%d/%m/%Y')} to {period_end.strftime('%d/%m/%Y')}\n"
            f"Total Days: {total_days}\n"
            f"Employers: {len(selected_emps)}\n\n"
            f"Note: Service years are calculated from actual days.")

    ctk.CTkLabel(step3_frame, text="STEP 3: ADD PERIOD", font=ctk.CTkFont(size=16, weight="bold"), 
                text_color=COLORS['success']).pack(pady=(0,10))
    
    ctk.CTkButton(step3_frame, text="ADD EMPLOYMENT PERIOD", command=add_period, 
                 fg_color=COLORS['success'], height=50, width=300, 
                 font=ctk.CTkFont(size=15, weight="bold")).pack(pady=5)
    ctk.CTkButton(step3_frame, text="Cancel", command=dialog.destroy, 
                 fg_color=COLORS['error'], height=40, width=150).pack(pady=10)

def remove_period():
    selection = periods_listbox.curselection()
    if selection:
        index = selection[0]
        if messagebox.askyesno("Confirm", "Remove this employment period?"):
            del employment_periods[index]
            update_periods_display()
            update_wage_status()

def update_periods_display():
    periods_listbox.delete(0, tk.END)
    for i, p in enumerate(employment_periods):
        if len(p['employers']) <= 2:
            employers_str = ", ".join([f"{e[2]}" for e in p['employers']])
        else:
            employers_str = f"{p['employers'][0][2]}, {p['employers'][1][2]} +{len(p['employers'])-2} more"
        total_days = (p['to'] - p['from']).days + 1
        periods_listbox.insert(tk.END, 
            f"Period {i+1}: {p['from'].strftime('%d/%m/%Y')} - {p['to'].strftime('%d/%m/%Y')} ({total_days} days) | {employers_str}")

def get_days_in_month(year, month):
    return calendar.monthrange(year, month)[1]

def show_claim_type_dialog():
    """Dialog to set claim type (self or survivor)"""
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("550x600")
    dialog.title("Claim Type Selection")
    dialog.grab_set()
    
    header = ctk.CTkFrame(dialog, fg_color=COLORS['survivor'], height=60, corner_radius=10)
    header.pack(fill="x", padx=20, pady=20)
    ctk.CTkLabel(header, text="CLAIM TYPE SELECTION", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(expand=True)
    
    type_frame = ctk.CTkFrame(dialog, fg_color=COLORS['bg_hover'])
    type_frame.pack(fill="x", padx=20, pady=10)
    
    ctk.CTkLabel(type_frame, text="Select Claim Type:", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
    
    claim_var = tk.StringVar(value=claim_type)
    
    ctk.CTkRadioButton(type_frame, text="Insured Person (Own OAP/OAG Claim)", variable=claim_var, value="self",
                      font=ctk.CTkFont(size=13), fg_color=COLORS['primary']).pack(pady=8, padx=20, anchor="w")
    ctk.CTkRadioButton(type_frame, text="Survivor (Heir/Family Member)", variable=claim_var, value="survivor",
                      font=ctk.CTkFont(size=13), fg_color=COLORS['survivor']).pack(pady=8, padx=20, anchor="w")
    
    survivor_frame = ctk.CTkFrame(dialog, fg_color=COLORS['bg_hover'])
    survivor_frame.pack(fill="x", padx=20, pady=10)
    
    ctk.CTkLabel(survivor_frame, text="SURVIVOR DETAILS (if applicable)", font=ctk.CTkFont(size=14, weight="bold"), 
                text_color=COLORS['survivor']).pack(pady=10)
    
    ctk.CTkLabel(survivor_frame, text="Death Date:", font=ctk.CTkFont(size=11)).pack(pady=(5,0))
    death_entry = ctk.CTkEntry(survivor_frame, width=200, placeholder_text="DD/MM/YYYY", height=35)
    death_entry.pack(pady=3)
    if death_date:
        death_entry.insert(0, death_date)
    ctk.CTkButton(survivor_frame, text="Pick Date", command=lambda: show_calendar(death_entry), 
                 height=28, width=100).pack(pady=3)
    
    survivor_type_var = tk.StringVar(value=survivor_type if survivor_type else "died_during_service")
    
    ctk.CTkLabel(survivor_frame, text="Death Circumstances:", font=ctk.CTkFont(size=11, weight="bold")).pack(pady=(10,3))
    ctk.CTkRadioButton(survivor_frame, text="Died before 60 during service / insurable employment", variable=survivor_type_var, 
                      value="died_during_service", font=ctk.CTkFont(size=11), fg_color=COLORS['warning']).pack(pady=3, padx=20, anchor="w")
    ctk.CTkRadioButton(survivor_frame, text="Died before 60 while not in service", variable=survivor_type_var, 
                      value="died_not_in_service", font=ctk.CTkFont(size=11), fg_color=COLORS['warning']).pack(pady=3, padx=20, anchor="w")
    ctk.CTkRadioButton(survivor_frame, text="Died after 60 years of age", variable=survivor_type_var, 
                      value="died_after_60", font=ctk.CTkFont(size=11), fg_color=COLORS['warning']).pack(pady=3, padx=20, anchor="w")
    
    def save_claim_type():
        global claim_type, survivor_type, death_date
        claim_type = claim_var.get()
        survivor_type = survivor_type_var.get()
        death_date = death_entry.get().strip()
        
        if claim_type == "survivor":
            if not death_date:
                messagebox.showwarning("Warning", "Please enter death date for survivor claim!")
                return
            try:
                datetime.strptime(death_date, "%d/%m/%Y")
            except:
                messagebox.showerror("Error", "Invalid death date format! Use DD/MM/YYYY")
                return
        
        dialog.destroy()
        update_claim_display()
        
        if claim_type == "survivor":
            messagebox.showinfo("Claim Type Set", 
                f"Claim Type: SURVIVOR\n"
                f"Death Date: {death_date}\n"
                f"Circumstances: {survivor_type.replace('_', ' ').title()}\n\n"
                f"Survivor pension eligibility will be calculated based on contribution history.")
        else:
            messagebox.showinfo("Claim Type Set", "Claim Type: INSURED PERSON\n\nOAP/OAG rules will apply.")
    
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=15)
    ctk.CTkButton(btn_frame, text="Save Claim Type", command=save_claim_type, 
                 fg_color=COLORS['survivor'], height=40, width=160).pack(side="left", padx=10)
    ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy, 
                 fg_color=COLORS['error'], height=40, width=100).pack(side="left", padx=10)

def update_claim_display():
    """Update the UI with current claim type"""
    if claim_type == "survivor":
        claim_label.configure(text=f"Claim Type: SURVIVOR | Death: {death_date} | {survivor_type.replace('_', ' ').title()}", 
                            fg_color=COLORS['survivor'])
    else:
        claim_label.configure(text="Claim Type: INSURED PERSON (Self)", fg_color=COLORS['primary'])

def check_survivor_eligibility():
    """Check survivor pension eligibility based on rules"""
    global survivor_eligible, survivor_pension, last_36_months_continuous, survivor_service_years
    
    if claim_type != "survivor":
        return
    
    if not death_date or not employment_periods:
        return
    
    try:
        death_dt = datetime.strptime(death_date, "%d/%m/%Y")
    except:
        return
    
    paid_months = {d for d, w in combined_wages.items() if w > 0}
    if not paid_months:
        survivor_eligible = False
        survivor_service_years = 0.0
        return

    covered_months = set()
    total_period_days = 0
    for period in employment_periods:
        total_period_days += (period['to'] - period['from']).days + 1
        covered_months.update(iter_month_starts(period['from'], period['to']))

    zero_month_dates = {m for m in covered_months if combined_wages.get(m, 0) <= 0}
    zero_days = sum(get_days_in_month(d.year, d.month) for d in zero_month_dates)
    paid_service_days = max(0, total_period_days - zero_days)
    paid_service_days = int(paid_service_days * (work_percentage / 100.0))
    survivor_service_years = service_years_from_days(paid_service_days)

    death_month = normalize_date_to_month(death_dt)
    check_months = []
    current = death_month
    for i in range(SURVIVOR_CONTINUOUS_MONTHS):
        check_months.append(current)
        if current.month == 1:
            current = current.replace(year=current.year - 1, month=12)
        else:
            current = current.replace(month=current.month - 1)
    
    check_months.reverse()
    last_36_months_continuous = all(combined_wages.get(m, 0) > 0 for m in check_months)
    if work_percentage < 100:
        last_36_months_continuous = False
    
    if survivor_type == "died_during_service":
        survivor_eligible = (
            last_36_months_continuous or
            survivor_service_years >= SURVIVOR_REQUIRED_YEARS_BEFORE_60
        )
    elif survivor_type == "died_not_in_service":
        survivor_eligible = survivor_service_years >= SURVIVOR_REQUIRED_YEARS_BEFORE_60
    elif survivor_type == "died_after_60":
        survivor_eligible = survivor_service_years >= SURVIVOR_REQUIRED_YEARS_AFTER_60
    else:
        survivor_eligible = False
    
    survivor_pension = MIN_PENSION if survivor_eligible else 0

def show_work_percentage_dialog():
    """Dialog to set work percentage and remarks"""
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("500x450")
    dialog.title("Work Days Percentage & Remarks")
    dialog.grab_set()
    
    header = ctk.CTkFrame(dialog, fg_color=COLORS['primary'], height=60, corner_radius=10)
    header.pack(fill="x", padx=20, pady=20)
    ctk.CTkLabel(header, text="WORK DAYS PERCENTAGE", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(expand=True)
    
    ctk.CTkLabel(dialog, text="Set the percentage of days actually worked during the period.", 
                font=ctk.CTkFont(size=12), text_color="gray").pack(pady=10)
    
    total_period_days = sum((p['to'] - p['from']).days + 1 for p in employment_periods)
    ctk.CTkLabel(dialog, text=f"Total Period Days: {total_period_days}", 
                font=ctk.CTkFont(size=13, weight="bold")).pack(pady=5)
    
    pct_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    pct_frame.pack(pady=10)
    
    ctk.CTkLabel(pct_frame, text="Work Percentage (%):", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=10, pady=5)
    pct_entry = ctk.CTkEntry(pct_frame, width=150, height=35, font=ctk.CTkFont(size=14))
    pct_entry.grid(row=0, column=1, padx=10, pady=5)
    pct_entry.insert(0, str(work_percentage))
    
    ctk.CTkLabel(pct_frame, text="%", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=5, pady=5)
    
    result_label = ctk.CTkLabel(dialog, text=f"Actual Work Days: {int(total_period_days * work_percentage / 100)}", 
                               font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS['success'])
    result_label.pack(pady=5)
    
    def update_days(*args):
        try:
            pct = float(pct_entry.get())
            if 0 < pct <= 100:
                actual_days = int(total_period_days * pct / 100)
                result_label.configure(text=f"Actual Work Days: {actual_days} ({pct}% of {total_period_days})")
            else:
                result_label.configure(text="Please enter a value between 1 and 100")
        except:
            result_label.configure(text="Invalid percentage")
    
    pct_entry.bind('<KeyRelease>', update_days)
    
    ctk.CTkLabel(dialog, text="━━━━━━━━━━━━━━━━", text_color="gray").pack(pady=5)
    ctk.CTkLabel(dialog, text="REMARKS (Optional):", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=5)
    remarks_entry = ctk.CTkTextbox(dialog, height=80, font=ctk.CTkFont(size=12))
    remarks_entry.pack(padx=20, pady=5, fill="x")
    remarks_entry.insert("1.0", remarks_text)
    
    def save_settings():
        global work_percentage, actual_work_days, adjusted_oag_average, adjusted_years, remarks_text
        try:
            pct = float(pct_entry.get())
            if not (0 < pct <= 100):
                messagebox.showwarning("Warning", "Percentage must be between 1 and 100!")
                return
            work_percentage = pct
            actual_work_days = int(total_period_days * pct / 100)
            remarks_text = remarks_entry.get("1.0", "end-1c").strip()
            
            if final_avg_value > 0 and total_months_in_period > 0:
                adjusted_years = service_years_from_days(actual_work_days)
                adjusted_oag_average = round(final_avg_value * (pct / 100), 2)
            else:
                adjusted_years = 0
                adjusted_oag_average = 0
            
            dialog.destroy()
            update_percentage_display()
            messagebox.showinfo("Settings Saved", 
                f"Work Percentage: {pct}%\n"
                f"Actual Work Days: {actual_work_days}\n"
                f"Adjusted OAG Average: Rs. {adjusted_oag_average:,.2f}\n"
                f"Adjusted Years: {adjusted_years:.2f}\n\n"
                f"Remarks: {remarks_text if remarks_text else 'None'}")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
    
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=15)
    ctk.CTkButton(btn_frame, text="Save Settings", command=save_settings, 
                 fg_color=COLORS['success'], height=40, width=150).pack(side="left", padx=10)
    ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy, 
                 fg_color=COLORS['error'], height=40, width=100).pack(side="left", padx=10)

def update_percentage_display():
    """Update the UI with percentage-based calculations"""
    if work_percentage < 100 and final_avg_value > 0:
        pct_text = f"📊 WORK PERCENTAGE: {work_percentage}% | Actual Days: {actual_work_days} | Adjusted OAG Avg: Rs. {adjusted_oag_average:,.2f} | Adjusted Years: {adjusted_years:.2f}"
        percentage_label.configure(text=pct_text, fg_color=COLORS['secondary'])
    elif final_avg_value > 0:
        percentage_label.configure(text=f"Work Percentage: 100% | Actual Days: {actual_work_days} | Service Years: {adjusted_years:.2f}", fg_color=COLORS['success'])
    else:
        percentage_label.configure(text="Work Percentage: 100% (Full Period)", fg_color=COLORS['success'])

def calculate():
    global yearly_data, less_months, final_avg_value, last12_avg_value, total_months_worked, qualifying_years
    global duplicate_warnings, missing_periods, zero_wage_months, lesser_rate_months, total_oag_amount, total_oap_amount, oap_eligible
    global combined_wages, oap_qualifying_period_years, total_months_in_period
    global work_percentage, actual_work_days, adjusted_oag_average, adjusted_years
    global survivor_eligible, survivor_pension, last_36_months_continuous
    global oap_formula_years, lesser_rate_years, zero_wage_years, survivor_service_years
    
    yearly_data = []; less_months = 0; total_months_worked = 0; qualifying_years = 0
    duplicate_warnings = []; missing_periods = []; zero_wage_months = []; lesser_rate_months = []
    total_oag_amount = 0; total_oap_amount = 0; oap_eligible = False
    combined_wages = {}; oap_qualifying_period_years = 0.0; total_months_in_period = 0
    oap_formula_years = 0.0; lesser_rate_years = 0.0; zero_wage_years = 0.0; survivor_service_years = 0.0
    survivor_eligible = False; survivor_pension = 0; last_36_months_continuous = False

    if not employment_periods:
        messagebox.showwarning("Warning", "Please add at least one employment period")
        return

    claimant = entry_claimant.get().strip()

    all_missing_months = []
    
    for period in employment_periods:
        for main, sub, name in period['employers']:
            from_month_key = get_month_key_from_date(period['from'])
            to_month_key = get_month_key_from_date(period['to'])
            
            cursor.execute("""
                SELECT month, wage FROM wages 
                WHERE main_code=? AND sub_code=? 
                AND month >= ? AND month <= ?
                ORDER BY month
            """, (main, sub, from_month_key, to_month_key))
            
            existing_months = {}
            for (m, w) in cursor.fetchall():
                existing_months[datetime.strptime(m, "%Y-%m")] = w
            
            expected_months = list(iter_month_starts(period['from'], period['to']))
            
            missing = []
            for expected in expected_months:
                if expected not in existing_months:
                    missing.append(expected)
            
            if missing:
                all_missing_months.append((name, main, sub, period, missing))
    
    if all_missing_months:
        error_msg = "CANNOT CALCULATE!\n\nWAGES ARE MISSING FOR THESE PERIODS:\n\n"
        
        for name, main, sub, period, missing in all_missing_months[:5]:
            error_msg += f"Employer: {name} ({main}-{sub})\n"
            error_msg += f"Period: {period['from'].strftime('%d/%m/%Y')} to {period['to'].strftime('%d/%m/%Y')}\n"
            error_msg += f"Missing {len(missing)} month(s):\n"
            for m in missing[:3]:
                error_msg += f"  • {m.strftime('%B %Y')}\n"
            if len(missing) > 3:
                error_msg += f"  • ... and {len(missing)-3} more\n"
            error_msg += "\n"
        
        if len(all_missing_months) > 5:
            error_msg += f"... and {len(all_missing_months)-5} more employers\n\n"
        
        error_msg += "Please add wages for ALL missing periods before calculating."
        
        messagebox.showerror("Calculation Blocked", error_msg)
        return

    total_period_days = 0
    total_zero_days = 0
    covered_months = set()
    
    for period in employment_periods:
        period_days = (period['to'] - period['from']).days + 1
        total_period_days += period_days
        
        for month_start in iter_month_starts(period['from'], period['to']):
            covered_months.add(month_start)
        
        for main, sub, name in period['employers']:
            from_month_key = get_month_key_from_date(period['from'])
            to_month_key = get_month_key_from_date(period['to'])
            
            cursor.execute("""
                SELECT month, wage FROM wages 
                WHERE main_code=? AND sub_code=? 
                AND month >= ? AND month <= ?
                ORDER BY month
            """, (main, sub, from_month_key, to_month_key))
            
            for m, w in cursor.fetchall():
                d = datetime.strptime(m, "%Y-%m")
                
                if claimant:
                    temp_key = (main, sub, m, claimant)
                    if temp_key in temporary_changes:
                        w = temporary_changes[temp_key]['wage']
                
                if w == 0:
                    zero_wage_months.append((name, main, sub, d))
                    total_zero_days += get_days_in_month(d.year, d.month)
                    continue
                
                min_wage = get_min(m)
                if w < min_wage:
                    lesser_rate_months.append((name, main, sub, d, w, min_wage))
                
                if d in combined_wages:
                    combined_wages[d] += w
                    duplicate_warnings.append(d.strftime('%b %Y'))
                else:
                    combined_wages[d] = w

    total_months_in_period = len(covered_months)

    if claimant and temporary_changes:
        for (main, sub, month, cl), temp_data in temporary_changes.items():
            if cl == claimant:
                d = datetime.strptime(month, "%Y-%m")
                combined_wages[d] = temp_data['wage']

    active_wages = sorted([(d, w) for d, w in combined_wages.items() if w > 0], key=lambda x: x[0])
    total_months_worked = len(active_wages)

    overall_start = min(p['from'] for p in employment_periods)
    overall_end = max(p['to'] for p in employment_periods)

    zero_month_dates = {m for m in covered_months if combined_wages.get(m, 0) <= 0}
    lesser_rate_month_dates = {
        d for d, w in active_wages
        if get_min(d.strftime("%Y-%m")) and w < get_min(d.strftime("%Y-%m"))
    }
    less_months = len(lesser_rate_month_dates)

    table_year.delete(*table_year.get_children())
    yearly_data = []
    yearly_averages = []
    
    wage_index = 0
    year_num = 1
    
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
            
            if months_collected == 12:
                status = f"Complete Year ({months_collected}/12 months)"
                qualifies = True
            elif months_collected >= OAG_PARTIAL_YEAR_MONTHS:
                status = f"Partial Year ({months_collected}/12 months) - QUALIFIES"
                qualifies = True
            else:
                status = f"Partial Year ({months_collected}/12 months) - DOES NOT QUALIFY"
                qualifies = False
            
            if qualifies:
                qualifying_years += 1
                yearly_averages.append(year_avg)
            
            period_start_display = get_month_start_date(year_start_actual)
            period_end_display = get_month_end_date(year_end_actual)
            
            yearly_data.append((year_num, year_start_actual, year_end_actual, year_avg, months_collected, qualifies, status, year_days))
            table_year.insert("", "end", values=(
                f"Year {year_num}",
                f"{period_start_display.strftime('%d/%m/%Y')} - {period_end_display.strftime('%d/%m/%Y')}",
                f"Rs. {round(year_avg,2):,}",
                f"{months_collected}/12",
                status,
                f"{year_days} days"
            ))
        
        wage_index = temp_index
        year_num += 1

    final_avg_value = round(sum(yearly_averages)/len(yearly_averages), 2) if yearly_averages else 0
    total_oag_amount = round(final_avg_value * qualifying_years, 2)
    
    last12 = active_wages[-12:] if len(active_wages) >= 12 else active_wages
    last12_with_temp = []
    for d, w in last12:
        month_key = d.strftime("%Y-%m")
        temp_wage_applied = False
        if claimant and temporary_changes:
            for (main, sub, month, cl), temp_data in temporary_changes.items():
                if cl == claimant and month == month_key:
                    last12_with_temp.append(temp_data['wage'])
                    temp_wage_applied = True
                    break
        if not temp_wage_applied:
            last12_with_temp.append(w)
    
    last12_avg_value = sum(last12_with_temp) / len(last12_with_temp) if last12_with_temp else 0
    
    zero_wage_months_count = len(zero_month_dates)

    percentage_factor = work_percentage / 100.0
    effective_service_days = int(total_period_days * percentage_factor)
    actual_work_days = effective_service_days
    oap_qualifying_period_years = service_years_from_days(effective_service_days)

    zero_days_for_formula = sum(get_days_in_month(d.year, d.month) for d in zero_month_dates)
    lesser_days_for_formula = sum(get_days_in_month(d.year, d.month) for d in lesser_rate_month_dates)
    total_zero_days = zero_days_for_formula
    zero_wage_years = service_years_from_days(int(zero_days_for_formula * percentage_factor))
    lesser_rate_years = service_years_from_days(int(lesser_days_for_formula * percentage_factor))
    oap_formula_years = max(0.0, round(oap_qualifying_period_years - lesser_rate_years - zero_wage_years, 4))
    oap_eligible = oap_qualifying_period_years >= OAP_REQUIRED_YEARS

    if oap_eligible:
        raw_oap = (last12_avg_value * oap_formula_years) / 50
        total_oap_amount = max(MIN_PENSION, round(raw_oap, 2))
    else:
        total_oap_amount = 0

    if work_percentage < 100:
        adjusted_years = round(oap_qualifying_period_years, 2)
        adjusted_oag_average = round(final_avg_value * percentage_factor, 2)
    else:
        adjusted_years = round(oap_qualifying_period_years, 2)
        adjusted_oag_average = final_avg_value

    # Check survivor eligibility
    check_survivor_eligibility()

    # Update display based on claim type
    if claim_type == "survivor":
        if survivor_eligible:
            result.configure(text=f"Decision: Survivor Pension Eligible | Pension: PKR {survivor_pension:,.2f} per month")
            last12_result.configure(text=f"36 Continuous Paid Months: {'YES' if last_36_months_continuous else 'NO'} | Paid Service: {survivor_service_years:.2f} years")
        else:
            result.configure(text="Decision: Survivor Pension Not Eligible")
            last12_result.configure(text=f"36 Continuous Paid Months: {'YES' if last_36_months_continuous else 'NO'} | Paid Service: {survivor_service_years:.2f} years")
    else:
        if oap_eligible:
            result.configure(text=f"Decision: OAP Pension Eligible | Final Pension: PKR {total_oap_amount:,.2f} per month")
        else:
            result.configure(text=f"Decision: OAG Eligible | OAG Average Wage: Rs. {final_avg_value:,.2f}")
        last12_result.configure(text=f"OAP Average: Rs. {round(last12_avg_value,2):,.2f} | Service: {oap_qualifying_period_years:.2f} years | Formula Years: {oap_formula_years:.2f}")
    
    update_percentage_display()
    
    warning_parts = []
    if claim_type == "survivor":
        if survivor_eligible:
            warning_parts.append(f"SURVIVOR ELIGIBLE - Pension: PKR {survivor_pension:,.2f}/month")
            warning_parts.append(f"Death Circumstances: {survivor_type.replace('_', ' ').title()}")
            warning_parts.append(f"Paid Service: {survivor_service_years:.2f} years")
        else:
            warning_parts.append("SURVIVOR NOT ELIGIBLE")
            warning_parts.append(f"Death Circumstances: {survivor_type.replace('_', ' ').title()}")
            warning_parts.append(f"Paid Service: {survivor_service_years:.2f} years")
            if survivor_type == "died_during_service":
                warning_parts.append(f"Required: {SURVIVOR_CONTINUOUS_MONTHS} continuous paid months OR {SURVIVOR_REQUIRED_YEARS_BEFORE_60} paid service years")
            elif survivor_type == "died_not_in_service":
                warning_parts.append(f"Required: {SURVIVOR_REQUIRED_YEARS_BEFORE_60} paid service years")
            elif survivor_type == "died_after_60":
                warning_parts.append(f"Required: {SURVIVOR_REQUIRED_YEARS_AFTER_60} paid service years")
    else:
        if less_months > 0:
            warning_parts.append(f"{less_months} months contribution paid at lesser rate ({lesser_rate_years:.2f} years)")
        if duplicate_warnings:
            unique_dupes = list(set(duplicate_warnings))
            warning_parts.append(f"{len(unique_dupes)} months have wages from multiple employers")
        if zero_wage_months_count:
            warning_parts.append(f"{zero_wage_months_count} months with no contribution paid ({zero_wage_years:.2f} years)")
        if temporary_changes and claimant:
            temp_count = sum(1 for k in temporary_changes if k[3] == claimant)
            if temp_count > 0:
                warning_parts.append(f"{temp_count} temporary wage changes applied")
        if work_percentage < 100:
            warning_parts.append(f"Work Percentage: {work_percentage}% ({actual_work_days} actual days / {oap_qualifying_period_years:.2f} years)")
        if not oap_eligible:
            warning_parts.append(f"OAP NOT ELIGIBLE: Service ({oap_qualifying_period_years:.2f} years) is less than {OAP_REQUIRED_YEARS} years")
            warning_parts.append("Recommended report: OAG Calculation Report")
        else:
            warning_parts.append(f"OAP ELIGIBLE: Service {oap_qualifying_period_years:.2f} years (required {OAP_REQUIRED_YEARS})")
            warning_parts.append(f"Formula Years: {oap_formula_years:.2f} = service - lesser - zero")
            warning_parts.append(f"OAP Pension: PKR {total_oap_amount:,.2f} per month (minimum PKR {MIN_PENSION:,.0f})")
    
    if warning_parts:
        if claim_type == "survivor":
            if survivor_eligible:
                lesser_result.configure(text="\n".join(warning_parts), fg_color=COLORS['success'])
            else:
                lesser_result.configure(text="\n".join(warning_parts), fg_color=COLORS['error'])
        elif oap_eligible:
            lesser_result.configure(text="\n".join(warning_parts), fg_color=COLORS['success'])
        else:
            lesser_result.configure(text="\n".join(warning_parts), fg_color=COLORS['error'])
    else:
        lesser_result.configure(text="No issues detected - all checks passed", fg_color=COLORS['success'])
    
    active_days = total_period_days - total_zero_days
    missing_display.configure(text=f"All months have wages | Total Period Days: {total_period_days} | Active Days: {active_days}", fg_color=COLORS['success'])
    
    if claim_type == "survivor":
        msg = f"Period: {overall_start.strftime('%d/%m/%Y')} to {overall_end.strftime('%d/%m/%Y')}\n"
        msg += f"Total Period Days: {total_period_days}\n"
        msg += f"Paid Service Years: {survivor_service_years:.2f}\n"
        msg += f"Claim Type: SURVIVOR\n"
        msg += f"Death Date: {death_date}\n"
        msg += f"Circumstances: {survivor_type.replace('_', ' ').title()}\n"
        msg += f"36 Continuous Paid Months: {'YES' if last_36_months_continuous else 'NO'}\n"
        msg += f"Survivor Eligible: {'YES' if survivor_eligible else 'NO'}\n"
        if survivor_eligible:
            msg += f"Survivor Pension: PKR {survivor_pension:,.2f} per month"
    else:
        msg = f"Period: {overall_start.strftime('%d/%m/%Y')} to {overall_end.strftime('%d/%m/%Y')}\n"
        msg += f"Total Period Days: {total_period_days}\n"
        msg += f"Total Months in Period: {total_months_in_period}\n"
        msg += f"Active Months (with wages): {total_months_worked}\n"
        msg += f"Lesser Rate Months: {less_months} ({lesser_rate_years:.2f} years)\n"
        msg += f"Zero Wage Months: {zero_wage_months_count} ({zero_wage_years:.2f} years)\n"
        msg += f"OAG Qualifying Years: {qualifying_years}\n"
        msg += f"Service for OAP Eligibility: {oap_qualifying_period_years:.2f} years\n"
        msg += f"OAP Formula Years: {oap_formula_years:.2f}\n"
        msg += f"Recommended Benefit: {'OAP Pension' if oap_eligible else 'OAG'}\n"
        msg += f"OAG Average: Rs. {final_avg_value:,.2f}"
    
    messagebox.showinfo("Calculation Complete!", msg)
    
    update_stats()

def save_calculation_record(report_type):
    global current_record_id
    try:
        zero_month_count_for_record = len({
            d for _, _, _, d in zero_wage_months
            if combined_wages.get(d, 0) <= 0
        })
        cursor.execute("""
            INSERT INTO calculated_records 
            (claimant_name, father_name, eobi_no, cnic_no, calculation_date, 
             oag_average, oap_average, total_oag_amount, total_oap_amount,
             total_months, total_months_in_period, qualifying_years, 
             total_days, zero_wage_months_count, lesser_months_count, 
             periods_data, temporary_changes_data, report_type, oap_eligible,
             work_percentage, actual_work_days, adjusted_oag_average, adjusted_years, remarks,
             claim_type, survivor_type, death_date, last_36_months_continuous, survivor_eligible, survivor_pension)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_claimant.get(),
            entry_father.get(),
            entry_eobi.get(),
            entry_cnic.get(),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            final_avg_value,
            round(last12_avg_value, 2),
            total_oag_amount,
            total_oap_amount,
            total_months_worked,
            total_months_in_period,
            qualifying_years,
            sum((p['to'] - p['from']).days + 1 for p in employment_periods),
            zero_month_count_for_record,
            less_months,
            json.dumps([{'from': p['from'].strftime('%Y-%m-%d'), 'to': p['to'].strftime('%Y-%m-%d'), 
                        'employers': [(e[0], e[1], e[2]) for e in p['employers']]} for p in employment_periods]),
            json.dumps({f"{k[0]}|{k[1]}|{k[2]}|{k[3]}": v for k, v in temporary_changes.items()}),
            report_type,
            1 if oap_eligible else 0,
            work_percentage,
            actual_work_days,
            adjusted_oag_average,
            adjusted_years,
            remarks_text,
            claim_type,
            survivor_type,
            death_date,
            1 if last_36_months_continuous else 0,
            1 if survivor_eligible else 0,
            survivor_pension
        ))
        conn.commit()
        current_record_id = cursor.lastrowid
        return current_record_id
    except Exception as e:
        print(f"Error saving record: {e}")
        return None

def show_calculated_records():
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("1100x650")
    dialog.title("Saved Calculation Records")
    dialog.grab_set()
    
    header = ctk.CTkFrame(dialog, fg_color=COLORS['primary'], height=50, corner_radius=8)
    header.pack(fill="x", padx=12, pady=12)
    ctk.CTkLabel(header, text="SAVED CALCULATION RECORDS", font=ctk.CTkFont(size=18, weight="bold"), 
                text_color="white").pack(expand=True)
    
    search_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    search_frame.pack(fill="x", padx=12, pady=8)
    ctk.CTkLabel(search_frame, text="Search:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=8)
    search_record_entry = ctk.CTkEntry(search_frame, placeholder_text="Search by Name/EOBI/CNIC...", width=250, height=32)
    search_record_entry.pack(side="left", padx=8)
    
    table_frame = ctk.CTkFrame(dialog, fg_color=COLORS['bg_hover'])
    table_frame.pack(fill="both", expand=True, padx=12, pady=8)
    
    columns = ("ID", "Claimant", "Father", "EOBI", "CNIC", "Date", "OAG Avg", "OAP Avg", "Months", "Years", "OAP Eligible", "Claim Type")
    records_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
    
    for col in columns:
        records_table.heading(col, text=col)
        records_table.column(col, width=75)
    
    records_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=records_table.yview)
    records_table.configure(yscrollcommand=records_scroll.set)
    records_table.pack(side="left", fill="both", expand=True)
    records_scroll.pack(side="right", fill="y")
    
    def load_records(search_term=""):
        records_table.delete(*records_table.get_children())
        query = """SELECT id, claimant_name, father_name, eobi_no, cnic_no, 
                   calculation_date, oag_average, oap_average,
                   total_months, qualifying_years, oap_eligible, claim_type
                   FROM calculated_records"""
        
        if search_term:
            query += """ WHERE LOWER(claimant_name) LIKE ? 
                        OR LOWER(eobi_no) LIKE ? 
                        OR LOWER(cnic_no) LIKE ?"""
            cursor.execute(query, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        else:
            cursor.execute(query + " ORDER BY calculation_date DESC")
        
        for row in cursor.fetchall():
            oap_status = "YES" if row[10] == 1 else "NO"
            claim_type_display = row[11] if row[11] else "self"
            records_table.insert("", "end", values=(row[0], row[1], row[2], row[3], row[4], 
                                                     row[5][:10] if row[5] else "", 
                                                     f"Rs. {row[6]:,.2f}" if row[6] else "N/A",
                                                     f"Rs. {row[7]:,.2f}" if row[7] else "N/A",
                                                     row[8], row[9], oap_status, claim_type_display.upper()))
    
    def search_records():
        load_records(search_record_entry.get().lower())
    
    def delete_record():
        selection = records_table.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a record first")
            return
        
        if messagebox.askyesno("Confirm", "Delete this record?"):
            record = records_table.item(selection[0], 'values')
            cursor.execute("DELETE FROM calculated_records WHERE id=?", (record[0],))
            conn.commit()
            load_records()
            update_stats()
    
    def load_record_for_edit():
        selection = records_table.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a record to load!")
            return
        
        record = records_table.item(selection[0], 'values')
        record_id = record[0]
        
        try:
            cursor.execute("""
                SELECT claimant_name, father_name, eobi_no, cnic_no,
                       periods_data, temporary_changes_data, report_type,
                       oag_average, oap_average, total_oag_amount, total_oap_amount,
                       total_months, total_months_in_period, qualifying_years, total_days,
                       zero_wage_months_count, lesser_months_count, oap_eligible,
                       work_percentage, actual_work_days, adjusted_oag_average, adjusted_years, remarks,
                       claim_type, survivor_type, death_date, last_36_months_continuous, survivor_eligible, survivor_pension
                FROM calculated_records WHERE id=?
            """, (record_id,))
            saved = cursor.fetchone()
            
            if not saved:
                messagebox.showerror("Error", "Record not found!")
                return
            
            restore_saved_data({
                'claimant_name': saved[0],
                'father_name': saved[1],
                'eobi_no': saved[2],
                'cnic_no': saved[3],
                'periods_data': saved[4],
                'temporary_changes_data': saved[5],
                'report_type': saved[6],
                'oag_average': saved[7],
                'oap_average': saved[8],
                'total_oag_amount': saved[9],
                'total_oap_amount': saved[10],
                'total_months': saved[11],
                'total_months_in_period': saved[12],
                'qualifying_years': saved[13],
                'total_days': saved[14],
                'zero_wage_months_count': saved[15],
                'lesser_months_count': saved[16],
                'oap_eligible': saved[17],
                'work_percentage': saved[18] if len(saved) > 18 else 100,
                'actual_work_days': saved[19] if len(saved) > 19 else 0,
                'adjusted_oag_average': saved[20] if len(saved) > 20 else 0,
                'adjusted_years': saved[21] if len(saved) > 21 else 0,
                'remarks': saved[22] if len(saved) > 22 else '',
                'claim_type': saved[23] if len(saved) > 23 else 'self',
                'survivor_type': saved[24] if len(saved) > 24 else '',
                'death_date': saved[25] if len(saved) > 25 else '',
                'last_36_months_continuous': saved[26] if len(saved) > 26 else 0,
                'survivor_eligible': saved[27] if len(saved) > 27 else 0,
                'survivor_pension': saved[28] if len(saved) > 28 else 0
            })
            
            global current_record_id
            current_record_id = int(record_id)
            
            dialog.destroy()
            messagebox.showinfo("Record Loaded", 
                f"Record loaded and recalculated successfully!\n\n"
                f"Claimant: {saved[0]}\n"
                f"Record ID: {record_id}\n"
                f"Claim Type: {saved[23] if len(saved) > 23 else 'self'}\n"
                f"OAG Average: Rs. {saved[7]:,.2f}\n"
                f"OAP Average: Rs. {saved[8]:,.2f}\n\n"
                f"You can now modify periods, wages, or temporary changes.\n"
                f"Click 'Calculate Wages' to recalculate and then generate report.")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Could not load record: {str(e)}")
    
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=8)
    ctk.CTkButton(btn_frame, text="Search", command=search_records, width=80, height=32).pack(side="left", padx=3)
    ctk.CTkButton(btn_frame, text="Load & Edit", command=load_record_for_edit, 
                 fg_color=COLORS['success'], width=100, height=32).pack(side="left", padx=3)
    ctk.CTkButton(btn_frame, text="Delete Record", command=delete_record, 
                 fg_color=COLORS['error'], width=100, height=32).pack(side="left", padx=3)
    ctk.CTkButton(btn_frame, text="Close", command=dialog.destroy, width=80, height=32).pack(side="left", padx=3)
    
    load_records()

def restore_saved_data(saved_data):
    """Restore global variables from saved calculation data"""
    global final_avg_value, last12_avg_value, total_oag_amount, total_oap_amount
    global total_months_worked, total_months_in_period, qualifying_years, employment_periods, temporary_changes
    global oap_eligible, combined_wages, oap_qualifying_period_years, yearly_data
    global less_months, zero_wage_months, lesser_rate_months, current_record_id
    global work_percentage, actual_work_days, adjusted_oag_average, adjusted_years, remarks_text
    global claim_type, survivor_type, death_date, last_36_months_continuous, survivor_eligible, survivor_pension
    
    final_avg_value = saved_data.get('oag_average', 0)
    last12_avg_value = saved_data.get('oap_average', 0)
    total_oag_amount = saved_data.get('total_oag_amount', 0)
    total_oap_amount = saved_data.get('total_oap_amount', 0)
    total_months_worked = saved_data.get('total_months', 0)
    total_months_in_period = saved_data.get('total_months_in_period', 0)
    qualifying_years = saved_data.get('qualifying_years', 0)
    less_months = saved_data.get('lesser_months_count', 0)
    oap_eligible = saved_data.get('oap_eligible', 0) == 1
    work_percentage = saved_data.get('work_percentage', 100)
    actual_work_days = saved_data.get('actual_work_days', 0)
    adjusted_oag_average = saved_data.get('adjusted_oag_average', 0)
    adjusted_years = saved_data.get('adjusted_years', 0)
    remarks_text = saved_data.get('remarks', '')
    claim_type = saved_data.get('claim_type', 'self')
    survivor_type = saved_data.get('survivor_type', '')
    death_date = saved_data.get('death_date', '')
    last_36_months_continuous = saved_data.get('last_36_months_continuous', 0) == 1
    survivor_eligible = saved_data.get('survivor_eligible', 0) == 1
    survivor_pension = saved_data.get('survivor_pension', 0)
    
    employment_periods = []
    if saved_data.get('periods_data'):
        try:
            periods_raw = json.loads(saved_data['periods_data'])
            for p in periods_raw:
                period = {
                    'from': datetime.strptime(p['from'], '%Y-%m-%d'),
                    'to': datetime.strptime(p['to'], '%Y-%m-%d'),
                    'employers': [(e[0], e[1], e[2]) for e in p['employers']]
                }
                employment_periods.append(period)
        except:
            pass
    
    temporary_changes = {}
    if saved_data.get('temporary_changes_data'):
        try:
            temp_raw = json.loads(saved_data['temporary_changes_data'])
            for key_str, value in temp_raw.items():
                parts = key_str.split('|')
                if len(parts) == 4:
                    temporary_changes[(parts[0], parts[1], parts[2], parts[3])] = value
        except:
            pass
    
    entry_claimant.delete(0, 'end')
    entry_claimant.insert(0, saved_data.get('claimant_name', '') or "")
    entry_father.delete(0, 'end')
    entry_father.insert(0, saved_data.get('father_name', '') or "")
    entry_eobi.delete(0, 'end')
    entry_eobi.insert(0, saved_data.get('eobi_no', '') or "")
    entry_cnic.delete(0, 'end')
    entry_cnic.insert(0, saved_data.get('cnic_no', '') or "")
    
    update_periods_display()
    update_percentage_display()
    update_claim_display()
    
    if employment_periods:
        calculate()

def show_report_type_dialog():
    if not yearly_data and claim_type != "survivor":
        messagebox.showwarning("Warning", "Please calculate wages first")
        return
    if not entry_claimant.get():
        messagebox.showwarning("Warning", "Please enter claimant name")
        return
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("500x600")
    dialog.title("Select Report Type")
    dialog.grab_set()
    header = ctk.CTkFrame(dialog, fg_color=COLORS['primary'], height=70, corner_radius=10)
    header.pack(fill="x", padx=20, pady=20)
    ctk.CTkLabel(header, text="SELECT REPORT TYPE", font=ctk.CTkFont(size=22, weight="bold"), text_color="white").pack(expand=True)
    
    if claim_type == "survivor":
        ctk.CTkButton(dialog, text="Survivor Pension Report", command=lambda: [dialog.destroy(), get_region("SURVIVOR")],
                      height=50, width=350, fg_color=COLORS['survivor']).pack(pady=10)
    else:
        recommended = "OAP Pension Report" if oap_eligible else "OAG Calculation Report"
        ctk.CTkLabel(dialog, text=f"Recommended: {recommended}", font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COLORS['success'] if oap_eligible else COLORS['warning']).pack(pady=(0, 5))
        ctk.CTkButton(dialog, text=f"OAG Calculation Report{' (Recommended)' if not oap_eligible else ''}", command=lambda: [dialog.destroy(), get_region("OAG")],
                      height=50, width=350, fg_color=COLORS['primary']).pack(pady=10)
        ctk.CTkButton(dialog, text=f"OAP Pension Report{' (Recommended)' if oap_eligible else ''}", command=lambda: [dialog.destroy(), get_region("OAP")],
                      height=50, width=350, fg_color=COLORS['success']).pack(pady=10)
        ctk.CTkButton(dialog, text="Average Wage Report (Wages Sheet)", command=lambda: [dialog.destroy(), get_region("AVG")],
                      height=50, width=350, fg_color=COLORS['warning']).pack(pady=10)
        ctk.CTkButton(dialog, text="Consolidated Report", command=lambda: [dialog.destroy(), get_region("CON")],
                      height=50, width=350, fg_color=COLORS['secondary']).pack(pady=10)
        ctk.CTkButton(dialog, text="Days-Based Report (Percentage)", command=lambda: [dialog.destroy(), get_region("DAYS")],
                      height=50, width=350, fg_color=COLORS['accent']).pack(pady=10)
    
    ctk.CTkButton(dialog, text="Cancel", command=dialog.destroy, height=35, width=120, fg_color=COLORS['error']).pack(pady=10)

def get_region(report_type):
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("450x250")
    dialog.title("Enter Region Name")
    header = ctk.CTkFrame(dialog, fg_color=COLORS['primary'], height=60, corner_radius=10)
    header.pack(fill="x", padx=20, pady=20)
    ctk.CTkLabel(header, text="ENTER REGION NAME", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(expand=True)
    region_entry = ctk.CTkEntry(dialog, width=300, placeholder_text="e.g., Multan")
    region_entry.pack(pady=10)
    region_entry.focus()
    def confirm():
        region_name = region_entry.get().strip()
        if region_name:
            dialog.destroy()
            record_id = save_calculation_record(report_type)
            if record_id:
                if report_type == "OAG":
                    generate_oag_pdf(region_name)
                elif report_type == "OAP":
                    generate_oap_pdf(region_name)
                elif report_type == "AVG":
                    generate_avg_pdf(region_name)
                elif report_type == "CON":
                    generate_consolidated_pdf(region_name)
                elif report_type == "DAYS":
                    generate_days_based_pdf(region_name)
                elif report_type == "SURVIVOR":
                    generate_survivor_pdf(region_name)
            else:
                messagebox.showerror("Error", "Failed to save calculation record. Please check database.")
        else:
            messagebox.showwarning("Warning", "Please enter a region name!")
    region_entry.bind('<Return>', lambda e: confirm())
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=20)
    ctk.CTkButton(btn_frame, text="Generate Report", command=confirm, fg_color=COLORS['primary']).pack(side="left", padx=10)
    ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy, fg_color=COLORS['error']).pack(side="left", padx=10)

def show_thanks_dialog(report_type, record_id=None):
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("500x450")
    dialog.title("Report Generated Successfully!")
    dialog.grab_set()
    header = ctk.CTkFrame(dialog, fg_color=COLORS['success'], height=80, corner_radius=10)
    header.pack(fill="x", padx=20, pady=20)
    header.pack_propagate(False)
    ctk.CTkLabel(header, text="✅ REPORT GENERATED!", font=ctk.CTkFont(size=22, weight="bold"), text_color="white").pack(expand=True)
    try:
        img = ctk.CTkImage(Image.open(resource_path("logo.png")), size=(100,100))
    except:
        img = create_avatar()
    ctk.CTkLabel(dialog, image=img, text="").pack(pady=15)
    
    rec_id = record_id if record_id else current_record_id
    ctk.CTkLabel(dialog, text=f"{report_type} has been generated successfully!\nRecord ID: {rec_id}", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS['success']).pack(pady=10)
    ctk.CTkLabel(dialog, text="Details saved. You can load this record later from Records.", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=5)
    ctk.CTkLabel(dialog, text="🙏 Special thanks to Mr. Nasrullah Shah\nfor invaluable support and guidance!", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS['accent']).pack(pady=10)
    ctk.CTkButton(dialog, text="Close", command=dialog.destroy, height=40, width=150, fg_color=COLORS['primary']).pack(pady=15)

def generate_days_based_pdf(region):
    """Generate days-based report with percentage calculations - CLEANED UP VERSION"""
    global final_avg_value, last12_avg_value, work_percentage, actual_work_days, adjusted_oag_average, adjusted_years
    claimant_name = entry_claimant.get()
    filename = f"{claimant_name.replace(' ','_')}_Days_Based_Report_{region}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=0.5*inch, rightMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=14, alignment=TA_CENTER, spaceAfter=8, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', leading=18)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor('#546e7a'), fontName='Helvetica-Oblique', leading=10)
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=10, alignment=TA_LEFT, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', borderWidth=0.5, borderColor=colors.HexColor('#1a237e'), borderPadding=(2,2,2,2), borderRadius=2)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, spaceAfter=4, fontName='Helvetica', leading=12)
    info_label_style = ParagraphStyle('InfoLabel', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#455a64'), fontName='Helvetica-Bold', leading=12)
    info_value_style = ParagraphStyle('InfoValue', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#263238'), fontName='Helvetica', leftIndent=4, leading=12)
    footer_style = ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER, fontSize=7, textColor=colors.HexColor('#78909c'), leading=9)

    content = []
    
    content.append(Paragraph("EMPLOYEES' OLD-AGE BENEFITS INSTITUTION", title_style))
    content.append(Paragraph("Ministry of Overseas Pakistanis & Human Resource Development", subtitle_style))
    content.append(Paragraph(f"REGIONAL OFFICE - {region.upper()}", ParagraphStyle('RegionTitle', parent=title_style, fontSize=12, leading=16)))
    content.append(Paragraph("DAYS-BASED WAGE REPORT (PERCENTAGE CALCULATION)", ParagraphStyle('ReportTitle', parent=title_style, fontSize=11, textColor=colors.HexColor('#FF6F00'))))
    content.append(Spacer(1,8))
    
    content.append(Paragraph(f"<b>Ref:</b> DAYS/{datetime.now().strftime('%Y%m%d')} | <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,6))
    
    content.append(Paragraph("CLAIMANT DETAILS", heading_style))
    
    all_employers = set()
    for p in employment_periods:
        for e in p['employers']:
            all_employers.add(f"{e[2]}")
    emp_details = ", ".join(all_employers)[:150]
    
    details_data = [
        [Paragraph("<b>Claimant Name:</b>", info_label_style), Paragraph(entry_claimant.get(), info_value_style)],
        [Paragraph("<b>Father's Name:</b>", info_label_style), Paragraph(entry_father.get(), info_value_style)],
        [Paragraph("<b>EOBI No:</b>", info_label_style), Paragraph(entry_eobi.get(), info_value_style)],
        [Paragraph("<b>CNIC No:</b>", info_label_style), Paragraph(entry_cnic.get(), info_value_style)],
        [Paragraph("<b>Employer(s):</b>", info_label_style), Paragraph(emp_details, info_value_style)],
        [Paragraph("<b>Record ID:</b>", info_label_style), Paragraph(str(current_record_id), info_value_style)],
    ]
    
    details_table = Table(details_data, colWidths=[2.0*inch, 4.5*inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#e3f2fd')),
        ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#bdbdbd')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),4),
    ]))
    content.append(details_table)
    content.append(Spacer(1,10))
    
    content.append(Paragraph("DAYS-BASED CALCULATION SUMMARY", heading_style))
    content.append(Spacer(1,6))
    
    # CLEANED UP SUMMARY - Removed Total Period Days, Work Percentage, and (Original: ...) text
    summary_data = [
        [Paragraph("<b>DESCRIPTION</b>", ParagraphStyle('Header', parent=info_label_style, textColor=colors.white, fontSize=10)),
         Paragraph("<b>VALUE</b>", ParagraphStyle('Header', parent=info_label_style, textColor=colors.white, fontSize=10))],
        [Paragraph("Total Number of Days Actually Worked", info_label_style),
         Paragraph(f"<b>{actual_work_days} Days</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold'))],
        [Paragraph("Total Number of Years on the Basis of Days", info_label_style),
         Paragraph(f"<b>{adjusted_years:.2f} Years</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold'))],
        [Paragraph("Average Wage for OAG on the Basis of Days", info_label_style),
         Paragraph(f"<b>PKR {adjusted_oag_average:,.2f}</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold'))],
        [Paragraph("Average Wage of Last Twelve Months", info_label_style),
         Paragraph(f"<b>PKR {round(last12_avg_value,2):,.2f}</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold'))],
    ]
    
    summary_table = Table(summary_data, colWidths=[3.0*inch, 3.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a237e')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),9),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#9fa8da')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),8),
        ('BACKGROUND',(0,1),(-1,-1),colors.HexColor('#f5f5f5')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#ffffff'), colors.HexColor('#f5f5f5')]),
    ]))
    content.append(summary_table)
    content.append(Spacer(1,15))
    
    if remarks_text:
        content.append(Paragraph("REMARKS", heading_style))
        content.append(Paragraph(remarks_text, normal_style))
        content.append(Spacer(1,10))
    
    content.append(Spacer(1,10))
    content.append(Paragraph("CERTIFICATION", heading_style))
    content.append(Paragraph(f"This is to certify that the above-mentioned days-based wage calculation is correct.", normal_style))
    content.append(Spacer(1,10))
    
    cert_data = [
        [Paragraph("<b>Prepared By:</b>", info_label_style), Paragraph("_______________", info_value_style),
         Paragraph("<b>Verified By:</b>", info_label_style), Paragraph("_______________", info_value_style)],
        [Paragraph("<b>Date:</b>", info_label_style), Paragraph(datetime.now().strftime('%d-%m-%Y'), info_value_style),
         Paragraph("<b>Date:</b>", info_label_style), Paragraph("_______________", info_value_style)],
    ]
    
    cert_table = Table(cert_data, colWidths=[1.0*inch, 2.0*inch, 1.0*inch, 2.5*inch])
    cert_table.setStyle(TableStyle([
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),4),
    ]))
    content.append(cert_table)
    content.append(Spacer(1,15))
    
    content.append(Paragraph(f"<b>EOBI-Regional office {region}</b> | Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}<br/><font size='6'>Zee Shah | {APP_VERSION} | Special thanks to Mr. Nasrullah Shah</font>", footer_style))
    
    doc.build(content)
    show_thanks_dialog("Days-Based Report", current_record_id)
    if os.path.exists(filename): os.startfile(filename)

def generate_survivor_pdf(region):
    """Generate survivor pension report"""
    global survivor_eligible, survivor_pension, last_36_months_continuous, total_months_worked, survivor_service_years
    claimant_name = entry_claimant.get()
    filename = f"{claimant_name.replace(' ','_')}_Survivor_Pension_{region}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=0.5*inch, rightMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=14, alignment=TA_CENTER, spaceAfter=8, textColor=colors.HexColor('#6A1B9A'), fontName='Helvetica-Bold', leading=18)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor('#546e7a'), fontName='Helvetica-Oblique', leading=10)
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=10, alignment=TA_LEFT, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor('#6A1B9A'), fontName='Helvetica-Bold', borderWidth=0.5, borderColor=colors.HexColor('#6A1B9A'), borderPadding=(2,2,2,2), borderRadius=2)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, spaceAfter=4, fontName='Helvetica', leading=12)
    info_label_style = ParagraphStyle('InfoLabel', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#455a64'), fontName='Helvetica-Bold', leading=12)
    info_value_style = ParagraphStyle('InfoValue', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#263238'), fontName='Helvetica', leftIndent=4, leading=12)
    footer_style = ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER, fontSize=7, textColor=colors.HexColor('#78909c'), leading=9)

    content = []
    
    content.append(Paragraph("EMPLOYEES' OLD-AGE BENEFITS INSTITUTION", title_style))
    content.append(Paragraph("Ministry of Overseas Pakistanis & Human Resource Development", subtitle_style))
    content.append(Paragraph(f"REGIONAL OFFICE - {region.upper()}", ParagraphStyle('RegionTitle', parent=title_style, fontSize=12, leading=16)))
    content.append(Paragraph("SURVIVOR PENSION REPORT", ParagraphStyle('ReportTitle', parent=title_style, fontSize=13, textColor=colors.HexColor('#6A1B9A'))))
    content.append(Spacer(1,8))
    
    content.append(Paragraph(f"<b>Ref:</b> SUR/{datetime.now().strftime('%Y%m%d')} | <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,6))
    
    content.append(Paragraph("CLAIMANT & DECEASED DETAILS", heading_style))
    
    all_employers = set()
    for p in employment_periods:
        for e in p['employers']:
            all_employers.add(f"{e[2]}")
    emp_details = ", ".join(all_employers)[:150]
    
    details_data = [
        [Paragraph("<b>Claimant (Survivor) Name:</b>", info_label_style), Paragraph(entry_claimant.get(), info_value_style)],
        [Paragraph("<b>Father's Name:</b>", info_label_style), Paragraph(entry_father.get(), info_value_style)],
        [Paragraph("<b>EOBI No:</b>", info_label_style), Paragraph(entry_eobi.get(), info_value_style)],
        [Paragraph("<b>CNIC No:</b>", info_label_style), Paragraph(entry_cnic.get(), info_value_style)],
        [Paragraph("<b>Employer(s):</b>", info_label_style), Paragraph(emp_details, info_value_style)],
        [Paragraph("<b>Death Date:</b>", info_label_style), Paragraph(death_date, info_value_style)],
        [Paragraph("<b>Death Circumstances:</b>", info_label_style), Paragraph(survivor_type.replace('_', ' ').title(), info_value_style)],
        [Paragraph("<b>Record ID:</b>", info_label_style), Paragraph(str(current_record_id), info_value_style)],
    ]
    
    details_table = Table(details_data, colWidths=[2.0*inch, 4.5*inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#f3e5f5')),
        ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#ce93d8')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),4),
    ]))
    content.append(details_table)
    content.append(Spacer(1,10))
    
    content.append(Paragraph("SURVIVOR ELIGIBILITY ASSESSMENT", heading_style))
    
    if survivor_eligible:
        content.append(Paragraph(f"<font size='10' color='green'><b>✅ SURVIVOR IS ELIGIBLE FOR PENSION</b></font>", normal_style))
        content.append(Paragraph(f"<b>Survivor Pension: PKR {survivor_pension:,.2f} per month (Minimum Pension)</b>", normal_style))
    else:
        content.append(Paragraph(f"<font size='10' color='red'><b>❌ SURVIVOR IS NOT ELIGIBLE FOR PENSION</b></font>", normal_style))
    
    content.append(Spacer(1,6))
    
    # Eligibility criteria details
    content.append(Paragraph("ELIGIBILITY CRITERIA DETAILS", heading_style))
    
    criteria_data = [
        [Paragraph("<b>Criteria</b>", info_label_style), Paragraph("<b>Status</b>", info_label_style)],
        [Paragraph(f"Paid Service: {survivor_service_years:.2f} years", info_value_style),
         Paragraph("", info_value_style)],
        [Paragraph(f"{SURVIVOR_CONTINUOUS_MONTHS} Continuous Paid Months: {'YES' if last_36_months_continuous else 'NO'}", info_value_style),
         Paragraph("", info_value_style)],
    ]
    
    if survivor_type == "died_during_service":
        criteria_data.append([Paragraph(f"Requirement: {SURVIVOR_CONTINUOUS_MONTHS} continuous paid months OR {SURVIVOR_REQUIRED_YEARS_BEFORE_60} paid service years", info_label_style),
                             Paragraph("MET" if survivor_eligible else "NOT MET", info_value_style)])
    elif survivor_type == "died_not_in_service":
        criteria_data.append([Paragraph(f"Requirement: {SURVIVOR_REQUIRED_YEARS_BEFORE_60} paid service years", info_label_style),
                             Paragraph("MET" if survivor_eligible else "NOT MET", info_value_style)])
    elif survivor_type == "died_after_60":
        criteria_data.append([Paragraph(f"Requirement: {SURVIVOR_REQUIRED_YEARS_AFTER_60} paid service years", info_label_style),
                             Paragraph("MET" if survivor_eligible else "NOT MET", info_value_style)])
    
    criteria_table = Table(criteria_data, colWidths=[3.5*inch, 3.0*inch])
    criteria_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#6A1B9A')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#ce93d8')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),6),
    ]))
    content.append(criteria_table)
    content.append(Spacer(1,10))
    
    if remarks_text:
        content.append(Paragraph("REMARKS", heading_style))
        content.append(Paragraph(remarks_text, normal_style))
        content.append(Spacer(1,10))
    
    content.append(Spacer(1,10))
    content.append(Paragraph("CERTIFICATION", heading_style))
    content.append(Paragraph(f"This is to certify that the survivor pension eligibility has been assessed based on the contribution history and death circumstances.", normal_style))
    content.append(Spacer(1,10))
    
    cert_data = [
        [Paragraph("<b>Prepared By:</b>", info_label_style), Paragraph("_______________", info_value_style),
         Paragraph("<b>Verified By:</b>", info_label_style), Paragraph("_______________", info_value_style)],
        [Paragraph("<b>Date:</b>", info_label_style), Paragraph(datetime.now().strftime('%d-%m-%Y'), info_value_style),
         Paragraph("<b>Date:</b>", info_label_style), Paragraph("_______________", info_value_style)],
    ]
    
    cert_table = Table(cert_data, colWidths=[1.0*inch, 2.0*inch, 1.0*inch, 2.5*inch])
    cert_table.setStyle(TableStyle([
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),4),
    ]))
    content.append(cert_table)
    content.append(Spacer(1,15))
    
    content.append(Paragraph(f"<b>EOBI-Regional office {region}</b> | Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}<br/><font size='6'>Zee Shah | {APP_VERSION} | Special thanks to Mr. Nasrullah Shah</font>", footer_style))
    
    doc.build(content)
    show_thanks_dialog("Survivor Pension Report", current_record_id)
    if os.path.exists(filename): os.startfile(filename)

# Keep all other PDF functions (generate_oag_pdf, generate_oap_pdf, generate_avg_pdf, generate_consolidated_pdf) as they were
# They remain unchanged from previous code

def generate_oag_pdf(region):
    global final_avg_value, qualifying_years
    claimant_name = entry_claimant.get()
    filename = f"{claimant_name.replace(' ','_')}_OAG_Calculation_{region}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=0.3*inch, rightMargin=0.3*inch, topMargin=0.3*inch, bottomMargin=0.3*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=11, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', leading=13)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=6, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#546e7a'), fontName='Helvetica-Oblique', leading=8)
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=8, alignment=TA_LEFT, spaceBefore=4, spaceAfter=2, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', borderWidth=0.3, borderColor=colors.HexColor('#1a237e'), borderPadding=(1,1,1,1), borderRadius=1)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, spaceAfter=1, fontName='Helvetica', leading=8)
    info_label_style = ParagraphStyle('InfoLabel', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, textColor=colors.HexColor('#455a64'), fontName='Helvetica-Bold', leading=8)
    info_value_style = ParagraphStyle('InfoValue', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, textColor=colors.HexColor('#263238'), fontName='Helvetica', leftIndent=2, leading=8)
    footer_style = ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER, fontSize=5, textColor=colors.HexColor('#78909c'), leading=6)

    zero_month_dates = {d for _, _, _, d in zero_wage_months if combined_wages.get(d, 0) <= 0}
    total_zero_days = sum(get_days_in_month(d.year, d.month) for d in zero_month_dates)
    total_period_days = sum((p['to'] - p['from']).days + 1 for p in employment_periods)
    active_days = total_period_days - total_zero_days

    content = []
    content.append(Paragraph("EMPLOYEES' OLD-AGE BENEFITS INSTITUTION", title_style))
    content.append(Paragraph("Ministry of Overseas Pakistanis & Human Resource Development", subtitle_style))
    content.append(Paragraph(f"REGIONAL OFFICE - {region.upper()}", title_style))
    content.append(Paragraph("AVERAGE WAGES FOR OLD-AGE GRANT (OAG)", title_style))
    content.append(Spacer(1,4))
    content.append(Paragraph(f"<b>Ref:</b> OAG/{datetime.now().strftime('%Y%m%d')} | <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,3))

    all_employers = set()
    for p in employment_periods:
        for e in p['employers']:
            all_employers.add(f"{e[2]} ({e[0]}-{e[1]})")
    emp_details = ", ".join(all_employers)[:120]
    
    content.append(Paragraph("EMPLOYER & CLAIMANT DETAILS", heading_style))
    combined_data = [
        [Paragraph("<b>Employer(s):</b>", info_label_style), Paragraph(emp_details, info_value_style), Paragraph("<b>Claimant:</b>", info_label_style), Paragraph(entry_claimant.get(), info_value_style)],
        [Paragraph("<b>Father:</b>", info_label_style), Paragraph(entry_father.get(), info_value_style), Paragraph("<b>EOBI/CNIC:</b>", info_label_style), Paragraph(f"{entry_eobi.get()} / {entry_cnic.get()}", info_value_style)],
        [Paragraph("<b>Total Period Days:</b>", info_label_style), Paragraph(f"{total_period_days} days", info_value_style), Paragraph("<b>Record ID:</b>", info_label_style), Paragraph(f"{current_record_id}", info_value_style)]
    ]
    combined_table = Table(combined_data, colWidths=[0.7*inch, 2.1*inch, 0.7*inch, 2.2*inch])
    combined_table.setStyle(TableStyle([('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e3f2fd')), ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f3e5f5')), ('GRID', (0,0), (-1,-1), 0.2, colors.HexColor('#bdbdbd')), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 1)]))
    content.append(combined_table)
    content.append(Spacer(1,4))

    content.append(Paragraph("INSURABLE EMPLOYMENT PERIOD ANALYSIS", heading_style))
    content.append(Paragraph(f"<b>Overall insurable employment:</b> {get_month_start_date(min(p['from'] for p in employment_periods)).strftime('%d/%m/%Y')} to {get_month_end_date(max(p['to'] for p in employment_periods)).strftime('%d/%m/%Y')}", normal_style))
    content.append(Paragraph(f"<b>Total Period Days:</b> {total_period_days} | <b>Days Contribution Paid:</b> {active_days}", normal_style))
    content.append(Spacer(1,2))
    
    table_data = [["Yr", "Period", "Avg Wage (PKR)", "Mths", "Days", "Status"]]
    for year_num, start, end, avg, months, qualifies, status, year_days in yearly_data:
        period_start_display = get_month_start_date(start)
        period_end_display = get_month_end_date(end)
        table_data.append([str(year_num), f"{period_start_display.strftime('%d/%m/%Y')}-{period_end_display.strftime('%d/%m/%Y')}", f"Rs. {round(avg,2):,}", str(months), str(year_days), "QUALIFIES" if qualifies else "NOT QUALIFY"])
    table_data.append(["","","","","",""])
    table_data.append([f"TOTAL QUALIFYING YEARS: {qualifying_years}","","","","",""])
    
    table = Table(table_data, colWidths=[0.4*inch,1.5*inch,1.2*inch,0.4*inch,0.5*inch,1.8*inch])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a237e')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ALIGN',(0,0),(-1,-1),'CENTER'),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,0),5),('BOTTOMPADDING',(0,0),(-1,0),1),('TOPPADDING',(0,0),(-1,0),1),('BACKGROUND',(0,1),(-1,-3),colors.HexColor('#f5f5f5')),('BACKGROUND',(0,-2),(-1,-2),colors.HexColor('#e8eaf6')),('GRID',(0,0),(-1,-3),0.2,colors.HexColor('#9fa8da')),('FONTNAME',(0,1),(-1,-1),'Helvetica'),('FONTSIZE',(0,1),(-1,-1),5),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('FONTNAME',(0,-2),(0,-2),'Helvetica-Bold'),('PADDING',(0,0),(-1,-1),1)]))
    content.append(table)
    content.append(Spacer(1,4))
    
    content.append(Paragraph("AVERAGE MONTHLY WAGES FOR OAG", heading_style))
    result_table = Table([[Paragraph(f"<font size='10'><b>PKR {final_avg_value:,.2f}</b></font><br/><font size='6'>(Average of {qualifying_years} qualifying year averages)</font>", ParagraphStyle('Result1', alignment=TA_CENTER, leading=12))]], colWidths=[5.7*inch])
    result_table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#e8f5e9')),('BOX',(0,0),(-1,-1),1,colors.HexColor('#4caf50')),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),8)]))
    content.append(result_table)
    
    if remarks_text:
        content.append(Spacer(1,3))
        content.append(Paragraph("REMARKS", heading_style))
        content.append(Paragraph(remarks_text, normal_style))
    
    content.append(Spacer(1,4))
    content.append(Paragraph("CERTIFICATION & SIGNATURE", heading_style))
    content.append(Paragraph(f"<b>Signature:</b> _______________ <b>Name:</b> _______________ <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,3))
    content.append(Paragraph(f"<b>EOBI-Regional office {region}</b> | Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}<br/><font size='4'>Zee Shah | {APP_VERSION} | Special thanks to Mr. Nasrullah Shah</font>", footer_style))
    doc.build(content)
    show_thanks_dialog("OAG Calculation Report", current_record_id)
    if os.path.exists(filename): os.startfile(filename)

def generate_oap_pdf(region):
    global last12_avg_value, less_months, lesser_rate_months, oap_eligible, oap_qualifying_period_years, total_oap_amount
    global oap_formula_years, lesser_rate_years, zero_wage_years
    claimant_name = entry_claimant.get()
    filename = f"{claimant_name.replace(' ','_')}_OAP_Pension_{region}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=0.3*inch, rightMargin=0.3*inch, topMargin=0.3*inch, bottomMargin=0.3*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=11, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', leading=13)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=6, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#546e7a'), fontName='Helvetica-Oblique', leading=8)
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=8, alignment=TA_LEFT, spaceBefore=4, spaceAfter=2, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', borderWidth=0.3, borderColor=colors.HexColor('#1a237e'), borderPadding=(1,1,1,1), borderRadius=1)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, spaceAfter=1, fontName='Helvetica', leading=8)
    info_label_style = ParagraphStyle('InfoLabel', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, textColor=colors.HexColor('#455a64'), fontName='Helvetica-Bold', leading=8)
    info_value_style = ParagraphStyle('InfoValue', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, textColor=colors.HexColor('#263238'), fontName='Helvetica', leftIndent=2, leading=8)
    footer_style = ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER, fontSize=5, textColor=colors.HexColor('#78909c'), leading=6)

    content = []
    content.append(Paragraph("EMPLOYEES' OLD-AGE BENEFITS INSTITUTION", title_style))
    content.append(Paragraph("Ministry of Overseas Pakistanis & Human Resource Development", subtitle_style))
    content.append(Paragraph(f"REGIONAL OFFICE - {region.upper()}", title_style))
    content.append(Paragraph("PENSION CALCULATION REPORT (OAP)", title_style))
    content.append(Spacer(1,4))
    content.append(Paragraph(f"<b>Ref:</b> OAP/{datetime.now().strftime('%Y%m%d')} | <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,3))
    
    all_employers = set()
    for p in employment_periods:
        for e in p['employers']:
            all_employers.add(f"{e[2]} ({e[0]}-{e[1]})")
    emp_details = ", ".join(all_employers)[:120]
    
    total_period_days = sum((p['to'] - p['from']).days + 1 for p in employment_periods)
    
    content.append(Paragraph("EMPLOYER & CLAIMANT DETAILS", heading_style))
    combined_data = [
        [Paragraph("<b>Employer(s):</b>", info_label_style), Paragraph(emp_details, info_value_style), Paragraph("<b>Claimant:</b>", info_label_style), Paragraph(entry_claimant.get(), info_value_style)],
        [Paragraph("<b>Father:</b>", info_label_style), Paragraph(entry_father.get(), info_value_style), Paragraph("<b>EOBI/CNIC:</b>", info_label_style), Paragraph(f"{entry_eobi.get()} / {entry_cnic.get()}", info_value_style)],
        [Paragraph("<b>Total Period Days:</b>", info_label_style), Paragraph(f"{total_period_days} days", info_value_style), Paragraph("<b>Record ID:</b>", info_label_style), Paragraph(f"{current_record_id}", info_value_style)]
    ]
    combined_table = Table(combined_data, colWidths=[0.7*inch,2.1*inch,0.7*inch,2.2*inch])
    combined_table.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#e3f2fd')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#f3e5f5')),('GRID',(0,0),(-1,-1),0.2,colors.HexColor('#bdbdbd')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),1)]))
    content.append(combined_table)
    content.append(Spacer(1,4))
    
    content.append(Paragraph("OAP ELIGIBILITY STATUS", heading_style))
    if oap_eligible:
        content.append(Paragraph(f"<font size='9' color='green'><b>ELIGIBLE FOR OAP PENSION</b></font><br/><font size='7'>Service Period: {oap_qualifying_period_years:.2f} years ({OAP_REQUIRED_YEARS} years required)</font>", normal_style))
    else:
        content.append(Paragraph(f"<font size='9' color='red'><b>NOT ELIGIBLE FOR OAP PENSION</b></font><br/><font size='7'>Service Period: {oap_qualifying_period_years:.2f} years (less than {OAP_REQUIRED_YEARS} years required)</font>", normal_style))
    content.append(Spacer(1,4))
    
    content.append(Paragraph("LAST TWELVE MONTHS WAGES FOR OAP PENSION", heading_style))
    
    active_wages_sorted = sorted([(d, w) for d, w in combined_wages.items() if w > 0], key=lambda x: x[0])
    last12 = active_wages_sorted[-12:] if len(active_wages_sorted) >= 12 else active_wages_sorted
    
    last12_table_data = [["Month", "Wage (PKR)", "Min Wage", "Status"]]
    for d, w in last12:
        min_w = get_min(d.strftime("%Y-%m"))
        if w == 0:
            status = "Zero"
        elif w < min_w:
            status = "Lesser"
        else:
            status = "Active"
        last12_table_data.append([d.strftime('%b %Y'), f"Rs. {w:,.2f}", f"Rs. {min_w:,}", status])
    
    last12_table = Table(last12_table_data, colWidths=[0.8*inch, 1.2*inch, 1.2*inch, 0.8*inch])
    last12_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1565c0')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),5),
        ('FONTSIZE',(0,1),(-1,-1),5),
        ('GRID',(0,0),(-1,-1),0.2,colors.HexColor('#90caf9')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),1),
    ]))
    content.append(last12_table)
    content.append(Spacer(1,3))
    
    content.append(Paragraph("LAST 12 MONTHS AVERAGE WAGE", heading_style))
    avg_table = Table([[Paragraph(f"<font size='10'><b>PKR {round(last12_avg_value,2):,}</b></font><br/><font size='6'>(Average of last 12 months wages)</font>", ParagraphStyle('ResultAvg', alignment=TA_CENTER, leading=12))]], colWidths=[5.7*inch])
    avg_table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#e3f2fd')),('BOX',(0,0),(-1,-1),1,colors.HexColor('#1565c0')),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),8)]))
    content.append(avg_table)
    content.append(Spacer(1,4))
    
    if lesser_rate_months:
        content.append(Paragraph("🔻 LESSER RATE CONTRIBUTION MONTHS", heading_style))
        lesser_rate_data = [["No.", "Month", "Employer", "Paid Wage (PKR)", "Min Wage (PKR)", "Shortfall (PKR)"]]
        
        unique_lesser = []
        seen = set()
        for name, main, sub, d, w, min_w in lesser_rate_months:
            key = (d.strftime('%b %Y'), name[:20])
            if key not in seen:
                seen.add(key)
                unique_lesser.append((name, d, w, min_w))
        
        for i, (name, d, w, min_w) in enumerate(sorted(unique_lesser, key=lambda x: x[1]), 1):
            shortfall = min_w - w
            lesser_rate_data.append([str(i), d.strftime('%b %Y'), name[:20], f"Rs. {w:,.2f}", f"Rs. {min_w:,.2f}", f"Rs. {shortfall:,.2f}"])
        
        lesser_rate_data.append(["", "", "", "", "", ""])
        lesser_rate_data.append([f"TOTAL LESSER RATE MONTHS: {less_months}", "", "", "", "", ""])
        
        lesser_table = Table(lesser_rate_data, colWidths=[0.3*inch, 0.8*inch, 1.2*inch, 1.0*inch, 1.0*inch, 1.0*inch])
        lesser_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#ff6f00')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),5),
            ('FONTSIZE',(0,1),(-1,-1),5),
            ('GRID',(0,0),(-1,-1),0.2,colors.HexColor('#ffcc02')),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('PADDING',(0,0),(-1,-1),1),
            ('BACKGROUND',(0,-2),(-1,-2),colors.HexColor('#ffe0b2')),
            ('FONTNAME',(0,-2),(-1,-2),'Helvetica-Bold'),
            ('FONTWEIGHT',(0,-2),(-1,-2),'BOLD'),
        ]))
        content.append(lesser_table)
        content.append(Spacer(1,4))
    
    if oap_eligible:
        content.append(Paragraph("OAP PENSION CALCULATION", heading_style))
        raw_oap = (last12_avg_value * oap_formula_years) / 50
        content.append(Paragraph(f"<b>Formula:</b> Last 12 Month Average x (Service Years - Lesser Rate Years - Zero Wage Years) / 50", normal_style))
        content.append(Paragraph(f"Formula Years: {oap_qualifying_period_years:.2f} - {lesser_rate_years:.2f} - {zero_wage_years:.2f} = {oap_formula_years:.2f}", normal_style))
        content.append(Paragraph(f"({round(last12_avg_value,2)} x {oap_formula_years:.2f}) / 50 = {raw_oap:.2f}", normal_style))
        content.append(Paragraph(f"<b>Calculated Pension: PKR {raw_oap:.2f}</b>", normal_style))
        content.append(Paragraph(f"<b>Minimum Pension: PKR {MIN_PENSION:,.0f}</b>", normal_style))
        content.append(Paragraph(f"<font size='10' color='green'><b>Final OAP Pension = PKR {total_oap_amount:,.2f} per month</b></font>", normal_style))
        content.append(Paragraph(f"<font size='6'>(Eligibility based on service period >= {OAP_REQUIRED_YEARS} years; lesser and zero wage years reduce formula years.)</font>", normal_style))
    
    if remarks_text:
        content.append(Spacer(1,3))
        content.append(Paragraph("REMARKS", heading_style))
        content.append(Paragraph(remarks_text, normal_style))
    
    content.append(Spacer(1,4))
    content.append(Paragraph("CERTIFICATION & SIGNATURE", heading_style))
    content.append(Paragraph(f"<b>Signature:</b> _______________ <b>Name:</b> _______________ <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,4))
    content.append(Paragraph(f"<b>EOBI-Regional office {region}</b> | Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}<br/><font size='4'>Zee Shah | {APP_VERSION} | Special thanks to Mr. Nasrullah Shah</font>", footer_style))
    doc.build(content)
    show_thanks_dialog("OAP Pension Report", current_record_id)
    if os.path.exists(filename): os.startfile(filename)

def generate_avg_pdf(region):
    global final_avg_value, last12_avg_value, total_oag_amount, total_oap_amount, oap_eligible, oap_qualifying_period_years, total_months_in_period
    global less_months, lesser_rate_months
    claimant_name = entry_claimant.get()
    claimant = entry_claimant.get().strip()
    filename = f"{claimant_name.replace(' ','_')}_Average_Wage_Report_{region}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=0.3*inch, rightMargin=0.3*inch, topMargin=0.3*inch, bottomMargin=0.3*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=11, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', leading=13)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=6, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#546e7a'), fontName='Helvetica-Oblique', leading=8)
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=8, alignment=TA_LEFT, spaceBefore=4, spaceAfter=2, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', borderWidth=0.3, borderColor=colors.HexColor('#1a237e'), borderPadding=(1,1,1,1), borderRadius=1)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, spaceAfter=1, fontName='Helvetica', leading=8)
    info_label_style = ParagraphStyle('InfoLabel', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, textColor=colors.HexColor('#455a64'), fontName='Helvetica-Bold', leading=8)
    info_value_style = ParagraphStyle('InfoValue', parent=styles['Normal'], fontSize=6, alignment=TA_LEFT, textColor=colors.HexColor('#263238'), fontName='Helvetica', leftIndent=2, leading=8)
    footer_style = ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER, fontSize=5, textColor=colors.HexColor('#78909c'), leading=6)

    zero_month_dates = {d for _, _, _, d in zero_wage_months if combined_wages.get(d, 0) <= 0}
    total_zero_days = sum(get_days_in_month(d.year, d.month) for d in zero_month_dates)
    total_period_days = sum((p['to'] - p['from']).days + 1 for p in employment_periods)
    active_days = total_period_days - total_zero_days
    zero_wage_months_count = len(zero_month_dates)

    content = []
    content.append(Paragraph("EMPLOYEES' OLD-AGE BENEFITS INSTITUTION", title_style))
    content.append(Paragraph("Ministry of Overseas Pakistanis & Human Resource Development", subtitle_style))
    content.append(Paragraph(f"REGIONAL OFFICE - {region.upper()}", title_style))
    content.append(Paragraph("AVERAGE WAGE REPORT (WAGES SHEET)", title_style))
    content.append(Spacer(1,4))
    content.append(Paragraph(f"<b>Ref:</b> AVG/{datetime.now().strftime('%Y%m%d')} | <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,3))

    all_employers = set()
    for p in employment_periods:
        for e in p['employers']:
            all_employers.add(f"{e[2]} ({e[0]}-{e[1]})")
    emp_details = ", ".join(all_employers)[:120]
    
    content.append(Paragraph("EMPLOYER & CLAIMANT DETAILS", heading_style))
    combined_data = [
        [Paragraph("<b>Employer(s):</b>", info_label_style), Paragraph(emp_details, info_value_style), Paragraph("<b>Claimant:</b>", info_label_style), Paragraph(entry_claimant.get(), info_value_style)],
        [Paragraph("<b>Father:</b>", info_label_style), Paragraph(entry_father.get(), info_value_style), Paragraph("<b>EOBI/CNIC:</b>", info_label_style), Paragraph(f"{entry_eobi.get()} / {entry_cnic.get()}", info_value_style)],
        [Paragraph("<b>Total Period Days:</b>", info_label_style), Paragraph(f"{total_period_days} days", info_value_style), Paragraph("<b>Record ID:</b>", info_label_style), Paragraph(f"{current_record_id}", info_value_style)]
    ]
    combined_table = Table(combined_data, colWidths=[0.7*inch, 2.1*inch, 0.7*inch, 2.2*inch])
    combined_table.setStyle(TableStyle([('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e3f2fd')), ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f3e5f5')), ('GRID', (0,0), (-1,-1), 0.2, colors.HexColor('#bdbdbd')), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 1)]))
    content.append(combined_table)
    content.append(Spacer(1,4))

    if remarks_text:
        content.append(Paragraph("REMARKS", heading_style))
        content.append(Paragraph(remarks_text, normal_style))
        content.append(Spacer(1,3))
    
    content.append(Paragraph("CERTIFICATION & SIGNATURE", heading_style))
    content.append(Paragraph(f"<b>Signature:</b> _______________ <b>Name:</b> _______________ <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,3))
    content.append(Paragraph(f"<b>EOBI-Regional office {region}</b> | Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}<br/><font size='4'>Zee Shah | {APP_VERSION} | Special thanks to Mr. Nasrullah Shah</font>", footer_style))
    doc.build(content)
    show_thanks_dialog("Average Wage Report", current_record_id)
    if os.path.exists(filename): os.startfile(filename)

def generate_consolidated_pdf(region):
    """Generate consolidated report"""
    global final_avg_value, last12_avg_value, less_months, lesser_rate_months, oap_eligible, oap_qualifying_period_years, total_oap_amount
    global oap_formula_years, zero_wage_years, lesser_rate_years
    claimant_name = entry_claimant.get()
    filename = f"{claimant_name.replace(' ','_')}_Consolidated_Report_{region}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=0.5*inch, rightMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=14, alignment=TA_CENTER, spaceAfter=8, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', leading=18)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor('#546e7a'), fontName='Helvetica-Oblique', leading=10)
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=10, alignment=TA_LEFT, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor('#1a237e'), fontName='Helvetica-Bold', borderWidth=0.5, borderColor=colors.HexColor('#1a237e'), borderPadding=(2,2,2,2), borderRadius=2)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, spaceAfter=4, fontName='Helvetica', leading=12)
    info_label_style = ParagraphStyle('InfoLabel', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#455a64'), fontName='Helvetica-Bold', leading=12)
    info_value_style = ParagraphStyle('InfoValue', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#263238'), fontName='Helvetica', leftIndent=4, leading=12)
    footer_style = ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER, fontSize=7, textColor=colors.HexColor('#78909c'), leading=9)

    content = []
    
    content.append(Paragraph("EMPLOYEES' OLD-AGE BENEFITS INSTITUTION", title_style))
    content.append(Paragraph("Ministry of Overseas Pakistanis & Human Resource Development", subtitle_style))
    content.append(Paragraph(f"REGIONAL OFFICE - {region.upper()}", ParagraphStyle('RegionTitle', parent=title_style, fontSize=12, leading=16)))
    content.append(Paragraph("CONSOLIDATED WAGE REPORT", ParagraphStyle('ReportTitle', parent=title_style, fontSize=13, textColor=colors.HexColor('#00897B'))))
    content.append(Spacer(1,8))
    
    content.append(Paragraph(f"<b>Ref:</b> CON/{datetime.now().strftime('%Y%m%d')} | <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}", normal_style))
    content.append(Spacer(1,6))
    
    content.append(Paragraph("CLAIMANT DETAILS", heading_style))
    
    all_employers = set()
    for p in employment_periods:
        for e in p['employers']:
            all_employers.add(f"{e[2]}")
    emp_details = ", ".join(all_employers)[:150]
    
    details_data = [
        [Paragraph("<b>Claimant Name:</b>", info_label_style), Paragraph(entry_claimant.get(), info_value_style)],
        [Paragraph("<b>Father's Name:</b>", info_label_style), Paragraph(entry_father.get(), info_value_style)],
        [Paragraph("<b>EOBI No:</b>", info_label_style), Paragraph(entry_eobi.get(), info_value_style)],
        [Paragraph("<b>CNIC No:</b>", info_label_style), Paragraph(entry_cnic.get(), info_value_style)],
        [Paragraph("<b>Employer(s):</b>", info_label_style), Paragraph(emp_details, info_value_style)],
        [Paragraph("<b>Record ID:</b>", info_label_style), Paragraph(str(current_record_id), info_value_style)],
    ]
    
    details_table = Table(details_data, colWidths=[2.0*inch, 4.5*inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#e3f2fd')),
        ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#bdbdbd')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),4),
    ]))
    content.append(details_table)
    content.append(Spacer(1,10))
    
    content.append(Paragraph("CONSOLIDATED WAGE SUMMARY", heading_style))
    content.append(Spacer(1,6))
    
    summary_data = [
        [Paragraph("<b>DESCRIPTION</b>", ParagraphStyle('Header', parent=info_label_style, textColor=colors.white, fontSize=10)),
         Paragraph("<b>VALUE</b>", ParagraphStyle('Header', parent=info_label_style, textColor=colors.white, fontSize=10))],
        [Paragraph("Average Wage for OAG", info_label_style),
         Paragraph(f"<b>PKR {final_avg_value:,.2f}</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold'))],
        [Paragraph("Average Wage of Last Twelve Months", info_label_style),
         Paragraph(f"<b>PKR {round(last12_avg_value,2):,.2f}</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold'))],
        [Paragraph("Service Period for OAP Eligibility", info_label_style),
         Paragraph(f"<b>{oap_qualifying_period_years:.2f} Years</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold'))],
        [Paragraph("Formula Years after Lesser/Zero Wage Deduction", info_label_style),
         Paragraph(f"<b>{oap_formula_years:.2f} Years</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold'))],
        [Paragraph("Number of Months at Which Contribution is Paid at Lesser Rates", info_label_style),
         Paragraph(f"<b>{less_months} Months</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#FF6F00') if less_months > 0 else colors.HexColor('#2E7D32')))],
        [Paragraph("OAP Eligibility", info_label_style),
         Paragraph(f"<b>{'ELIGIBLE ✅' if oap_eligible else 'NOT ELIGIBLE ❌'}</b>", ParagraphStyle('Value', parent=info_value_style, fontSize=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#2E7D32') if oap_eligible else colors.HexColor('#C62828')))],
    ]
    
    summary_table = Table(summary_data, colWidths=[3.5*inch, 3.0*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a237e')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),9),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#9fa8da')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),8),
        ('BACKGROUND',(0,1),(-1,-1),colors.HexColor('#f5f5f5')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#ffffff'), colors.HexColor('#f5f5f5')]),
    ]))
    content.append(summary_table)
    content.append(Spacer(1,15))
    
    if remarks_text:
        content.append(Paragraph("REMARKS", heading_style))
        content.append(Paragraph(remarks_text, normal_style))
        content.append(Spacer(1,10))
    
    content.append(Spacer(1,10))
    content.append(Paragraph("CERTIFICATION", heading_style))
    content.append(Paragraph(f"This is to certify that the above-mentioned consolidated wage details are correct.", normal_style))
    content.append(Spacer(1,10))
    
    cert_data = [
        [Paragraph("<b>Prepared By:</b>", info_label_style), Paragraph("_______________", info_value_style),
         Paragraph("<b>Verified By:</b>", info_label_style), Paragraph("_______________", info_value_style)],
        [Paragraph("<b>Date:</b>", info_label_style), Paragraph(datetime.now().strftime('%d-%m-%Y'), info_value_style),
         Paragraph("<b>Date:</b>", info_label_style), Paragraph("_______________", info_value_style)],
    ]
    
    cert_table = Table(cert_data, colWidths=[1.0*inch, 2.0*inch, 1.0*inch, 2.5*inch])
    cert_table.setStyle(TableStyle([
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('PADDING',(0,0),(-1,-1),4),
    ]))
    content.append(cert_table)
    content.append(Spacer(1,15))
    
    content.append(Paragraph(f"<b>EOBI-Regional office {region}</b> | Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}<br/><font size='6'>Zee Shah | {APP_VERSION} | Special thanks to Mr. Nasrullah Shah</font>", footer_style))
    
    doc.build(content)
    show_thanks_dialog("Consolidated Report", current_record_id)
    if os.path.exists(filename): os.startfile(filename)

def clear_all_fields():
    entry_claimant.delete(0, 'end'); entry_father.delete(0, 'end'); entry_eobi.delete(0, 'end'); entry_cnic.delete(0, 'end')
    result.configure(text="Accumulated Average Monthly Wages for OAG: Not Calculated")
    last12_result.configure(text="Last Twelve Month Accumulated Wages for OAP Pension: Not Calculated")
    lesser_result.configure(text="Lesser Rate Information: Not Calculated", fg_color="#c62828")
    missing_display.configure(text="", fg_color=COLORS['warning'])
    table_year.delete(*table_year.get_children())
    employment_periods.clear()
    update_periods_display()
    temporary_changes.clear()
    global yearly_data, final_avg_value, last12_avg_value, qualifying_years, zero_wage_months, lesser_rate_months
    global total_oag_amount, total_oap_amount, oap_eligible, combined_wages, oap_qualifying_period_years, total_months_in_period, current_record_id
    global work_percentage, actual_work_days, adjusted_oag_average, adjusted_years, remarks_text
    global claim_type, survivor_type, death_date, last_36_months_continuous, survivor_eligible, survivor_pension
    global oap_formula_years, lesser_rate_years, zero_wage_years, survivor_service_years
    yearly_data = []; final_avg_value = 0; last12_avg_value = 0; qualifying_years = 0; zero_wage_months = []
    lesser_rate_months = []
    total_oag_amount = 0; total_oap_amount = 0; oap_eligible = False; combined_wages = {}; oap_qualifying_period_years = 0.0; total_months_in_period = 0
    oap_formula_years = 0.0; lesser_rate_years = 0.0; zero_wage_years = 0.0; survivor_service_years = 0.0
    current_record_id = None
    work_percentage = 100.0; actual_work_days = 0; adjusted_oag_average = 0; adjusted_years = 0.0; remarks_text = ""
    claim_type = "self"; survivor_type = ""; death_date = ""; last_36_months_continuous = False; survivor_eligible = False; survivor_pension = 0
    percentage_label.configure(text="Work Percentage: 100% (Full Period)", fg_color=COLORS['success'])
    claim_label.configure(text="Claim Type: INSURED PERSON (Self)", fg_color=COLORS['primary'])
    messagebox.showinfo("Cleared", "All details, employment periods, and temporary changes have been cleared!")

def update_stats():
    cursor.execute("SELECT COUNT(*) FROM employers")
    emp_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT main_code || '-' || sub_code) FROM wages")
    emp_with_wages = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM wages")
    total_wages = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM wages WHERE wage = 0")
    zero_wages = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM calculated_records")
    total_records = cursor.fetchone()[0]
    stats_text = f"""SYSTEM STATISTICS

Total Registered Employers: {emp_count}
Employers with Wage Data: {emp_with_wages}
Total Wage Records: {total_wages}
Zero Wage Records: {zero_wages}
Employment Periods: {len(employment_periods)}
Temporary Changes: {len(temporary_changes)}
Saved Calculation Records: {total_records}
Claim Type: {'INSURED PERSON' if claim_type == 'self' else 'SURVIVOR'}
OAG Qualifying Years: {qualifying_years}
Total Active Months: {total_months_worked}
OAP Service Period: {oap_qualifying_period_years:.2f} years
OAP Formula Years: {oap_formula_years:.2f}
OAP Eligible: {'YES' if oap_eligible else 'NO'}
Survivor Paid Service: {survivor_service_years:.2f} years
Survivor Eligible: {'YES' if survivor_eligible else 'NO'}
Lesser Rate Months: {less_months}
Work Percentage: {work_percentage}%
Current Record ID: {current_record_id if current_record_id else 'None'}

🙏 Special thanks to Mr. Nasrullah Shah
for invaluable support and guidance!"""
    calculated_label.configure(text=stats_text)

def add_new_employer():
    dialog = ctk.CTkToplevel(app)
    dialog.geometry("500x450")
    dialog.title("Add New Employer")
    dialog.grab_set()
    header = ctk.CTkFrame(dialog, fg_color=COLORS['primary'], height=60, corner_radius=10)
    header.pack(fill="x", padx=20, pady=20)
    ctk.CTkLabel(header, text="ADD NEW EMPLOYER", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(expand=True)
    fields = [("Main Code:", "main"), ("Sub Code:", "sub"), ("Employer Name:", "name"), ("City:", "city"), ("Applicability Date:", "app"), ("Beat:", "beat")]
    entries = {}
    for label, key in fields:
        ctk.CTkLabel(dialog, text=label, font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(5,0))
        entry = ctk.CTkEntry(dialog, width=300, height=35, font=ctk.CTkFont(size=12))
        entry.pack(pady=2)
        entries[key] = entry
    def save():
        main = entries['main'].get().strip()
        sub = entries['sub'].get().strip()
        name = entries['name'].get().strip()
        if not all([main, sub, name]):
            messagebox.showwarning("Warning", "Main Code, Sub Code, and Name are required!")
            return
        try:
            cursor.execute("INSERT INTO employers VALUES (?,?,?,?,?,?)",
                          (main, sub, name, entries['city'].get().strip(), entries['app'].get().strip(), entries['beat'].get().strip()))
            conn.commit()
            update_stats()
            messagebox.showinfo("Success", "Employer added successfully!")
            dialog.destroy()
            search()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Employer already exists!")
    ctk.CTkButton(dialog, text="Save Employer", command=save, height=40, width=150, fg_color=COLORS['success']).pack(pady=15)

def show_instructions():
    messagebox.showinfo("Instructions", f"""{APP_TITLE} - {APP_VERSION}

KEY FEATURES:
- Insured Person and Survivor claim types
- Manual, zero, minimum, lesser-rate, and above-minimum wage tracking
- Temporary claimant-specific wage changes
- Actual service-day based OAP/OAG eligibility
- Work percentage and days-based reports
- Professional PDF reports and saved records

CLAIM TYPES:
- INSURED PERSON: OAP when service is {OAP_REQUIRED_YEARS}+ years, otherwise OAG
- SURVIVOR: Pension for heirs/family

SURVIVOR ELIGIBILITY:
1. Death before 60 during service: {SURVIVOR_CONTINUOUS_MONTHS} continuous paid months OR {SURVIVOR_REQUIRED_YEARS_BEFORE_60} paid service years
2. Death before 60 not in service: {SURVIVOR_REQUIRED_YEARS_BEFORE_60} paid service years
3. Death after 60: {SURVIVOR_REQUIRED_YEARS_AFTER_60} paid service years
- Zero-wage months do not count as paid months
- Minimum survivor pension: PKR {MIN_PENSION:,.0f}

OAP / OAG:
- OAP average wage uses the last 12 paid months
- OAG average uses yearly averages; a final partial year counts only when it has at least {OAG_PARTIAL_YEAR_MONTHS} paid months
- Minimum pension: PKR {MIN_PENSION:,.0f}
- Current minimum wage rate coverage: {get_rate_coverage_text()}

Special thanks to Mr. Nasrullah Shah.
Zee Shah - The IT Solutions""")

# ========== UI BUILD ==========
app = ctk.CTk()
app.geometry("1400x850")
app.title(f"{APP_TITLE} - {APP_VERSION}")

main_container = ctk.CTkFrame(app, fg_color=COLORS['bg_dark'])
main_container.pack(fill="both", expand=True, padx=3, pady=3)

header_frame = ctk.CTkFrame(main_container, height=100, corner_radius=10, fg_color=COLORS['primary'])
header_frame.pack(fill="x", padx=3, pady=3)
header_frame.pack_propagate(False)

avatar_frame = ctk.CTkFrame(header_frame, fg_color="transparent", width=90)
avatar_frame.pack(side="left", padx=10, pady=5)
try:
    img = ctk.CTkImage(Image.open(resource_path("logo.png")), size=(70, 70))
except:
    img = create_avatar()
ctk.CTkLabel(avatar_frame, image=img, text="").pack(expand=True)

title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
title_frame.pack(side="left", padx=10, pady=5)
ctk.CTkLabel(title_frame, text=APP_TITLE.upper(), font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack()
bubble_frame = ctk.CTkFrame(title_frame, fg_color=COLORS['primary_light'], corner_radius=12)
bubble_frame.pack(pady=3)
avatar_label = ctk.CTkLabel(bubble_frame, text="👋 Hello! I'm your EOBI Assistant!", font=ctk.CTkFont(size=11), text_color="white", padx=12, pady=6)
avatar_label.pack()

right_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
right_frame.pack(side="right", padx=10, pady=8)
btn_row1 = ctk.CTkFrame(right_frame, fg_color="transparent")
btn_row1.pack(pady=2)
ctk.CTkButton(btn_row1, text="Guide", command=show_instructions, height=30, width=80, fg_color=COLORS['secondary']).pack(side="left", padx=3)
ctk.CTkButton(btn_row1, text="Records", command=show_calculated_records, height=30, width=80, fg_color=COLORS['accent']).pack(side="left", padx=3)
ctk.CTkButton(btn_row1, text="Temp Wages", command=manage_temporary_wages, height=30, width=90, fg_color=COLORS['warning']).pack(side="left", padx=3)
label_emp = ctk.CTkLabel(right_frame, text="No Employer Selected", font=ctk.CTkFont(size=11, weight="bold"), fg_color=COLORS['warning'], text_color="white", corner_radius=6, padx=10, pady=4)
label_emp.pack(pady=3)

tabs = ctk.CTkTabview(main_container, corner_radius=8, fg_color=COLORS['bg_card'])
tabs.pack(fill="both", expand=True, padx=3, pady=3)

# Dashboard Tab
tab_stats = tabs.add("Dashboard")
stats_container = ctk.CTkFrame(tab_stats, fg_color=COLORS['bg_card'])
stats_container.pack(fill="both", expand=True, padx=15, pady=15)
ctk.CTkLabel(stats_container, text="SYSTEM DASHBOARD", font=ctk.CTkFont(size=22, weight="bold"), text_color=COLORS['primary']).pack(pady=15)
calculated_label = ctk.CTkLabel(stats_container, text="Loading...", font=ctk.CTkFont(size=13), fg_color=COLORS['bg_hover'], text_color="white", corner_radius=10, padx=30, pady=25, justify="left")
calculated_label.pack(pady=15)
ctk.CTkButton(stats_container, text="Refresh Dashboard", command=update_stats, height=40, width=180, fg_color=COLORS['primary']).pack(pady=15)

# Search Tab
tab1 = tabs.add("Search")
search_frame = ctk.CTkFrame(tab1, fg_color=COLORS['bg_card'])
search_frame.pack(fill="x", padx=8, pady=8)
entry_search = ctk.CTkEntry(search_frame, placeholder_text="Search by Name or Code...", height=40, font=ctk.CTkFont(size=13))
entry_search.pack(side="left", fill="x", expand=True, padx=(8,8))
ctk.CTkButton(search_frame, text="Search", command=search, height=40, width=100, fg_color=COLORS['primary']).pack(side="right", padx=(0,8))
ctk.CTkButton(search_frame, text="New Employer", command=add_new_employer, height=40, width=130, fg_color=COLORS['success']).pack(side="right", padx=(0,8))

table_frame = ctk.CTkFrame(tab1, fg_color=COLORS['bg_card'])
table_frame.pack(fill="both", expand=True, padx=8, pady=8)
table_emp = ttk.Treeview(table_frame, columns=("Main","Sub","Name","City","App","Beat"), show="headings", height=18)
style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=28, font=('Segoe UI', 9))
style.configure("Treeview.Heading", background=COLORS['primary'], foreground="white", font=('Segoe UI', 9, 'bold'))
style.map('Treeview', background=[('selected', COLORS['primary_light'])])
for c in ("Main","Sub","Name","City","App","Beat"):
    table_emp.heading(c, text=c); table_emp.column(c, width=130)
table_emp.pack(fill="both", expand=True, padx=3, pady=3)
table_emp.bind("<<TreeviewSelect>>", select_emp)
emp_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=table_emp.yview)
table_emp.configure(yscrollcommand=emp_scroll.set); emp_scroll.pack(side="right", fill="y")

# Wages Tab
tab2 = tabs.add("Wages")
wage_container = ctk.CTkFrame(tab2, fg_color=COLORS['bg_card'])
wage_container.pack(fill="both", expand=True, padx=8, pady=8)
wage_container.grid_columnconfigure(1, weight=1)

left_panel = ctk.CTkFrame(wage_container, width=350, fg_color=COLORS['bg_hover'])
left_panel.grid(row=0, column=0, sticky="nsew", padx=(0,8))
left_panel.grid_propagate(False)
ctk.CTkLabel(left_panel, text="WAGE MANAGEMENT", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS['primary']).pack(pady=12)
ctk.CTkButton(left_panel, text="Auto-Add Minimum Wages", command=add_approved, height=45, font=ctk.CTkFont(size=13, weight="bold"), fg_color=COLORS['success']).pack(padx=15, pady=12)
ctk.CTkLabel(left_panel, text="━━━━━━━━━━━━━━━━", text_color="gray").pack(pady=8)
ctk.CTkLabel(left_panel, text="Manual Wage Entry", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS['primary']).pack(pady=(8,5))

ctk.CTkLabel(left_panel, text="From Date:", font=ctk.CTkFont(size=11)).pack(pady=(3,0))
date_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
date_frame.pack(padx=15, pady=3, fill="x")
entry_wage_date = ctk.CTkEntry(date_frame, placeholder_text="DD/MM/YYYY", height=35, font=ctk.CTkFont(size=12))
entry_wage_date.pack(side="left", fill="x", expand=True, padx=(0,3))
ctk.CTkButton(date_frame, text="📅", width=35, height=35, command=lambda: show_calendar(entry_wage_date)).pack(side="right")

ctk.CTkLabel(left_panel, text="To Date (optional):", font=ctk.CTkFont(size=11)).pack(pady=(8,0))
date_frame_to = ctk.CTkFrame(left_panel, fg_color="transparent")
date_frame_to.pack(padx=15, pady=3, fill="x")
entry_wage_date_to = ctk.CTkEntry(date_frame_to, placeholder_text="DD/MM/YYYY (optional)", height=35, font=ctk.CTkFont(size=12))
entry_wage_date_to.pack(side="left", fill="x", expand=True, padx=(0,3))
ctk.CTkButton(date_frame_to, text="📅", width=35, height=35, command=lambda: show_calendar(entry_wage_date_to)).pack(side="right")

entry_wage_amount = ctk.CTkEntry(left_panel, placeholder_text="Monthly Wage (PKR) - 0 = No Contribution", height=38, font=ctk.CTkFont(size=12))
entry_wage_amount.pack(padx=15, pady=8)

button_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
button_frame.pack(pady=15)
add_btn = ctk.CTkButton(button_frame, text="Add", command=add_wage, width=80, height=38, fg_color=COLORS['primary'])
add_btn.pack(side="left", padx=3)
ctk.CTkButton(button_frame, text="Edit", command=edit_wage, width=80, height=38, fg_color=COLORS['warning']).pack(side="left", padx=3)
ctk.CTkButton(button_frame, text="Delete", command=delete, width=80, height=38, fg_color=COLORS['error']).pack(side="left", padx=3)
ctk.CTkButton(button_frame, text="Bulk Delete", command=bulk_delete_wages, width=90, height=38, fg_color=COLORS['error']).pack(side="left", padx=3)

right_panel = ctk.CTkFrame(wage_container, fg_color=COLORS['bg_hover'])
right_panel.grid(row=0, column=1, sticky="nsew")
ctk.CTkLabel(right_panel, text="WAGE HISTORY", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS['primary']).pack(pady=8)

table_wages = ttk.Treeview(right_panel, columns=("ID","Month","Wage","Status"), show="headings", height=10)
table_wages.heading("ID", text="ID"); table_wages.heading("Month", text="Date"); table_wages.heading("Wage", text="Wage (PKR)"); table_wages.heading("Status", text="Status")
table_wages.column("ID", width=50); table_wages.column("Month", width=140); table_wages.column("Wage", width=170); table_wages.column("Status", width=110)
wage_scroll = ttk.Scrollbar(right_panel, orient="vertical", command=table_wages.yview)
table_wages.configure(yscrollcommand=wage_scroll.set)
table_wages.pack(side="left", fill="both", expand=True, padx=3, pady=3); wage_scroll.pack(side="right", fill="y")

status_panel = ctk.CTkFrame(right_panel, fg_color=COLORS['bg_dark'], height=180)
status_panel.pack(fill="x", padx=3, pady=3)
wage_status_label = ctk.CTkLabel(status_panel, text="Select an employer to view wage status", 
                                  font=ctk.CTkFont(size=9), text_color="white", 
                                  fg_color=COLORS['bg_hover'], corner_radius=6, 
                                  padx=10, pady=6, justify="left")
wage_status_label.pack(fill="both", expand=True, padx=6, pady=3)

ctk.CTkButton(status_panel, text="🔍 See More Details", command=show_full_wage_status,
             fg_color=COLORS['secondary'], height=28, width=140, font=ctk.CTkFont(size=11)).pack(pady=5)

# Calculate Tab
tab3 = tabs.add("Calculate")
calc_container = ctk.CTkScrollableFrame(tab3, fg_color=COLORS['bg_card'])
calc_container.pack(fill="both", expand=True, padx=8, pady=8)

info_section = ctk.CTkFrame(calc_container, fg_color=COLORS['bg_hover'])
info_section.pack(fill="x", padx=8, pady=8)
ctk.CTkLabel(info_section, text="CLAIMANT INFORMATION", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS['primary']).pack(pady=10)
info_grid = ctk.CTkFrame(info_section, fg_color="transparent")
info_grid.pack(pady=3)
entry_claimant = ctk.CTkEntry(info_grid, placeholder_text="Claimant Name", width=280, height=38, font=ctk.CTkFont(size=12))
entry_claimant.grid(row=0, column=0, padx=12, pady=6)
entry_father = ctk.CTkEntry(info_grid, placeholder_text="Father's Name", width=280, height=38, font=ctk.CTkFont(size=12))
entry_father.grid(row=0, column=1, padx=12, pady=6)
entry_eobi = ctk.CTkEntry(info_grid, placeholder_text="EOBI Registration No:", width=280, height=38, font=ctk.CTkFont(size=12))
entry_eobi.grid(row=1, column=0, padx=12, pady=6)
entry_cnic = ctk.CTkEntry(info_grid, placeholder_text="CNIC Number", width=280, height=38, font=ctk.CTkFont(size=12))
entry_cnic.grid(row=1, column=1, padx=12, pady=6)

# Claim Type Section
claim_section = ctk.CTkFrame(calc_container, fg_color=COLORS['bg_hover'])
claim_section.pack(fill="x", padx=8, pady=8)
ctk.CTkLabel(claim_section, text="CLAIM TYPE", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS['primary']).pack(pady=8)
claim_btn_frame = ctk.CTkFrame(claim_section, fg_color="transparent")
claim_btn_frame.pack(fill="x", padx=8, pady=3)
ctk.CTkButton(claim_btn_frame, text="Select Claim Type", command=show_claim_type_dialog, 
             fg_color=COLORS['survivor'], height=35, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=3)
claim_label = ctk.CTkLabel(claim_section, text="Claim Type: INSURED PERSON (Self)", 
                          font=ctk.CTkFont(size=12, weight="bold"), fg_color=COLORS['primary'], 
                          text_color="white", corner_radius=6, padx=10, pady=6)
claim_label.pack(fill="x", padx=8, pady=5)

periods_section = ctk.CTkFrame(calc_container, fg_color=COLORS['bg_hover'])
periods_section.pack(fill="x", padx=8, pady=8)
ctk.CTkLabel(periods_section, text="EMPLOYMENT PERIODS", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS['primary']).pack(pady=8)

btn_periods_frame = ctk.CTkFrame(periods_section, fg_color="transparent")
btn_periods_frame.pack(fill="x", padx=8, pady=3)
ctk.CTkButton(btn_periods_frame, text="Add Employment Period", command=add_employment_period, fg_color=COLORS['success'], height=35, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=3)
ctk.CTkButton(btn_periods_frame, text="Manage Temp Wages", command=manage_temporary_wages, fg_color=COLORS['accent'], height=35, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=3)
ctk.CTkButton(btn_periods_frame, text="Remove Selected", command=remove_period, fg_color=COLORS['error'], height=35, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=3)

listbox_frame = ctk.CTkFrame(periods_section, fg_color="transparent")
listbox_frame.pack(fill="both", expand=True, padx=8, pady=3)
periods_listbox = tk.Listbox(listbox_frame, bg="#2b2b2b", fg="white", selectbackground=COLORS['primary_light'], font=('Segoe UI', 9), height=3)
periods_listbox.pack(side="left", fill="both", expand=True)
period_scroll = ttk.Scrollbar(listbox_frame, orient="vertical", command=periods_listbox.yview)
periods_listbox.configure(yscrollcommand=period_scroll.set)
period_scroll.pack(side="right", fill="y")

percentage_section = ctk.CTkFrame(calc_container, fg_color=COLORS['bg_hover'])
percentage_section.pack(fill="x", padx=8, pady=8)
ctk.CTkLabel(percentage_section, text="WORK PERCENTAGE & REMARKS", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS['primary']).pack(pady=8)

pct_btn_frame = ctk.CTkFrame(percentage_section, fg_color="transparent")
pct_btn_frame.pack(fill="x", padx=8, pady=3)
ctk.CTkButton(pct_btn_frame, text="Set Work Percentage & Remarks", command=show_work_percentage_dialog, fg_color=COLORS['secondary'], height=35, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=3)

percentage_label = ctk.CTkLabel(percentage_section, text="Work Percentage: 100% (Full Period)", 
                               font=ctk.CTkFont(size=12, weight="bold"), fg_color=COLORS['success'], 
                               text_color="white", corner_radius=6, padx=10, pady=6)
percentage_label.pack(fill="x", padx=8, pady=5)

action_frame = ctk.CTkFrame(calc_container, fg_color="transparent")
action_frame.pack(fill="x", padx=8, pady=8)
ctk.CTkButton(action_frame, text="Calculate Wages", command=calculate, height=45, width=180, font=ctk.CTkFont(size=14, weight="bold"), fg_color=COLORS['primary']).pack(side="left", padx=8, pady=3)
ctk.CTkButton(action_frame, text="Generate PDF Report", command=show_report_type_dialog, height=45, width=180, font=ctk.CTkFont(size=14, weight="bold"), fg_color=COLORS['success']).pack(side="left", padx=8, pady=3)
ctk.CTkButton(action_frame, text="Clear Details", command=clear_all_fields, height=45, width=160, font=ctk.CTkFont(size=14, weight="bold"), fg_color=COLORS['error']).pack(side="left", padx=8, pady=3)

results_frame = ctk.CTkFrame(calc_container, fg_color=COLORS['bg_hover'])
results_frame.pack(fill="x", padx=8, pady=8)
ctk.CTkLabel(results_frame, text="CALCULATION RESULTS", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS['primary']).pack(pady=10)

result = ctk.CTkLabel(results_frame, text="Accumulated Average Monthly Wages for OAG: Not Calculated", font=ctk.CTkFont(size=14, weight="bold"), fg_color="#1a237e", text_color="white", corner_radius=8, padx=15, pady=12)
result.pack(fill="x", padx=12, pady=6)
last12_result = ctk.CTkLabel(results_frame, text="Last Twelve Month Accumulated Wages for OAP Pension: Not Calculated", font=ctk.CTkFont(size=13, weight="bold"), fg_color="#1565c0", text_color="white", corner_radius=8, padx=15, pady=10)
last12_result.pack(fill="x", padx=12, pady=6)
lesser_result = ctk.CTkLabel(results_frame, text="Lesser Rate Information: Not Calculated", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#c62828", text_color="white", corner_radius=8, padx=15, pady=10)
lesser_result.pack(fill="x", padx=12, pady=6)
missing_display = ctk.CTkLabel(results_frame, text="", font=ctk.CTkFont(size=12, weight="bold"), fg_color=COLORS['warning'], text_color="white", corner_radius=8, padx=15, pady=10)
missing_display.pack(fill="x", padx=12, pady=6)

table_frame_year = ctk.CTkFrame(calc_container, fg_color=COLORS['bg_hover'])
table_frame_year.pack(fill="both", expand=True, padx=8, pady=8)
ctk.CTkLabel(table_frame_year, text="CONSOLIDATED YEARLY BREAKDOWN", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS['primary']).pack(pady=8)

table_year = ttk.Treeview(table_frame_year, columns=("Year","Period","Average","Months","Status","Days"), show="headings", height=6)
table_year.heading("Year", text="Year"); table_year.heading("Period", text="Actual Period"); table_year.heading("Average", text="Avg Monthly Wage"); table_year.heading("Months", text="Months"); table_year.heading("Status", text="Status"); table_year.heading("Days", text="Days")
table_year.column("Year", width=55); table_year.column("Period", width=190); table_year.column("Average", width=130); table_year.column("Months", width=55); table_year.column("Status", width=260); table_year.column("Days", width=65)
year_scroll = ttk.Scrollbar(table_frame_year, orient="vertical", command=table_year.yview)
table_year.configure(yscrollcommand=year_scroll.set)
table_year.pack(side="left", fill="both", expand=True, padx=3, pady=3)
year_scroll.pack(side="right", fill="y")

# Initialize
load_csv()
update_stats()
app.after(1000, update_avatar_message)
app.after(500, show_instructions)
app.mainloop()

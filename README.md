# EOBI Wage & Pension Calculation System

Professional calculator for EOBI wage, service-day, OAG, OAP, and survivor pension calculations.

## Features

- **Insured Person and Survivor claim types**
- **Manual wage entry with status tracking** (Zero, Lesser Rate, Minimum, Above Minimum)
- **Temporary wage changes** for claimant-specific adjustments
- **Service-day based calculations** with work percentage adjustment
- **Full OAP/OAG eligibility checking**
- **Survivor pension eligibility** with 36-month continuous check
- **Professional PDF reports** (OAG, OAP, Survivor, Consolidated, Days-Based)
- **Saved calculation records** with search and load functionality
- **Visual charts** for wage trends

## Business Rules

### OAP / OAG
- Scheme start date: 01/07/1976
- Minimum pension: PKR 11,500
- OAP eligibility: service period >= 14.5 years
- OAP wage average: average of last 12 paid months
- OAP formula years: service years - lesser-rate years - zero-wage years
- OAP pension: (last 12 month avg x formula years) / 50
- OAG average: average of qualifying yearly averages
- Partial year qualifies with >= 6 paid months

### Survivor Pension
- **Died during service before 60**: 36 continuous paid months OR 5 paid service years
- **Died before 60 not in service**: 5 paid service years
- **Died after 60**: 15 paid service years
- Zero-wage months do not count as paid months

## Minimum Wage Rates

Current rate coverage: 2025-07 to 2026-06: PKR 40,000

## Deployment

### On Render
1. Push this repository to GitHub
2. Go to render.com
3. Click "New +" → "Blueprint"
4. Connect your GitHub repository
5. Render will auto-deploy

### On Streamlit Cloud
1. Push to GitHub
2. Go to share.streamlit.io
3. Connect your repository
4. Deploy

### Local Desktop EXE
Run `rebuild.bat` to create a Windows executable.

## Tech Stack
- Streamlit (Web) / CustomTkinter (Desktop)
- Pandas for data handling
- Plotly for charts
- ReportLab for PDF generation (desktop only)

Special thanks to Mr. Nasrullah Shah for invaluable support and guidance.
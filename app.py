#!/usr/bin/env python3
# encoding: utf-8

import os
import base64
import math
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, render_template, request

# --- Décodage du service_account.json depuis la var d'env Base64 ---
b64 = os.getenv('SERVICE_ACCOUNT_JSON_BASE64')
SERVICE_ACCOUNT_PATH = os.getenv('SERVICE_ACCOUNT_PATH', 'service_account.json')
if b64:
    data = base64.b64decode(b64)
    with open(SERVICE_ACCOUNT_PATH, 'wb') as f:
        f.write(data)
# ----------------------------------------------------------------

app = Flask(__name__)

# Configuration Google Sheets
SPREADSHEET_KEY = '19tmcUn-MXUqQrzF43BYw8zeLOE7GZiQhk58MhrFAgRA'
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

def get_workbook():
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_PATH, SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_KEY)

def get_sheet_data(sheet_name):
    """Lit un onglet et retourne ses lignes en dicts, convertit 'Perf.' en float."""
    wb = get_workbook()
    ws = wb.worksheet(sheet_name)
    rows = ws.get_all_records()
    for row in rows:
        try:
            row['Perf.'] = float(row.get('Perf.', '') or 0)
        except ValueError:
            row['Perf.'] = 0.0
    return rows

def fetch_and_parse(url):
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')
    table = soup.find('table', id='ctnQualifies')
    if not table:
        raise RuntimeError("Tableau d'engagés introuvable.")
    return soup, table.find_all('tr')

def parse_link_params(url):
    qs = parse_qs(urlparse(url).query)
    return qs.get('frmepreuve', [''])[0], qs.get('frmsexe', [''])[0]

def get_competition_name(soup):
    div = soup.find('div', class_='headers1')
    full = div.get_text(strip=True) if div else 'Compétition'
    return full.split(' - ',1)[1].strip() if ' - ' in full else full

def extract_and_sort(rows):
    tmp = []
    for tr in rows:
        tds = tr.find_all('td')
        if len(tds) < 13:
            continue
        name = tds[2].get_text(strip=True)
        if not name or name.lower() == 'nom':
            continue
        club = tds[4].get_text(strip=True)
        cat  = tds[8].get_text(strip=True)
        perf = tds[12].get_text(strip=True)
        try:
            perf_val = float(perf)
        except:
            perf_val = None
        tmp.append((name, club, cat, perf, perf_val))
    tmp.sort(key=lambda x: x[4] if x[4] is not None else -math.inf, reverse=True)
    return [[i+1, *rec[:4]] for i, rec in enumerate(tmp)]

def write_to_sheet(data, sheet_name):
    wb = get_workbook()
    try:
        ws = wb.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet(title=sheet_name, rows=str(len(data)+1), cols="5")
    ws.batch_clear([f"A1:E{ws.row_count}"])
    ws.update('A1:E1', [["Place", "Nom / Prénom", "Club", "Cat.", "Perf."]])
    ws.append_rows(data, value_input_option='RAW')

def process_url(url):
    soup, rows = fetch_and_parse(url)
    epreuve, sexe = parse_link_params(url)
    comp = get_competition_name(soup)
    sheet = f"{comp} – {epreuve} {sexe}"
    data = extract_and_sort(rows)
    if data:
        write_to_sheet(data, sheet)
    return sheet, len(data)

def get_competitions():
    """Lit l’onglet 'Competitions' (Nom + URL) et retourne une liste de dicts."""
    wb = get_workbook()
    try:
        ws = wb.worksheet('Competitions')
    except gspread.exceptions.WorksheetNotFound:
        return []
    return ws.get_all_records()

@app.route('/', methods=['GET'])
def index():
    wb = get_workbook()
    sheet_names = [ws.title for ws in wb.worksheets()]

    selected_sheet   = request.args.get('sheet', sheet_names[0])
    if selected_sheet not in sheet_names:
        selected_sheet = sheet_names[0]

    category         = request.args.get('category', '')
    sort_field       = request.args.get('sort', 'Perf.')
    sort_order       = request.args.get('order', 'desc')

    rows = get_sheet_data(selected_sheet)
    if category:
        rows = [r for r in rows if r.get('Cat.') == category]

    reverse = (sort_order == 'desc')
    rows.sort(key=lambda r: r.get(sort_field, 0) or 0, reverse=reverse)

    all_rows   = get_sheet_data(selected_sheet)
    categories = sorted({r.get('Cat.') for r in all_rows if r.get('Cat.')})

    return render_template(
        'table.html',
        sheet_names=sheet_names,
        selected_sheet=selected_sheet,
        categories=categories,
        selected_category=category,
        sort_field=sort_field,
        sort_order=sort_order,
        rows=rows
    )

@app.route('/reload', methods=['GET', 'POST'])
def reload():
    comps = get_competitions()
    message = None
    if request.method == 'POST':
        selected = request.form.getlist('selected')
        total = 0
        for comp in comps:
            if comp['Nom'] in selected:
                sheet, count = process_url(comp['URL'])
                total += count
        message = f"✅ {total} athlètes rechargés dans {len(selected)} compétitions."
    return render_template('reload.html', competitions=comps, message=message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

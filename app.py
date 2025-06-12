#!/usr/bin/env python3
# encoding: utf-8

import os
import base64
import math
import requests
import re
from urllib.parse import urlparse, parse_qs
from datetime import datetime, date
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, render_template, request, redirect, url_for, flash, abort


# --- Décodage du service_account.json depuis la var d'env Base64 ---
b64 = os.getenv('SERVICE_ACCOUNT_JSON_BASE64')
SERVICE_ACCOUNT_PATH = os.getenv('SERVICE_ACCOUNT_PATH', 'service_account.json')
if b64:
    data = base64.b64decode(b64)
    with open(SERVICE_ACCOUNT_PATH, 'wb') as f:
        f.write(data)
# ----------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'change-me')

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
    wb = get_workbook()
    ws = wb.worksheet(sheet_name)
    rows = ws.get_all_records()
    for row in rows:
        try:
            row['Perf.'] = float(row.get('Perf.', '') or 0)
        except ValueError:
            row['Perf.'] = 0.0
    return rows

def get_competitions():
    wb = get_workbook()
    try:
        ws = wb.worksheet('Competitions')
    except gspread.exceptions.WorksheetNotFound:
        return []
    return ws.get_all_records()

def append_competition(name, url):
    wb = get_workbook()
    try:
        ws = wb.worksheet('Competitions')
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet(title='Competitions', rows='100', cols='2')
        ws.append_row(['Nom', 'URL'])
    ws.append_row([name, url], value_input_option='RAW')

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
        if len(tds) < 13: continue
        name = tds[2].get_text(strip=True)
        if not name or name.lower() == 'nom': continue
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
    ws.update('A1:E1', [["Place","Nom / Prénom","Club","Cat.","Perf."]])
    ws.append_rows(data, value_input_option='RAW')

def process_url(url):
    soup, rows = fetch_and_parse(url)
    epreuve, sexe = parse_link_params(url)
    comp = get_competition_name(soup)
    sheet_name = f"{comp} – {epreuve} {sexe}"
    data = extract_and_sort(rows)
    if data:
        write_to_sheet(data, sheet_name)
    return sheet_name, len(data)

# ---------------- ROUTES EXISTANTES ----------------

@app.route('/', methods=['GET'])
def index():
    wb = get_workbook()

    # Récupère tous les onglets puis exclut "Calendrier" et "Competitions"
    all_sheets = [ws.title for ws in wb.worksheets()]
    sheet_names = [name for name in all_sheets if name not in ('Calendrier', 'Competitions', 'Engagement', 'Engagement - Meeting du Souvenir', 'Engagement - Championnat regional')]

    # Sélection de la feuille (paramètre ?sheet= ou première feuille disponible)
    selected_sheet = request.args.get('sheet', sheet_names[0])
    if selected_sheet not in sheet_names:
        selected_sheet = sheet_names[0]

    # Filtrage / tri
    selected_category = request.args.get('category', '')
    sort_field        = request.args.get('sort', 'Perf.')
    sort_order        = request.args.get('order', 'desc')

    rows = get_sheet_data(selected_sheet)
    if selected_category:
        rows = [r for r in rows if r.get('Cat.') == selected_category]

    reverse = (sort_order == 'desc')
    rows.sort(key=lambda r: r.get(sort_field, 0) or 0, reverse=reverse)

    # Pour la liste des catégories disponibles
    all_rows   = get_sheet_data(selected_sheet)
    categories = sorted({r.get('Cat.') for r in all_rows if r.get('Cat.')})

    return render_template(
        'table.html',
        sheet_names=sheet_names,
        selected_sheet=selected_sheet,
        categories=categories,
        selected_category=selected_category,
        sort_field=sort_field,
        sort_order=sort_order,
        rows=rows
    )


@app.route('/reload', methods=['GET','POST'])
def reload():
    comps = get_competitions()
    message = None
    if request.method == 'POST':
        selected = request.form.getlist('selected')
        total = 0
        for comp in comps:
            if comp['Nom'] in selected:
                _, count = process_url(comp['URL'])
                total += count
        message = f"✅ {total} athlètes rechargés dans {len(selected)} compétitions."
    return render_template('reload.html',
                           competitions=comps,
                           message=message)

@app.route('/add', methods=['GET','POST'])
def add():
    message = None
    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            try:
                sheet_name, count = process_url(url)
                append_competition(sheet_name, url)
                message = f"✅ Compétition « {sheet_name} » ajoutée et {count} athlètes importés."
            except Exception as e:
                message = f"❌ Erreur : {e}"
    return render_template('add.html', message=message)

@app.route('/help', methods=['GET'])
def help():
    return render_template('help.html')

# ---------------- ROUTE CALENDRIER ----------------

def parse_french_date(s: str) -> date:
    s = (s or "").strip()
    # 1) format numérique jj/mm/AAAA
    m = re.match(r'^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{2,4})\s*$', s)
    if m:
        day, mon, yr = m.groups()
        try:
            return date(int(yr), int(mon), int(day))
        except ValueError:
            return date.min
    # 2) format texte "29 mai 2025"
    month_map = {
        'janvier':1, 'février':2, 'mars':3, 'avril':4,
        'mai':5, 'juin':6, 'juillet':7, 'août':8,
        'septembre':9, 'octobre':10, 'novembre':11, 'décembre':12
    }
    parts = s.split()
    if len(parts) == 3:
        day_str, mon_str, yr_str = parts
        try:
            day = int(day_str)
            yr  = int(yr_str)
            mnum = month_map.get(mon_str.lower())
            if mnum:
                return date(yr, mnum, day)
        except ValueError:
            pass
    return date.min

@app.route('/calendar')
def calendar():
    wb = get_workbook()
    try:
        ws = wb.worksheet('Calendrier')
    except gspread.exceptions.WorksheetNotFound:
        return "❌ Feuille “Calendrier” introuvable.", 404

    # 1. Récupération brute des lignes
    rows = ws.get_all_records()

    # 2. Parsez et stockez la date
    for r in rows:
        r['_parsed_date'] = parse_french_date(r.get('Date', ''))

    # 3. Filtrez uniquement les dates à venir (>= aujourd'hui)
    today    = date.today()
    upcoming = [r for r in rows if r['_parsed_date'] >= today]

    # 4. Triez de la plus proche à la plus lointaine
    upcoming.sort(key=lambda r: r['_parsed_date'])

    # 5. Rendu
    return render_template(
        'calendar.html',
        rows=upcoming,
        today=today
    )

EPREUVES = ['100 m', '200 m', 'Longueur', 'Triple saut', 'Hauteur', 'Poids', 'Disque', 'Javelot']

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    wb = get_workbook()
    # On lit la feuille 'Engagement' qui contient la liste des compétitions
    try:
        ws = wb.worksheet('Engagement')
    except gspread.exceptions.WorksheetNotFound:
        abort(404, description="❌ Feuille “Engagement” introuvable.")
    # chaque ligne : {'Nom': ..., 'Feuille': ...}
    compets = ws.get_all_records()

    message = None
    if request.method == 'POST':
        nom  = request.form.get('nom','').strip()
        prenom = request.form.get('prenom','').strip()
        feuille = request.form.get('competition')
        # on récupère les 3 épreuves + perfs
        selections = []
        for i in range(1,4):
            ep = request.form.get(f'epreuve{i}')
            perf = request.form.get(f'perf{i}')
            if ep and ep != 'aucune' and perf:
                selections.append((ep, perf))
        if not nom or not prenom or not feuille or not selections:
            flash("⚠️ Merci de renseigner votre nom, prénom, la compétition et au moins une épreuve avec perf.", "warning")
        else:
            try:
                ws_cdt = wb.worksheet(feuille)
            except gspread.exceptions.WorksheetNotFound:
                flash(f"❌ Feuille « {feuille} » introuvable.", "danger")
            else:
                # on cherche la ligne correspondant à nom/prenom
                data = ws_cdt.get_all_records()
                idx = None
                for i, row in enumerate(data, start=2):
                    if row.get('Nom','').strip().lower()==nom.lower() and row.get('Prénom','').strip().lower()==prenom.lower():
                        idx = i
                        break
                if idx is None:
                    flash("❌ Athlète non trouvé·e dans la feuille d'engagement.", "danger")
                else:
                    # pour chaque épreuve on écrit la perf dans la colonne correspondante
                    header = ws_cdt.row_values(1)
                    updates = []
                    for ep, perf in selections:
                        try:
                            col = header.index(ep) + 1
                        except ValueError:
                            flash(f"❌ Épreuve « {ep} » introuvable en entête.", "danger")
                            continue
                        updates.append({
                            'range': gspread.utils.rowcol_to_a1(idx, col),
                            'values': [[perf]]
                        })
                    if updates:
                        ws_cdt.batch_update(updates)
                        flash("✅ Inscription enregistrée.", "success")

    return render_template('inscription.html',
                           compets=compets,
                           epreuves=EPREUVES)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
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

# --- Décodage du service_account depuis la var d'env Base64 ---
b64 = os.getenv('SERVICE_ACCOUNT_JSON_BASE64')
SERVICE_ACCOUNT_PATH = os.getenv('SERVICE_ACCOUNT_PATH', 'service_account.json')
if b64:
    data = base64.b64decode(b64)
    with open(SERVICE_ACCOUNT_PATH, 'wb') as f:
        f.write(data)
# --------------------------------------------------------------

# Google Sheets
SPREADSHEET_KEY = '19tmcUn-MXUqQrzF43BYw8zeLOE7GZiQhk58MhrFAgRA'
SCOPES = ['https://spreadsheets.google.com/feeds',
          'https://www.googleapis.com/auth/drive']

def fetch_and_parse(url):
    """Télécharge la page, renvoie soup + <tr> du tableau."""
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')
    table = soup.find('table', id='ctnQualifies')
    if not table:
        raise RuntimeError("Tableau d'engagés introuvable.")
    return soup, table.find_all('tr')

def parse_link_params(url):
    """Extrait frmepreuve et frmsexe de l'URL."""
    qs = parse_qs(urlparse(url).query)
    return qs.get('frmepreuve', [''])[0], qs.get('frmsexe', [''])[0]

def get_competition_name(soup):
    """Récupère le nom après la date dans <div class='headers1'>."""
    div = soup.find('div', class_='headers1')
    full = div.get_text(strip=True) if div else 'Compétition'
    return full.split(' - ',1)[1].strip() if ' - ' in full else full

def extract_and_sort(rows):
    """Retourne [[place,name,club,cat,perf],…] trié perf décroissante."""
    tmp = []
    for tr in rows:
        tds = tr.find_all('td')
        if len(tds) < 13: continue
        name = tds[2].get_text(strip=True)
        if not name or name.lower()=='nom': continue
        club, cat, perf = tds[4].get_text(strip=True), tds[8].get_text(strip=True), tds[12].get_text(strip=True)
        try: perf_val = float(perf)
        except: perf_val = None
        tmp.append((name, club, cat, perf, perf_val))
    tmp.sort(key=lambda x: x[4] if x[4] is not None else -math.inf, reverse=True)
    return [[i+1, *rec[:4]] for i, rec in enumerate(tmp)]

def write_to_sheet(data, sheet_name):
    """Écrit l’en-tête + data dans l’onglet sheet_name (créé si besoin)."""
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_PATH, SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SPREADSHEET_KEY)
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=str(len(data)+1), cols="5")
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
        print(f"✔️  {len(data)} lignes écrites dans l'onglet «{sheet_name}»")
    else:
        print(f"⚠️  Aucun athlète pour {sheet_name}")

def main():
    # Si lien.txt existe, on boucle dessus, sinon on demande une URL
    if os.path.isfile('lien.txt'):
        with open('lien.txt', encoding='utf-8') as f:
            liens = [l.strip() for l in f if l.strip()]
        for lien in liens:
            print(f"\n→ Traitement de {lien}")
            try:
                process_url(lien)
            except Exception as e:
                print(f"❌ Erreur sur {lien} : {e}")
    else:
        url = input("Entrez le lien de la liste des engagé·e·s : ").strip()
        process_url(url)

if __name__ == "__main__":
    main()

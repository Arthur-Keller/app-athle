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

# --- Décodage du service_account.json depuis la variable d'environnement Base64 ---
b64 = os.getenv('SERVICE_ACCOUNT_JSON_BASE64')
SERVICE_ACCOUNT_PATH = os.getenv('SERVICE_ACCOUNT_PATH', 'service_account.json')
if b64:
    data = base64.b64decode(b64)
    with open(SERVICE_ACCOUNT_PATH, 'wb') as f:
        f.write(data)
# -------------------------------------------------------------------------------

# Clé du Google Sheet (ou mettez-la en variable d'env si vous préférez)
SPREADSHEET_KEY = '19tmcUn-MXUqQrzF43BYw8zeLOE7GZiQhk58MhrFAgRA'

# Scopes Google Sheets/Drive
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
]

def fetch_and_parse(url):
    """Télécharge la page, renvoie soup + liste de <tr> du tableau d'engagés."""
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')
    table = soup.find('table', id='ctnQualifies')
    if not table:
        raise RuntimeError("Tableau des engagés introuvable (id='ctnQualifies').")
    return soup, table.find_all('tr')

def parse_link_params(url):
    """Extrait frmepreuve et frmsexe de l'URL."""
    qs = parse_qs(urlparse(url).query)
    epreuve = qs.get('frmepreuve', [''])[0]
    sexe    = qs.get('frmsexe',    [''])[0]
    return epreuve, sexe

def get_competition_name(soup):
    """Lit le <div class='headers1'> et retire la date."""
    div = soup.find('div', class_='headers1')
    full = div.get_text(strip=True) if div else 'Compétition'
    if ' - ' in full:
        return full.split(' - ', 1)[1].strip()
    return full

def extract_and_sort(rows):
    """Extrait [rank, nom, club, cat, perf], trie perf décroissante."""
    data = []
    for tr in rows:
        tds = tr.find_all('td')
        if len(tds) < 13:
            continue
        name = tds[2].get_text(strip=True)
        if not name or name.lower() == 'nom':
            continue
        club    = tds[4].get_text(strip=True)
        cat     = tds[8].get_text(strip=True)
        perfstr = tds[12].get_text(strip=True)
        try:
            perf = float(perfstr)
        except:
            perf = None
        data.append((name, club, cat, perfstr, perf))
    data.sort(key=lambda x: x[4] if x[4] is not None else -math.inf, reverse=True)
    # Numérotation
    return [[i+1, rec[0], rec[1], rec[2], rec[3]]
            for i, rec in enumerate(data)]

def write_to_sheet(data, sheet_name):
    """Écrit dans l'onglet sheet_name (créé si absent), à partir de la ligne 2."""
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_PATH, SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SPREADSHEET_KEY)
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=str(len(data)+1), cols="5")
    # Vide A1:E
    ws.batch_clear([f"A1:E{ws.row_count}"])
    # En-tête
    ws.update(range_name='A1:E1',
              values=[["Place", "Nom / Prénom", "Club", "Cat.", "Perf."]])
    # Contenu
    ws.append_rows(data, value_input_option='RAW')

def main():
    url = input("Entrez le lien de la liste des engagé·e·s : ").strip()
    try:
        soup, rows = fetch_and_parse(url)
    except Exception as e:
        print("❌ Erreur lors de la récupération de la page :", e)
        return

    epreuve, sexe = parse_link_params(url)
    compname = get_competition_name(soup)
    sheet_name = f"{compname} – {epreuve} {sexe}"

    data = extract_and_sort(rows)
    if not data:
        print("⚠️ Aucun athlète trouvé.")
        return

    try:
        write_to_sheet(data, sheet_name)
        print(f"✅ {len(data)} athlètes classé·e·s et envoyés dans l'onglet « {sheet_name} ».")
    except Exception as e:
        print("❌ Erreur d'écriture dans Google Sheets :", e)

if __name__ == "__main__":
    main()

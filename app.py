#!/usr/bin/env python3
# encoding: utf-8

from flask import Flask, render_template, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

app = Flask(__name__)

# Configuration Google Sheets
SHEET_KEY = '19tmcUn-MXUqQrzF43BYw8zeLOE7GZiQhk58MhrFAgRA'
SERVICE_ACCOUNT_PATH = os.getenv('SERVICE_ACCOUNT_PATH', 'service_account.json')
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

def get_workbook():
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_PATH, SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_KEY)

def get_sheet_data(sheet_name):
    """
    Récupère toutes les lignes de la feuille sheet_name sous forme de liste de dicts,
    convertit Perf. en float pour le tri.
    """
    wb = get_workbook()
    ws = wb.worksheet(sheet_name)
    rows = ws.get_all_records()
    for row in rows:
        try:
            row['Perf.'] = float(row.get('Perf.', '') or 0)
        except ValueError:
            row['Perf.'] = 0
    return rows

@app.route('/')
def index():
    wb = get_workbook()
    # Liste des onglets disponibles
    sheet_names = [ws.title for ws in wb.worksheets()]

    # Récup params
    selected_sheet = request.args.get('sheet', sheet_names[0])
    if selected_sheet not in sheet_names:
        selected_sheet = sheet_names[0]

    category   = request.args.get('category', '')
    sort_field = request.args.get('sort', 'Perf.')
    sort_order = request.args.get('order', 'desc')

    # Récup et préparation des données
    rows = get_sheet_data(selected_sheet)
    if category:
        rows = [r for r in rows if r.get('Cat.') == category]

    reverse = (sort_order == 'desc')
    rows.sort(key=lambda r: r.get(sort_field, 0) or 0, reverse=reverse)

    # Extraction des catégories pour le filtre
    all_rows = get_sheet_data(selected_sheet)
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

if __name__ == '__main__':
    # Démarre l'app sur http://localhost:5000
    app.run(host='0.0.0.0', port=5000, debug=True)

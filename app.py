from flask import Flask, request, jsonify, render_template
import json
import pandas as pd
import numpy as np  # Import numpy
import logging
from datetime import datetime

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Load the JSON file
with open('data.json', 'r') as file:
    data = json.load(file)

# Create dictionaries for quick lookup
sifra_to_coordinates = {feature['properties']['SIFRA']: feature['geometry']['coordinates']
                        for feature in data['features']
                        if 'geometry' in feature and 'coordinates' in feature['geometry']}

# Read and process the Excel file
df = pd.read_excel('EP_Eksport_Uredjaja.xlsx', sheet_name='Eksport_uredjaja', skiprows=6)
df = df.rename(columns=lambda x: x.strip())
df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
df = df[~(df.duplicated(subset='Šifra') & df['Naziv TS'].isnull())]
df['Serijski'] = df['Serijski'].astype(int)
df['Šifra'] = df['Šifra'].astype(int)
df = df.drop_duplicates(subset=['Serijski', 'Šifra'])

# Mapping 'Serijski' to 'Šifra'
serijski_broj_to_sifra = dict(zip(df['Serijski'], df['Šifra']))

# Utility functions
def find_coordinates_by_sifra(sifra, sifra_to_coordinates):
    return sifra_to_coordinates.get(sifra, None)

def find_sifra_by_serijski_broj(serijski_broj, serijski_broj_to_sifra):
    return serijski_broj_to_sifra.get(serijski_broj, None)

def create_google_maps_url(coordinates):
    lon, lat = coordinates
    return f"https://www.google.com/maps?q={lat},{lon}"

def format_date(date):
    return date.strftime('%d.%m.%Y')

def convert_to_native_types(data):
    """Convert numpy data types to native Python types."""
    if isinstance(data, pd.Series):
        return data.apply(lambda x: x.item() if isinstance(x, (np.int64, np.float64)) else x).to_dict()
    elif isinstance(data, pd.DataFrame):
        return data.applymap(lambda x: x.item() if isinstance(x, (np.int64, np.float64)) else x).to_dict(orient='records')
    elif isinstance(data, (np.int64, np.float64)):
        return data.item()
    elif isinstance(data, (list, dict)):
        return json.loads(json.dumps(data, default=str))  # Serialize and then deserialize to convert NumPy types
    return data

def get_additional_info(sifra):
    row = df[df['Šifra'] == sifra]
    if not row.empty:
        row = row.iloc[0]
        info = {
            "Tip brojila": row['Tip'],
            "Godina proizvodnje": format_date(row['Proizvodnj']),
            "Godina baždarenja": format_date(row['Baždarenje']),
            "Datum montaže": format_date(row['Datum žc']),
            "Serijski broj brojila": row['Serijski'],
            "Kupac": row['Kupac'],
            "Adresa": row['Adresa'],
            "Šifra mjernog mjesta": row['Šifra'],
            "Tarifna grupa": row['T'],
            "Angažovana snaga": row['A.sn'],
            "Naziv trafostanice": row['Naziv TS']
        }
        
        # Replace NaN with None (to convert to null in JSON)
        info = {key: (None if pd.isna(value) else value) for key, value in info.items()}
        
        return convert_to_native_types(info)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_coordinates_by_sifra', methods=['POST'])
def get_coordinates_by_sifra():
    sifra = request.form.get('sifra')
    app.logger.debug(f"Received SIFRA: {sifra}")
    if sifra:
        if sifra.isdigit():
            try:
                sifra = int(sifra)
                app.logger.debug(f"Converted SIFRA to int: {sifra}")
                coordinates = find_coordinates_by_sifra(sifra, sifra_to_coordinates)
                additional_info = get_additional_info(sifra)
                app.logger.debug(f"Coordinates found: {coordinates}")
                app.logger.debug(f"Additional info: {additional_info}")
                if coordinates and additional_info:
                    url = create_google_maps_url(coordinates)
                    return jsonify({"url": url, "additional_info": additional_info})
                return jsonify({"error": "Šifra mjernog mjesta nije pronađena u bazi podataka."}), 404
            except ValueError:
                return jsonify({"error": "Invalid SIFRA format."}), 400
        else:
            return jsonify({"error": "Uneseni podatak nije tipa integer (mora sadržavati samo brojeve)."}), 400
    return jsonify({"error": "Šifra nije pronašena, provjerite tačnost unesenih podataka."}), 404

@app.route('/get_coordinates_by_serijski_broj', methods=['POST'])
def get_coordinates_by_serijski_broj():
    serijski_broj = request.form.get('serijski_broj')
    app.logger.debug(f"Received SERIJSKI_BROJ: {serijski_broj}")
    if serijski_broj:
        if serijski_broj.isdigit():
            serijski_broj = int(serijski_broj)
            app.logger.debug(f"Converted SERIJSKI_BROJ to int: {serijski_broj}")
            sifra = find_sifra_by_serijski_broj(serijski_broj, serijski_broj_to_sifra)
            app.logger.debug(f"Found SIFRA: {sifra}")
            if sifra:
                coordinates = find_coordinates_by_sifra(sifra, sifra_to_coordinates)
                additional_info = get_additional_info(sifra)
                app.logger.debug(f"Coordinates found: {coordinates}")
                app.logger.debug(f"Additional info: {additional_info}")
                if coordinates and additional_info:
                    url = create_google_maps_url(coordinates)
                    return jsonify({"url": url, "additional_info": additional_info})
                return jsonify({"error": "Šifra mjernog mjesta nije pronađena u bazi podataka."}), 404
            return jsonify({"error": "Serijski broj nije pronađen u bazi podataka."}), 404
        else:
            return jsonify({"error": "Uneseni podatak nije tipa integer (mora sadržavati samo brojeve)."}), 400
    return jsonify({"error": "Serijski broj nije pronađen, provjerite tačnost unesenih podataka."}), 404

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, request, jsonify, render_template
import json
import pandas as pd
import logging

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

# Filtering out duplicate values added by report
df = df[~(df.duplicated(subset='Šifra') & df['Naziv TS'].isnull())]

# Ensure 'Serijski' and 'Šifra' are integers
df['Serijski'] = df['Serijski'].astype(int)
df['Šifra'] = df['Šifra'].astype(int)

# Remove duplicates
df = df.drop_duplicates(subset=['Serijski', 'Šifra'])

# Map 'Serijski' to 'Šifra' based on the Excel file
serijski_broj_to_sifra = dict(zip(df['Serijski'], df['Šifra']))

def find_coordinates_by_sifra(sifra, sifra_to_coordinates):
    return sifra_to_coordinates.get(sifra, None)

def find_sifra_by_serijski_broj(serijski_broj, serijski_broj_to_sifra):
    return serijski_broj_to_sifra.get(serijski_broj, None)

def create_google_maps_url(coordinates):
    lon, lat = coordinates  # Reverse the order if needed
    return f"https://www.google.com/maps?q={lat},{lon}"

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
                coordinates = find_coordinates_by_sifra(int(sifra), sifra_to_coordinates)
                if coordinates:
                    url = create_google_maps_url(coordinates)
                    return jsonify({"url": url})
                return jsonify({"error": "Šifra mjernog mjesta nije pronađena u bazi podataka. Provjeriti sa Odjeljenjem za priključenja da li je mjerno mjesto ucrtano."}), 404
            except ValueError:
                return jsonify({"error": "Invalid SIFRA format."}), 400
        else:
            return jsonify({"error": "Uneseni podatak nije tipa integer (mora sadržavati samo brojeve)."}), 400
    return jsonify({"error": "SIFRA not found."}), 404

@app.route('/get_coordinates_by_serijski_broj', methods=['POST'])
def get_coordinates_by_serijski_broj():
    serijski_broj = request.form.get('serijski_broj')
    app.logger.debug(f"Received SERIJSKI_BROJ: {serijski_broj}")
    if serijski_broj:
        if serijski_broj.isdigit():
            serijski_broj = int(serijski_broj)
            sifra = find_sifra_by_serijski_broj(serijski_broj, serijski_broj_to_sifra)
            app.logger.debug(f"SIFRA for SERIJSKI_BROJ {serijski_broj}: {sifra}")
            if sifra:
                coordinates = find_coordinates_by_sifra(sifra, sifra_to_coordinates)
                if coordinates:
                    url = create_google_maps_url(coordinates)
                    return jsonify({"url": url})
                return jsonify({"error": "Šifra mjernog mjesta nije pronađena u bazi podataka. Provjeriti sa Odjeljenjem za priključenja da li je mjerno mjesto ucrtano."}), 404
            return jsonify({"error": "Serijski broj nije pronađen u bazi podataka. Provjeriti sa Odjeljenjem za priključenja da li je mjerno mjesto ucrtano, te da li je izvršena zamjena brojila."}), 404
        else:
            return jsonify({"error": "Uneseni podatak nije tipa integer (mora sadržavati samo brojeve)."}), 400
    return jsonify({"error": "SERIJSKI_BROJ not found."}), 404

if __name__ == '__main__':
    app.run(debug=True)

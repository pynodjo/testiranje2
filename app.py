from flask import Flask, request, jsonify, render_template
import json
import pandas as pd
import numpy as np  # Import numpy
import logging
from datetime import datetime
import re  # Add this import for regex
import folium
import atexit


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

# New mapping for customer search
kupac_to_info = df.groupby('Kupac').apply(lambda x: x[['Serijski', 'Adresa', 'Šifra']].to_dict('records')).reset_index(name='info').set_index('Kupac')['info'].to_dict()

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
                if additional_info:
                    result = {"additional_info": additional_info}
                    if coordinates:
                        url = create_google_maps_url(coordinates)
                        result["url"] = url
                    else:
                        result["message"] = "Lokacija nije dostupna."
                    return jsonify(result)
                return jsonify({"error": "Šifra mjernog mjesta nije pronađena u bazi podataka."}), 404
            except ValueError:
                return jsonify({"error": "Invalid SIFRA format."}), 400
        else:
            return jsonify({"error": "Uneseni podatak nije tipa integer (mora sadržavati samo brojeve)."}), 400
    return jsonify({"error": "Šifra nije pronađena, provjerite tačnost unesenih podataka."}), 404

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
                if additional_info:
                    result = {"additional_info": additional_info}
                    if coordinates:
                        url = create_google_maps_url(coordinates)
                        result["url"] = url
                    else:
                        result["message"] = "Lokacija nije dostupna."
                    return jsonify(result)
                return jsonify({"error": "Šifra mjernog mjesta nije pronađena u bazi podataka."}), 404
            return jsonify({"error": "Serijski broj nije pronađen u bazi podataka."}), 404
        else:
            return jsonify({"error": "Uneseni podatak nije tipa integer (mora sadržavati samo brojeve)."}), 400
    return jsonify({"error": "Serijski broj nije pronađen, provjerite tačnost unesenih podataka."}), 404

# New routes for customer search
@app.route('/get_customer_suggestions', methods=['POST'])
def get_customer_suggestions():
    kupac_input = request.form.get('kupac', '').lower()
    if len(kupac_input) >= 3:
        pattern = re.compile(f'.*{re.escape(kupac_input)}.*', re.IGNORECASE)
        matches = []
        for kupac, info in kupac_to_info.items():
            if pattern.match(kupac):
                for record in info:  # Loop through all records for the customer
                    matches.append({
                        'kupac': kupac,
                        'serijski': record['Serijski'],
                        'adresa': record['Adresa']
                    })
        return jsonify(matches[:10])  # Limit to 10 suggestions
    return jsonify([])





@app.route('/get_coordinates_by_kupac', methods=['POST'])
def get_coordinates_by_kupac():
    kupac_input = request.form.get('kupac')
    serijski_input = request.form.get('serijski')

    # Validate input
    if kupac_input in kupac_to_info and serijski_input:
        # Convert serijski input to an integer
        serijski = int(serijski_input)

        # Look up the corresponding SIFRA
        sifra = find_sifra_by_serijski_broj(serijski, serijski_broj_to_sifra)

        if sifra:
            coordinates = find_coordinates_by_sifra(sifra, sifra_to_coordinates)
            additional_info = get_additional_info(sifra)
            
            result = {"additional_info": additional_info}
            if coordinates:
                url = create_google_maps_url(coordinates)
                result["url"] = url
            else:
                result["message"] = "Lokacija nije dostupna."
            return jsonify(result)

    return jsonify({"error": "Kupac ili serijski broj nije pronađen u bazi podataka."}), 404


@app.route('/get_oh_values_by_oj/<oj_value>', methods=['GET'])
def get_oh_values_by_oj(oj_value):
    print(f"get_oh_values_by_oj called with oj_value: {oj_value}")
    
    try:
        if oj_value == "303":
            filtered_df = df[df['OJ'].isin([3031, 3032])]
        else:
            filtered_df = df[df['OJ'] == int(oj_value)]
        
        # Sort the filtered DataFrame by 'OH' in ascending order
        filtered_df = filtered_df.sort_values(by='OH')

        # Extract unique OH values after sorting
        unique_oh_values = filtered_df['OH'].unique().tolist()
        return jsonify(unique_oh_values)
    except Exception as e:
        print(f"Error in get_oh_values_by_oj: {str(e)}")
        return jsonify([]), 500


@app.route('/search_by_oj_oh', methods=['GET'])
def search_by_oj_oh():
    oj_value = request.args.get('oj')
    oh_value = request.args.get('oh')
    
    print(f"search_by_oj_oh called with oj_value: {oj_value}, oh_value: {oh_value}")

    try:
        if oj_value == "303":
            filtered_df = df[(df['OJ'].isin([3031, 3032])) & (df['OH'] == oh_value)]
        else:
            filtered_df = df[(df['OJ'] == int(oj_value)) & (df['OH'] == oh_value)]

        print(f"Filtered DataFrame shape: {filtered_df.shape}")

        folium_map = folium.Map(location=[43.343, 17.807], zoom_start=12)

        for index, row in filtered_df.iterrows():
            sifra = row['Šifra']
            
            coordinates = None
            for feature in data['features']:
                if feature['properties']['SIFRA'] == sifra:
                    coordinates = feature['geometry']['coordinates']
                    break
            
            if coordinates:
                lon, lat = coordinates  # Note that coordinates are [longitude, latitude]
                
                # Prepare popup content
                popup_content = (
                    f"Kupac: <strong>{row['Kupac']}</strong><br>"
                    f"Adresa: <strong>{row['Adresa']}</strong><br>"
                    f"Šifra mjernog mjesta: <strong>{sifra}</strong><br>"
                    f"Serijski broj brojila: <strong>{row['Serijski']}</strong><br>"
                    f"Tip brojila: <strong>{row['Tip']}</strong><br>"
                    f"ROH: <strong>{row['ROH']}</strong>"  # Add ROH here
                )
                
                folium.Marker(
                    [lat, lon],
                    popup=popup_content
                ).add_to(folium_map)
            else:
                print(f"No coordinates found for Šifra: {sifra}")

        map_html = folium_map._repr_html_()
        return map_html

    except Exception as e:
        print(f"Error in search_by_oj_oh: {str(e)}")
        return f"An error occurred: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True)
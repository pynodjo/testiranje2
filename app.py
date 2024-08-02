#!/usr/bin/env python
# coding: utf-8

from flask import Flask, request, jsonify, render_template
import json

app = Flask(__name__)

# Load the JSON file
with open('data.json', 'r') as file:
    data = json.load(file)

# Create dictionaries for quick lookup
sifra_to_coordinates = {feature['properties']['SIFRA']: feature['geometry']['coordinates']
                        for feature in data['features']}
serijski_broj_to_coordinates = {feature['properties']['SERIJSKI_BROJ']: feature['geometry']['coordinates']
                                for feature in data['features']}

def find_coordinates_by_sifra(sifra, sifra_to_coordinates):
    return sifra_to_coordinates.get(sifra, None)

def find_coordinates_by_serijski_broj(serijski_broj, serijski_broj_to_coordinates):
    return serijski_broj_to_coordinates.get(serijski_broj, None)

def create_google_maps_url(coordinates):
    lon, lat = coordinates  # Reverse the order if needed
    return f"https://www.google.com/maps?q={lat},{lon}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_coordinates_by_sifra', methods=['POST'])
def get_coordinates_by_sifra():
    sifra = request.form.get('sifra')
    if sifra:
        coordinates = find_coordinates_by_sifra(int(sifra), sifra_to_coordinates)
        if coordinates:
            url = create_google_maps_url(coordinates)
            return jsonify({"url": url})
    return jsonify({"error": "SIFRA not found."}), 404

@app.route('/get_coordinates_by_serijski_broj', methods=['POST'])
def get_coordinates_by_serijski_broj():
    serijski_broj = request.form.get('serijski_broj')
    if serijski_broj:
        coordinates = find_coordinates_by_serijski_broj(serijski_broj, serijski_broj_to_coordinates)
        if coordinates:
            url = create_google_maps_url(coordinates)
            return jsonify({"url": url})
    return jsonify({"error": "SERIJSKI_BROJ not found."}), 404

if __name__ == '__main__':
    app.run(debug=True)

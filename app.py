from flask import Flask, render_template, flash, request
import requests
import datetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

app = Flask(__name__)
uri = os.environ.get('uri')
cluster = MongoClient(uri, server_api=ServerApi('1'))
db = cluster["PythonPump"]
collection = db["Busy"]

@app.route("/", methods=["POST", "GET"])
def home():
    return render_template('home.html')


@app.route("/enter_data/<id>/<brand>/<address>", methods=["POST", "GET"])
def enter_data(id, brand, address):
    if request.method == 'POST':
        name = brand
        id_station = id
        location = request.form["location"]
        busy_select = request.form["select"]
        price = request.form["price"]
        date_and_time = datetime.datetime.now()
        match busy_select:
            case "Buzzing Bliss":
                busy = 1
            case "Gentle Gliding":
                busy = 2
            case "Humming Harmony":
                busy = 3
            case "Busy Beehive":
                busy = 4
            case "Swarming Storm":
                busy = 5
            case _:
                busy = ""
        busy_list = [(busy, date_and_time)] if busy else []
        price_list = [(price, date_and_time)] if price else []
        if id == 'M':
            radius_km = 0.1
            limit = 1
            origin_coordinates = address_to_coordinates(location)
            station = stations_search(origin_coordinates, radius_km, limit)
            station_data = station.json()['features']
            for suggestion in station_data:
                station_info = suggestion["properties"]
                id_station, name, location = station_info["mapbox_id"], station_info['name'], station_info['full_address']
            if id_station == 'M':
                message = f"A Gas Station does not exist at address: {location}"
                flash(message)
                return render_template('enter_data.html', id=id, brand=brand, address=address)
        if (not collection.find_one({"_id": id_station})):
            post = {"_id": id_station, "brand": name,"address": location, "busy_status": [], "price": []}
            collection.insert_one(post)
        if busy:
            collection.update_one({"_id": id_station}, {"$push": {"busy_status": busy_list}})
        if price:
            collection.update_one({"_id": id_station}, {"$push": {"price": price_list}})
    return render_template('enter_data.html', id=id, brand=brand, address=address)


@app.route("/display_data", methods=["POST", "GET"])
def display_data():
    limit = 5
    radius_km = 5
    location = request.form["name"]
    origin_coordinates = address_to_coordinates(location)
    info_station = stations_search(origin_coordinates, radius_km, limit)
    data = info_station.json()['features']
    stations = []
    for suggestion in data:
        info = suggestion["properties"]
        brand_id, brand_name, address = info['mapbox_id'], info['name'], info['full_address']
        cost, total_busy_score, total_weight = 0, 0, 0
        busy_list, cost_list = [], []
        stations_found = collection.find_one({"_id": brand_id})
        if (stations_found):
            station_price_list = stations_found['price']
            station_busy_list = stations_found['busy_status']
            date_now = datetime.datetime.now()
            for score in station_busy_list or []:
                time = score[0][1]
                difference = (date_now - time).total_seconds()
                entry_sum = 0
                if (difference < 960):
                    scone = score[0][0]
                    busy_list.insert(0, (round((difference/60), 0), scone))
                    weight = pow(0.5, (difference/480))
                    entry_sum += weight * scone
                    total_weight += weight
                    total_busy_score += entry_sum
            for price in station_price_list:
                time = price[0][1]
                difference = (date_now - time).total_seconds()
                if (difference < 900):
                    cost = station_price_list[len(station_price_list)-1][0][0]
                    price_entry = price[0][0]
                    cost_list.insert(0, (round((difference/60), 0), price_entry))
        total_busy_score = round(total_busy_score/total_weight, 1) if total_weight > 0 else total_busy_score
        temp = (brand_name, address, cost, total_busy_score, brand_id, busy_list, cost_list)
        stations.append(temp)
    return render_template("display_data.html", station=stations)
    # return stations


def replace_space_with_dash(string):
    loc = string.replace(',', '')
    return '+'.join(loc.split())


def address_to_coordinates(location):
    loc = replace_space_with_dash(location)
    url = "https://geocode.maps.co/search"
    key = os.getenv('geocode_key')
    params_address = {
        "q": loc,
        "api_key": key
    }

    response = requests.get(url, params=params_address)

    lat = response.json()[0]['lat']
    lon = response.json()[0]['lon']

    return f"{lon},{lat}"


def stations_search(coordinates, radius_km, limit):
    places = "https://api.mapbox.com/search/searchbox/v1/category/gas_station?"
    key_place = os.getenv('key_place')
    bbox = calculate_bbox(coordinates, radius_km)
    params_place = {
        "language": "en",
        "bbox": bbox,
        "limit": limit,
        "proximity": coordinates,
        "access_token": key_place
    }
    response = requests.get(places, params=params_place)
    return response


def calculate_bbox(center, radius):
    longitude, latitude = map(float, center.split(','))
    degrees_to_km = 111
    delta_latitude = (radius / degrees_to_km)
    delta_longitude = (radius / degrees_to_km)
    min_longitude = longitude - delta_longitude
    min_latitude = latitude - delta_latitude
    max_longitude = longitude + delta_longitude
    max_latitude = latitude + delta_latitude
    return f"{min_longitude},{min_latitude},{max_longitude},{max_latitude}"


if __name__ == "__main__":
    app.run(debug=True)

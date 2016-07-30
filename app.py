from flask import Flask, render_template, jsonify, make_response, request
import time
import json
import pymongo
import os
import re
import traceback
import requests
import subprocess
from operator import itemgetter

POINT_INTERVAL = 60 * 10
DAYS_RANGE = 7


class Mongo:
    instance = None
    conn = None
    cursor = None

    def __init__(self):
        self.conn = pymongo.MongoClient("127.0.0.1", 27017).mySensor

    @staticmethod
    def get():
        if Mongo.instance is None:
            Mongo.instance = Mongo()

        return Mongo.instance.conn


def room_sensor():
    return json.loads(requests.get('http://10.0.0.11/room').text)


def pi_sensor():
    return json.loads(requests.get('http://10.0.0.11/sensor').text)


def route_sensor():
    with subprocess.Popen(
            'ssh -i ~/.ssh/route.600.key admin@10.0.0.1 "cat /proc/dmu/temperature;echo \'eth1 :\';wl -i eth1 phy_tempsense 2>/dev/null;echo \'eth2 :\';wl -i eth2 phy_tempsense 2>/dev/null"',
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as f:
        res = str(f.stdout.read(), 'gbk')

        route_pattern = r'CPU\s{1}temperature\s{1}:\s{1}(\d+\.?\d*)[^e]*(eth1)[^\d]*(\d*)[^\n]*\n{1}(eth2)[^\d]*(\d*)'
        route_re = re.compile(route_pattern)

        route_res = route_re.findall(res)

        data = {
            'CPU': route_res[0][0],
            route_res[0][1]: int(route_res[0][2] if route_res[0][2] else 0),
            route_res[0][3]: int(route_res[0][4] if route_res[0][4] else 0),
        }

        return data


def nas_sensor():
    data = {}
    with os.popen('sensors;free -m;w') as f:
        res = f.read()

        # CPU
        cpu_pattern = r'Core\s\d:\s+\+(\d+\.?\d*)'
        cpu_re = re.compile(cpu_pattern)
        cpu = [float(l) for l in cpu_re.findall(res)]
        data.setdefault('CPU', round(sum(cpu) / len(cpu), 2))
        index = 0
        for i in cpu:
            data.setdefault('Core' + str(index), float(i))
            index += 1

    return data


def dht_one_sensor():
    return dht_sensor('one')


def dht_two_sensor():
    return dht_sensor('two')


def dht_three_sensor():
    return dht_sensor('three')


def dht_sensor(chip):
    res = '{}'
    try:
        with open('/dev/shm/sensor.' + chip + '.log', 'r') as f:
            res = f.read()
    except:
        pass

    return json.loads(res)


app = Flask(__name__)


def get_temperatures(device):
    res = Mongo.get()[device].find({}, {'CPU': 1, 'add_time': 1, '_id': 0}).sort('_id', -1).limit(6)
    res = list(res)[::-1]
    return json.dumps(res)


@app.route('/pi/temperatures')
def pi_temperatures():
    return get_temperatures('pi')


@app.route('/nas/temperatures')
def nas_temperatures():
    return get_temperatures('nas')


@app.route('/route/temperatures')
def route_temperatures():
    return get_temperatures('route')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sensor.json')
def sensor_json():
    global POINT_INTERVAL, DAYS_RANGE
    temperature_data = {
        'temperature_one': {
            'name': 'temperature_one',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'temperature',
            'color': '#FF9933',
            'order': 1000,
        },
        'humidity_one': {
            'name': 'humidity_one',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'humidity',
            'color': '#0099ff',
            'order': 2000,
        },
        'nas': {
            'name': 'nas',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'CPU',
            'color': '#FF9933',
            'order': 3000,
        },
        'pi': {
            'name': 'pi',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'CPU',
            'color': '#FF9933',
            'order': 4000,
        },
        'route': {
            'name': 'route',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'CPU',
            'color': '#FF9933',
            'order': 5000,
        },
        'temperature_two': {
            'name': 'temperature_two',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'temperature',
            'color': '#FF9933',
            'order': 6000,
        },
        'humidity_two': {
            'name': 'humidity_two',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'humidity',
            'color': '#0099ff',
            'order': 7000,
        },
        'temperature_three': {
            'name': 'temperature_three',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'temperature',
            'color': '#FF9933',
            'order': 8000,
        },
        'humidity_three': {
            'name': 'humidity_three',
            'point_start': None,
            'point_interval': POINT_INTERVAL,
            'index': 'humidity',
            'color': '#0099ff',
            'order': 9000,
        },
    }

    def inner_loop(doc, device, data_key='CPU'):
        start_time = time.time()
        last_add_time = 0
        device_res = Mongo.get()[doc].find({}, {data_key: 1, 'add_time': 1}).sort('_id', -1).limit(
            int(DAYS_RANGE * 86400 / POINT_INTERVAL))
        device_res = list(device_res)[::-1]
        for v in device_res:
            temperature_data[device].setdefault(data_key, [])

            if not temperature_data[device]['point_start']:
                temperature_data[device]['point_start'] = v['add_time']
                last_add_time = v['add_time']
                temperature_data[device][data_key].append(float(v[data_key]))

            while last_add_time < v['add_time']:
                temperature_data[device][data_key].append(float(v[data_key]))
                last_add_time += POINT_INTERVAL

        print(round((time.time() - start_time) * 1000, 3), 'ms when get data')

    inner_loop('dht_one', 'temperature_one', 'temperature')
    inner_loop('dht_one', 'humidity_one', 'humidity')
    inner_loop('nas', 'nas')
    inner_loop('pi', 'pi')
    inner_loop('route', 'route')
    inner_loop('dht_two', 'temperature_two', 'temperature')
    inner_loop('dht_two', 'humidity_two', 'humidity')
    inner_loop('dht_three', 'temperature_three', 'temperature')
    inner_loop('dht_three', 'humidity_three', 'humidity')

    sorted_data = sorted([v for k, v in temperature_data.items()], key=itemgetter('order'))  # Sorted by order
    return jsonify(data=sorted_data)


@app.route('/room')
def room():
    return jsonify(room_sensor())


@app.route('/pi')
def pi():
    return jsonify(pi_sensor())


@app.route('/route')
def route():
    return jsonify(route_sensor())


@app.route('/nas')
def nas():
    return jsonify(nas_sensor())


@app.route('/dht/one')
def dht_one():
    return jsonify(dht_sensor('one'))


@app.route('/dht/two')
def dht_two():
    return jsonify(dht_sensor('two'))


@app.route('/dht/three')
def dht_three():
    return jsonify(dht_sensor('three'))


@app.route('/sensor/upload', methods=('POST',))
def sensor_upload():
    try:
        json_obj = json.loads(request.get_data().decode("utf-8"))
        file_path = '/dev/shm/sensor.' + json_obj['chip'] + '.log'
        with open(file_path, 'w') as f:
            json_obj['add_time'] = int(os.stat(file_path).st_mtime)
            f.write(json.dumps(json_obj))
    except:
        pass

    return ""


@app.route('/loop')
def get_sensor_data_loop():
    def inner_loop(device, sensor_fun):
        try:
            data = sensor_fun()
            if not data:
                return

            if 'add_time' not in data:
                data['add_time'] = int(time.time())

            Mongo.get()[device].insert(data)
        except:
            traceback.print_exc()
            pass

    inner_loop('nas', nas_sensor)
    inner_loop('route', route_sensor)
    inner_loop('pi', pi_sensor)
    # inner_loop('room', room_sensor)
    inner_loop('dht_one', dht_one_sensor)
    inner_loop('dht_two', dht_two_sensor)
    inner_loop('dht_three', dht_three_sensor)

    return make_response('success')

# app.run(host='0.0.0.0', debug=True, port=92)

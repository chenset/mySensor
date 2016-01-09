from flask import Flask, render_template, jsonify, make_response
import time
import json
import pymongo
import os
import re
import urllib2

POINT_INTERVAL = 60 * 10
DAYS_RANGE = 30


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


def pi_sensor():
    return json.loads(urllib2.urlopen('http://10.0.0.11/sensor').read())


def route_sensor():
    with os.popen(
            'ssh -i ~/.ssh/route.ssl admin@10.0.0.1 "cat /proc/dmu/temperature;echo \'eth1 :\';wl -i eth1 phy_tempsense 2>/dev/null;echo \'eth2 :\';wl -i eth2 phy_tempsense 2>/dev/null"') as f:
        res = f.read()

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

        # SYS
        sys_pattern = r'(SYSTIN|CPUTIN|AUXTIN):\s+\+(\d+\.?\d*)'
        sys_re = re.compile(sys_pattern)
        for (k, v) in sys_re.findall(res):
            data.setdefault(k, float(v))
        #
        # # HDD
        # hdd_pattern = r'(/dev/sd\w{1}):[^:]+:\s+(\d+\.?\d*)'
        # hdd_re = re.compile(hdd_pattern)
        # for (k, v) in hdd_re.findall(res):
        #     data.setdefault(k, float(v))

        # RAM
        ram_pattern = r'Mem:\s+(\d+)\s+(\d+)\s+(\d+)[\s\S]+buffers/cache:\s+(\d+)\s+(\d+)'
        ram_re = re.compile(ram_pattern)
        ram_res = list(ram_re.findall(res)[0])
        data.setdefault('RAM real free', int(ram_res.pop()))
        data.setdefault('RAM real used', int(ram_res.pop()))
        data.setdefault('RAM free', int(ram_res.pop()))
        data.setdefault('RAM used', int(ram_res.pop()))
        data.setdefault('RAM total', int(ram_res.pop()))

        # load
        load_pattern = r'load\s{1}average:\s{1}(\d+\.?\d*),\s{1}(\d+\.?\d*),\s{1}(\d+\.?\d*)'
        load_re = re.compile(load_pattern)
        load_res = list(load_re.findall(res)[0])
        data.setdefault('Load 15 min', float(load_res.pop()))
        data.setdefault('Load 5 min', float(load_res.pop()))
        data.setdefault('Load 1 min', float(load_res.pop()))

        # users
        other_pattern = r'\s+(\d+)\s{1}users,'
        other_re = re.compile(other_pattern)
        for i in other_re.findall(res):
            data.setdefault('users', int(i))

    # runtime
    with open('/proc/uptime', 'r') as f:
        data.setdefault('runtime', int(float(f.read().split(' ')[0])))
        # print request

    return data


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
    global POINT_INTERVAL, DAYS_RANGE
    temperature_data = {
        'nas': {
            'point_start': None,
            'point_interval': POINT_INTERVAL,
        },
        'pi': {
            'point_start': None,
            'point_interval': POINT_INTERVAL,
        },
        'route': {
            'point_start': None,
            'point_interval': POINT_INTERVAL,
        },
    }

    def inner_loop(device):
        start_time = time.time()
        last_add_time = 0
        device_res = Mongo.get()[device].find({}, {'CPU': 1, 'add_time': 1}).sort('_id', -1).limit(
            int(DAYS_RANGE * 86400 / POINT_INTERVAL))
        device_res = list(device_res)[::-1]
        for v in device_res:
            temperature_data[device].setdefault('CPU', [])

            if not temperature_data[device]['point_start']:
                temperature_data[device]['point_start'] = v['add_time']
                last_add_time = v['add_time']
                temperature_data[device]['CPU'].append(float(v['CPU']))

            while last_add_time < v['add_time']:
                temperature_data[device]['CPU'].append(float(v['CPU']))
                last_add_time += POINT_INTERVAL

        print round((time.time() - start_time) * 1000, 3), 'ms when get data'

    inner_loop('nas')
    inner_loop('pi')
    inner_loop('route')

    return render_template('index.html', temperature_data=json.dumps(temperature_data))


@app.route('/pi')
def pi():
    return jsonify(pi_sensor())


@app.route('/route')
def route():
    return jsonify(route_sensor())


@app.route('/nas')
def nas():
    return jsonify(nas_sensor())


@app.route('/loop')
def get_sensor_data_loop():

    def inner_loop(device, sensor_fun):
        try:
            data = sensor_fun()
            if 'add_time' not in data:
                data['add_time'] = int(time.time())

            Mongo.get()[device].insert(data)
        except:
            pass

    inner_loop('nas', nas_sensor)
    inner_loop('route', route_sensor)
    inner_loop('pi', pi_sensor)

    return make_response('success')

# app.run(host='0.0.0.0', debug=True, port=922)

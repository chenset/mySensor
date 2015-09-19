from flask import Flask, render_template, jsonify, make_response, request
from threading import Timer
import time
import json
import pymongo
import os
import re
import urllib2

POINT_INTERVAL = 30


class Scheduler(object):
    def __init__(self, sleep_time, function):
        self.sleep_time = sleep_time
        self.function = function
        self._t = None

    def start(self):
        if self._t is None:
            self._t = Timer(self.sleep_time, self._run)
            self._t.start()
        else:
            raise Exception("this timer is already running")

    def _run(self):
        self.function()
        self._t = Timer(self.sleep_time, self._run)
        self._t.start()

    def stop(self):
        if self._t is not None:
            self._t.cancel()
            self._t = None


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


app = Flask(__name__)


@app.route('/')
def index():
    global POINT_INTERVAL
    temperature_data = {
        'NAS': {
            'point_start': None,
            'point_interval': POINT_INTERVAL,
        },
        # 'R7000': {'cpu': [], 'eth1': [], 'eth2': []},
        # 'RaspberryPi2': {'cpu': []},
        # 'date': [],
    }
    start_time = time.time()

    for v in Mongo.get().sensor.find():
        if not temperature_data['NAS']['point_start']:
            temperature_data['NAS']['point_start'] = v['add_time']

        temperature_data['NAS'].setdefault('CPU', [])
        temperature_data['NAS']['CPU'].append(v['CPU'])

    print round((time.time() - start_time) * 1000, 3), 'ms when get data'



    # for doc in Mongo.get().temperatrue.find().limit(48).sort('_id', -1):
    # temperature_data['R7000']['cpu'].append(doc['R7000']['temperature']['cpu'] or None)
    # temperature_data['R7000']['eth1'].append(doc['R7000']['temperature']['eth1'] or None)
    # temperature_data['R7000']['eth2'].append(doc['R7000']['temperature']['eth2'] or None)
    # temperature_data['RaspberryPi2']['cpu'].append(float(doc['RaspberryPi2']['temperature']['cpu']) or None)
    # temperature_data['date'].append(time.strftime('%H:%M', time.localtime(int(doc['add_time']))) or '-')
    #
    # temperature_data['R7000']['cpu'] = temperature_data['R7000']['cpu'][::-1]
    # temperature_data['R7000']['eth1'] = temperature_data['R7000']['eth1'][::-1]
    # temperature_data['R7000']['eth2'] = temperature_data['R7000']['eth2'][::-1]
    # temperature_data['RaspberryPi2']['cpu'] = temperature_data['RaspberryPi2']['cpu'][::-1]
    # temperature_data['date'] = temperature_data['date'][::-1]

    return render_template('index.html', temperature_data=json.dumps(temperature_data))


@app.route('/pi')
def pi():
    # with os.popen('ssh -i ~/.ssh/pi.ssl 10.0.0.10 "w"') as f:
    data = urllib2.urlopen('http://10.0.0.10/sensor').read()
    return make_response('<pre>' + data + '</pre>')


@app.route('/nas')
def nas():
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

    try:
        return jsonify(data)
    except:
        return data

        # return make_response('<pre>' + res + '</pre><br/>' + json.dumps(data))


def get_sensor_data_loop():
    nas_data = nas()
    if 'add_time' not in nas_data:
        nas_data['add_time'] = int(time.time())

    Mongo.get().sensor.insert(nas_data)


# scheduler = Scheduler(POINT_INTERVAL, get_sensor_data_loop)
# scheduler.start()
app.run(host='0.0.0.0', debug=True, port=88)
# scheduler.stop()

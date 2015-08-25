from flask import Flask, render_template
from threading import Timer
import urllib2
import time
import json
import pymongo


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
    temperature_data = {
        'R7000': {'cpu': [], 'eth1': [], 'eth2': []},
        'RaspberryPi2': {'cpu': []},
        'date': [],
    }

    for doc in Mongo.get().temperatrue.find().limit(48).sort('_id', -1):
        temperature_data['R7000']['cpu'].append(doc['R7000']['temperature']['cpu'] or None)
        temperature_data['R7000']['eth1'].append(doc['R7000']['temperature']['eth1'] or None)
        temperature_data['R7000']['eth2'].append(doc['R7000']['temperature']['eth2'] or None)
        temperature_data['RaspberryPi2']['cpu'].append(float(doc['RaspberryPi2']['temperature']['cpu']) or None)
        temperature_data['date'].append(time.strftime('%H:%M', time.localtime(int(doc['add_time']))) or '-')

    temperature_data['R7000']['cpu'] = temperature_data['R7000']['cpu'][::-1]
    temperature_data['R7000']['eth1'] = temperature_data['R7000']['eth1'][::-1]
    temperature_data['R7000']['eth2'] = temperature_data['R7000']['eth2'][::-1]
    temperature_data['RaspberryPi2']['cpu'] = temperature_data['RaspberryPi2']['cpu'][::-1]
    temperature_data['date'] = temperature_data['date'][::-1]

    return render_template('index.html', temperature_data=json.dumps(temperature_data))


def get_sensor_data_loop():
    data = {}
    try:
        data = json.loads(urllib2.urlopen('http://127.0.0.1/sensor').read())
    finally:
        if not data:
            return

    if 'add_time' not in data:
        data['add_time'] = int(time.time())

    Mongo.get().temperatrue.insert(data)


scheduler = Scheduler(1800, get_sensor_data_loop)
scheduler.start()
# app.run(host='0.0.0.0', debug=False, port=82)
# scheduler.stop()
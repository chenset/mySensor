from flask import Flask, render_template, jsonify, make_response
import time
import json
import pymongo
import os
import re
import urllib
from operator import itemgetter

# import redis

# r = redis.StrictRedis(host='localhost', port=6379, db=0)

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

res = Mongo.get().nas.find({}, {'CPU': 1, 'add_time': 1}).sort('_id', -1).limit(1)

start_time = time.time()

# res = Mongo.get().nas.find({}, {'CPU': 1, 'add_time': 1, '_id': 0}).sort('_id', -1).limit(600)
res = Mongo.get().nas.find({}, {'CPU': 1, 'add_time': 1}).sort('_id', -1).limit(600)

print(len(list(res)))

# for k in range(450):
#     r.hset('nas','key'+str(k),'value')

# print len(r.hgetall('nas'))


print(round((time.time() - start_time) * 1000))

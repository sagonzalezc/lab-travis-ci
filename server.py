# Copyright 2016 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from redis import Redis
from redis.exceptions import ConnectionError
from flask import Flask, Response, jsonify, request, json, url_for
from pets import Pet

# Status Codes
HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_204_NO_CONTENT = 204
HTTP_400_BAD_REQUEST = 400
HTTP_404_NOT_FOUND = 404
HTTP_409_CONFLICT = 409

# Create Flask application
app = Flask(__name__)

# Pull options from environment
debug = (os.getenv('DEBUG', 'False') == 'True')
port = os.getenv('PORT', '5000')

######################################################################
# GET INDEX
######################################################################
@app.route('/')
def index():
    data = '{name: <string>, category: <string>}'
    url = request.base_url + 'pets' # url_for('list_pets')
    return jsonify(name='Pet Demo REST API Service', version='1.0', url=url, data=data), HTTP_200_OK

######################################################################
# LIST ALL PETS
######################################################################
@app.route('/pets', methods=['GET'])
def list_pets():
    results = []
    category = request.args.get('category')
    for key in redis.keys():
        if key != 'index':  # filer out our id index
            pet = redis.hgetall(key)
            if category: # filer for category
                if pet['category'] == category:
                    results.append(pet)
            else:
                results.append(pet)

    return reply(results, HTTP_200_OK)

######################################################################
# RETRIEVE A PET
######################################################################
@app.route('/pets/<int:id>', methods=['GET'])
def get_pet(id):
    if redis.exists(id):
        message = redis.hgetall(id)
        rc = HTTP_200_OK
    else:
        message = { 'error' : 'Pet %s was not found' % id }
        rc = HTTP_404_NOT_FOUND

    return reply(message, rc)

######################################################################
# ADD A NEW PET
######################################################################
@app.route('/pets', methods=['POST'])
def create_pet():
    # payload = request.get_json()
    payload = json.loads(request.data)
    if Pet.is_valid(payload):
        id = next_index()
        pet = Pet(id, payload['name'], payload['category'])
        redis.hmset(id, pet.to_dict())
        message = redis.hgetall(id)
        rc = HTTP_201_CREATED
    else:
        message = { 'error' : 'Data is not valid' }
        rc = HTTP_400_BAD_REQUEST

    response = Response(json.dumps(message))
    response.headers['Content-Type'] = 'application/json'
    if rc == HTTP_201_CREATED:
        response.headers['Location'] = url_for('get_pet', id=id)
    response.status_code = rc
    return response

######################################################################
# UPDATE AN EXISTING PET
######################################################################
@app.route('/pets/<int:id>', methods=['PUT'])
def update_pet(id):
    payload = json.loads(request.data)
    if Pet.is_valid(payload):
        if redis.exists(id):
            pet = Pet(id, payload['name'], payload['category'])
            redis.hmset(id, pet.to_dict())
            message = redis.hgetall(id)
            rc = HTTP_200_OK
        else:
            message = { 'error' : 'Pet %s was not found' % id }
            rc = HTTP_404_NOT_FOUND
    else:
        message = { 'error' : 'Data is not valid' }
        rc = HTTP_400_BAD_REQUEST

    return reply(message, rc)

######################################################################
# DELETE A PET
######################################################################
@app.route('/pets/<int:id>', methods=['DELETE'])
def delete_pet(id):
    redis.delete(id)
    return '', HTTP_204_NO_CONTENT

######################################################################
#  U T I L I T Y   F U N C T I O N S
######################################################################
def next_index():
    redis.incr('index')
    index = redis.get('index')
    return index

def reply(message, rc):
    response = Response(json.dumps(message))
    response.headers['Content-Type'] = 'application/json'
    response.status_code = rc
    return response

# load sample data
def data_load(payload):
    id = next_index()
    pet = Pet(id, payload['name'], payload['category'])
    redis.hmset(id, pet.to_dict())

def data_reset():
    redis.flushall()

######################################################################
# Connect to Redis and catch connection exceptions
######################################################################
def connect_to_redis(hostname, port, password):
    redis = Redis(host=hostname, port=port, password=password)
    try:
        redis.ping()
    except ConnectionError:
        redis = None
    return redis


######################################################################
# INITIALIZE Redis
# This method will work in the following conditions:
#   1) In Bluemix with Redsi bound through VCAP_SERVICES
#   2) With Redis running on the local server as with Travis CI
#   3) With Redis --link ed in a Docker container called 'redis'
######################################################################
def inititalize_redis():
    global redis
    redis = None
    # Get the crdentials from the Bluemix environment
    if 'VCAP_SERVICES' in os.environ:
        print "Using VCAP_SERVICES..."
        VCAP_SERVICES = os.environ['VCAP_SERVICES']
        services = json.loads(VCAP_SERVICES)
        creds = services['rediscloud'][0]['credentials']
        print "Conecting to Redis on host %s port %s" % (creds['hostname'], creds['port'])
        redis = connect_to_redis(creds['hostname'], creds['port'], creds['password'])
    else:
        print "VCAP_SERVICES not found, checking localhost for Redis"
        redis = connect_to_redis('127.0.0.1', 6379, None)
        if not redis:
            print "No Redis on localhost, pinging: redis"
            response = os.system("ping -c 1 redis")
            if response == 0:
                print "Connecting to remote: redis"
                redis = connect_to_redis('redis', 6379, None)
    if not redis:
        # if you end up here, redis instance is down.
        print '*** FATAL ERROR: Could not connect to the Redis Service'
        exit(1)


######################################################################
#   M A I N
######################################################################
if __name__ == "__main__":
    print "Pet Service Starting..."
    inititalize_redis()
    app.run(host='0.0.0.0', port=int(port), debug=debug)

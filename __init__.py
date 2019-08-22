import datetime
import logging
import requests
import json
import ast
from azure.storage.blob import BlockBlobService

import azure.functions as func


def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function ran at %s', utc_timestamp)


#Define temp threshhold, number is degree x 10
tempthresh = 40

#Define storage account name
storAcct = ''
#Define Access Key
storKey = ''

#API PREP
####################################################################################
#Grab latest Token from token.json in azure blob storage and assign to $auth
blob = BlockBlobService(storAcct, storKey)

tokenblob = blob.get_blob_to_text('ecobee-token', 'token.json')
#convert string to dict
data = ast.literal_eval(tokenblob.content)
auth = data['access_token']


#API Headers
hed = {
    'Authorization': 'Bearer ' + auth,
    }
#API Url
apiUrl = 'https://api.ecobee.com/1/thermostat'


#PROGRAM GET
####################################################################################
#API Query
query = {'json': ('{"selection":{"selectionType":"registered","includeProgram":true}}')}
#assign response to variable
programResp = requests.get(apiUrl, headers=hed, params=query)
#convert to Dict
programDict = json.loads(programResp.content)


#SENSOR GET
####################################################################################
#API Query
query = {'json': ('{"selection":{"selectionType":"registered","includeSensors":true}}')}
#assign response to variable
sensorsResp = requests.get(apiUrl, headers=hed, params=query)
#convert to Dict
sensorsDict = json.loads(sensorsResp.content)


#BEGIN TEMP DIFF CHECK
####################################################################################
#Grab current Temps loop, error checking to prevent getting reads from other possible keys
count = 0
temps={}
while count < 3:
    if sensorsDict['thermostatList'][0]['remoteSensors'][count]['capability'][0]['type'] == 'temperature':
        temps["temp{0}".format(count)] = sensorsDict['thermostatList'][0]['remoteSensors'][count]['capability'][0]['value']
    elif sensorsDict['thermostatList'][0]['remoteSensors'][count]['capability'][0]['type'] == 'humidity':
        temps["temp{0}".format(count)] = sensorsDict['thermostatList'][0]['remoteSensors'][count]['capability'][1]['value']
    elif sensorsDict['thermostatList'][0]['remoteSensors'][count]['capability'][0]['type'] == 'occupancy':
        temps["temp{0}".format(count)] = sensorsDict['thermostatList'][0]['remoteSensors'][count]['capability'][1]['value']
    else:
        print("error")
    count += 1

#Convert to individual variable Integers
temp0 = int(temps['temp0'])
temp1 = int(temps['temp1'])
temp2 = int(temps['temp2'])

#Get temp difs and abs converts to positive number
tempd0 = abs(temp0 - temp1)
tempd1 = abs(temp0 - temp2)
tempd2 = abs(temp1 - temp2)

#logic check
if tempd0 >= tempthresh:
    fan = 1
elif tempd1 >= tempthresh:
    fan = 1
elif tempd2 >= tempthresh:
    fan = 1
else:
    fan = 0


#BEGIN PREPPING RESPONSE AND ASSIGN FAN LOGIC
####################################################################################
#Declare json that will be returned and prepare to edit it
responseBody = programDict['thermostatList'][0]['program']
#Remove sensor Key loop
count=0
while count < 3:
    if responseBody['climates'][count]['sensors']:
        del(responseBody['climates'][count]['sensors'])
    count += 1
#Remove colour Key loop
count=0
while count < 3:
    if responseBody['climates'][count]['colour']:
        del(responseBody['climates'][count]['colour'])
    count += 1
#Remove Current Climate Key
if responseBody['currentClimateRef']:
        del(responseBody['currentClimateRef'])
#Cleanup done, declare fan AUTO/ON
if fan == 1:
    count = 0
    while count < 3:
        responseBody['climates'][count]['coolFan'] = 'on'
        responseBody['climates'][count]['heatFan'] = 'on'
        count += 1
elif fan == 0:
    count = 0
    while count < 3:
        responseBody['climates'][count]['coolFan'] = 'auto'
        responseBody['climates'][count]['heatFan'] = 'auto'
        count += 1
else:
    print("error")
responseBody['climates'][1]['heatFan']
responseBody['climates'][2]['heatFan']
responseBody['climates'][0]['heatFan']

#ADD REQUIRED JSON KEYS FOR RESPONSE
####################################################################################
#Declare required header
append = {"selection": {"selectionType":"registered","selectionMatch":""},"thermostat": {"program": {}}}
#Nest response in required header
append["thermostat"]["program"] = responseBody
#convert to json
jsonReturn = json.dumps(append)


#SEND RESPONSE
####################################################################################
#assign response to variable
programResp = requests.get(apiUrl, headers=hed, params=query)
#convert to Dict
programDict = json.loads(programResp.content)
#Post and save output
postResp = requests.post(apiUrl, headers=hed, data=jsonReturn)
fan = str(fan)
postResp = str(postResp)

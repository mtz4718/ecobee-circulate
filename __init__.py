import logging
import requests
import json
import ast
import datetime
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
storAcct = 'ENTER YOUR OWN'
#Define Access Key
storKey = 'ENTER YOUR OWN'

#API PREP
####################################################################################
#Grab latest Token from token.json in azure blob storage and assign to $auth
blob = BlockBlobService(storAcct, storKey)

tokenblob = blob.get_blob_to_text('ecobee-token', 'token.json')
#convert string to dict
data = ast.literal_eval(tokenblob.content)
refreshauth = data['refresh_token']
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

#Cleanup done, declare fan AUTO/ON and make variable for logs

if fan == 1:
    count = 0
    while count < 3:
        responseBody['climates'][count]['coolFan'] = 'on'
        responseBody['climates'][count]['heatFan'] = 'on'
        fanResp = 'Fan is turned to On'
        count += 1
elif fan == 0:
    count = 0
    while count < 3:
        responseBody['climates'][count]['coolFan'] = 'auto'
        responseBody['climates'][count]['heatFan'] = 'auto'
        fanResp = 'Fan is turned to Auto'
        count += 1
else:
    fanresp = 'ERROR'
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

#CONFIGURE LOGGING
####################################################################################
#Save output and settings in prep for log, use $fanResp from previous logic statements

postResp = str(postResp)
date = datetime.datetime.now()
dateTime = date.strftime("%m-%d-%Y_%H:%M:%S")
logString = dateTime + "   " + fanResp + " :::: The API responded with " + postResp

#Send log string to blob
blob.create_blob_from_text('ecobee-log', 'log-' + dateTime + '.txt', logString)


####################################################################################
#Refresh authentication

#API Headers

#API Url
apiUrl = 'https://api.ecobee.com/token'


#PROGRAM GET
####################################################################################
#API Query

query = 'grant_type=refresh_token&code=' + refreshauth + '&client_id= ENTER YOUR OWN'

#assign response to variable

refreshResp = requests.post(apiUrl, params=query)

#convert to Dict, then to String

refreshDict = json.loads(refreshResp.content)
refreshString = json.dumps(refreshDict)

#Upload new tokens back to azure

blob.create_blob_from_text('ecobee-token','token.json',refreshString)

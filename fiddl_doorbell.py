# fiddl
# author: Drew Bies
# description: this program connects to the google nest doorbell camera through the google cloud services.
#   get_access_token() retrieves the authentication token needed to access the doorbell device.
#   get_rtsp_stream() retrieves a live stream url of the camera feed in rtsp format.
#   pull_messages() pulls all messages in the queue from the doorbell with a timeout
#   callback(message) is called from pull_messages() for every message found. 
#       the message is filtered based on the eventId (person, motion, chime)
#       uses the eventId to call get_image(eventId)
#   get_image(eventId) retrieves the image and saves it to the desired location using the eventId

from flask import Flask, current_app, flash, session
import pyrebase
import requests
import json
import os
from google.cloud import pubsub_v1
import fiddl_utils as fiddl_utils

# ----------------------------------------------------------------------------
# Parse the JSON Payload for an event
# ----------------------------------------------------------------------------
def callback(message):
    current_app.logger.info("[DOORBELL] Looking for messages event")

    print("Payload Type: ", type(message))
    print("Message: ", message)
    # convert message into a python dictionary of the event
    event_json = json.loads(bytes.decode(message))
    print()
    print("event_json: ", event_json)
    event_type = event_json['resourceUpdate']['events']
    print("event_type: ", event_type)
    #event_type = message['resourceUpdate']['events']

    person = 'sdm.devices.events.CameraPerson.Person'
    motion = 'sdm.devices.events.CameraMotion.Motion'
    chime = 'sdm.devices.events.DoorbellChime.Chime'
    sound = 'sdm.devices.events.CameraSound.Sound'
    event = person

    info = []
    print("2")
    # using 'sdm.devices.events.CameraPerson.Person' to get person events only
    if event in event_type:
        print("3.1")
        print(fiddl_utils.bcolors.OKBLUE, "                             Event Type PERSON DETECTED: ", event, fiddl_utils.bcolors.ENDC)

        current_app.logger.info("[DOORBELL] Person event found")
        event_id = event_type[event]['eventId']
        print(fiddl_utils.bcolors.OKGREEN, "                             Event Id: ", event_id, fiddl_utils.bcolors.ENDC)
        info = get_image(event_id) # get the image
        if(info):
            info.append(event_id)
        print("4.1")
    elif chime in event_type:
        print("3.2")
        print(fiddl_utils.bcolors.OKBLUE, "                             Event Type CHIME: ", chime, fiddl_utils.bcolors.ENDC)

        current_app.logger.info("[DOORBELL] Chime event found")
        event_id = event_type[chime]['eventId']
        print(fiddl_utils.bcolors.OKGREEN, "                             Event Id: ", event_id, fiddl_utils.bcolors.ENDC)
        info = get_image(event_id) # get the image
        if(info):
            info.append(event_id)
        print("4.2")
    else:
        print(fiddl_utils.bcolors.WARNING, "                             Don't Care Event: ", fiddl_utils.bcolors.ENDC)
        current_app.logger.info("[DOORBELL] Other event found. Skipping.")
        return None
    print("5")
    # delete the message from the Google Cloud Platform queue
    #current_app.logger.info("[DOORBELL] Message Acknowledged")
    #message.ack()
    return info

# ----------------------------------------------------------------------------
# Grabs the Doorbell Events Image URL
# ----------------------------------------------------------------------------
# get the image url using the eventId
def get_image(eventId):
    current_app.logger.info("[DOORBELL] Getting the Event Image")
    DEVICE_ID = 'XXXX-XXXX'
    CLIENT_ID = 'XX-XXX.apps.googleusercontent.com'
    CLIENT_SECRET = 'XXXX'
    PROJECT_ID = 'XXXX'
    AUTH_CODE = 'XXXX'
    REFRESH_TOKEN = 'XXXXX'
    
    # construct the json POST request
    url_str = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/' + PROJECT_ID + '/devices/' + DEVICE_ID + ':executeCommand'
    data = '{ "command" : "sdm.devices.commands.CameraEventImage.GenerateImage", "params" : {"eventId" :  "' + eventId + '", }, }'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + get_access_token(),
    }

    current_app.logger.info("[DOORBELL] Accessing Google Cloud Nest Doorbell Image from the Event Id")
    # response from the google cloud
    response = requests.post(url_str, headers=headers, data=data).json()
    info = []
    if 'error' in response:
        print(fiddl_utils.bcolors.WARNING, "                             ERROR WITH GCLOUD RESPONSE: ", response['error']['message'], fiddl_utils.bcolors.ENDC)
        return info

    results = response['results']
    image_url = results['url']
    info.append(image_url)
    event_token = results['token']
    info.append(event_token)
    current_app.logger.info("[DOORBELL] Image URL Grabbed Succesfully")
    headers = { 'Authorization': 'Basic ' + event_token }
    info.append(headers)

    return info
    

# ----------------------------------------------------------------------------
# Gets the Image access token by using the refresh token
# ----------------------------------------------------------------------------
def get_access_token():
    DEVICE_ID = 'XXXX'
    CLIENT_ID = 'XX-XXX.apps.googleusercontent.com'
    CLIENT_SECRET = 'XXX'
    PROJECT_ID = 'XXXX'
    AUTH_CODE = 'XXXX'
    REFRESH_TOKEN = 'XXXX'
    # construct the json request
    url_str = 'https://www.googleapis.com/oauth2/v4/token?client_id=' + CLIENT_ID + '&client_secret=' + CLIENT_SECRET + '&refresh_token=' + REFRESH_TOKEN + '&grant_type=refresh_token'
    
    response = requests.post(url_str)
    json_object = response.json()
    token = json_object['access_token']
    current_app.logger.info("[DOORBELL] Image Access Token Grabbed Succesfully")

    return token




# ----------------------------------------------------------------------------
# Only need if we are pulling messages (worse than getting them pushed to us)
# ----------------------------------------------------------------------------
# pull all the messages in the event queue
def pull_messages():
    timeout = 5.0
    print("pull_messages started")

    # returns error if credentials are not set
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = current_app.config["GOOGLE_APPLICATION_CREDENTIALS"]
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = 'projects/fiddl-1604901867274/subscriptions/fiddl-sub'
    #subscriber = current_app.config['client']
    #os.system('$env:GOOGLE_APPLICATION_CREDENTIALS="C:\Users\Drew\iCloudDrive\Documents\senior design\fiddl-1604901867274-1d28c44d691d.json"')
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    print(f"Listening for messages on {subscription_path}..\n")

    # Wrap subscriber in a 'with' block to automatically call close() when done.
    with subscriber:
        try:
            # When `timeout` is not set, result() will block indefinitely,
            # unless an exception is encountered first.
            print("####################DATA FOUND $$$$$$$$$$$$$$$$$$$$$")
            streaming_pull_future.result(timeout=timeout)
        except TimeoutError:
            streaming_pull_future.cancel()
            print("Not found")
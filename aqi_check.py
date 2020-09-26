#!/usr/bin/env python

import os
import sys

try:
    # Assume Python 3.x
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
except ImportError:
    # Assume Python 2.x
    from urllib2 import Request, urlopen
    from urllib2 import URLError, HTTPError

try:
    # raise ImportError()
    # Python 2.6+
    import json
except ImportError:
    # raise ImportError()
    import simplejson as json  # from http://code.google.com/p/simplejson


def get_json(url):
    headers = {'content-type': 'application/json'}  # optionally set headers
    #req = Request(url, data, headers)
    req = Request(url, None, headers)
    f = urlopen(req)
    response_str = f.read()  # read entire response, could use json.load()
    f.close()

    response = json.loads(response_str)
    return response


# US EPA PM 2.5 AQI levels (this is NOT raw PM2.5 in ug/m3 numbers)
# "AQI" (min/max), "Air Pollution Level", "Health Implications", "Cautionary Statement (for PM2.5)", "AQI Color Name", "AQI Color Hex 24-bit"
aqi_levels = [
    (0, 50, "Good", "Air quality is considered satisfactory, and air pollution poses little or no risk", "Air quality is considered satisfactory, and air pollution poses little or no risk.", "Green", "009966"),
    (51, 100, "Moderate", "Air quality is acceptable; however, for some pollutants there may be a moderate health concern for a very small number of people who are unusually sensitive to air pollution.", "Active children and adults, and people with respiratory disease, such as asthma, should limit prolonged outdoor exertion.", "Yellow", "ffde33"),
    (101, 150, "Unhealthy for Sensitive Groups", "Members of sensitive groups may experience health effects. The general public is not likely to be affected.", "Active children and adults, and people with respiratory disease, such as asthma, should limit prolonged outdoor exertion.", "Orange", "ff9933"),
    (151, 200, "Unhealthy", "Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects", "Active children and adults, and people with respiratory disease, such as asthma, should avoid prolonged outdoor exertion; everyone else, especially children, should limit prolonged outdoor exertion", "Red", "cc0033"),
    (201, 300, "Very Unhealthy", "Health warnings of emergency conditions. The entire population is more likely to be affected.", "Active children and adults, and people with respiratory disease, such as asthma, should avoid all outdoor exertion; everyone else, especially children, should limit outdoor exertion.", "Purple", "660099"),
    (301, None, "Hazardous", "Health alert: everyone may experience more serious health effects", "Everyone should avoid all outdoor exertion", "Maroon", "7e0023"),
]

def aqi_rating(aqi):
    for level in aqi_levels[:-1]:
        min_aqi, max_aqi = level[0], level[1]
        if min_aqi <= aqi <= max_aqi:
            return level
    return aqi_levels[-1]  # catch any case not covered by the check, so too small or too large


# TODO config file
aqicn_city, aqicn_token = 'california/coast-and-central-bay/san-francisco', 'TOKEN'
airnow_zip, airnow_token = '94016', 'TOKEN'


# https://aqicn.org support
url = 'https://api.waqi.info/feed/' + aqicn_city + '/?token=' + aqicn_token  # FIXME use a template
#print(url)
# NOTE got bad gateway on API site
#url = 'https://api.waqi.info/feed/california/coast-and-central-bay/san-francisco/?token=TOKEN_HERE'
# but https://aqicn.org/california/coast-and-central-bay/san-francisco/ was still up and scrape-able  

aqis = {}

try:
    data = get_json(url)
    aqis['aqicn'] = data['data']['aqi']
    #print(data['data']['aqi'])
    #print(data['data']['city']['name'])
    #print(data['data']['time']['s'] + ' ' + data['data']['time']['tz'])  # reading timestamp
except Exception as error:
    print(error)


# AirNow / airnowapi.org - US EPA
url = 'http://www.airnowapi.org/aq/observation/zipCode/current/?format=application/json&zipCode=' + airnow_zip + '&distance=25&API_KEY=' + airnow_token
print(url)
try:
    data = get_json(url)
    #print(json.dumps(data, indent=4, sort_keys=True))
    for result in data:
        if result['ParameterName'] == 'PM2.5':
            aqis['airnow'] = result['AQI']
            # reading_timestamp = '%s%d:00:00' % (result['DateObserved'], result['HourObserved'],)
            #reading_timestamp = '%s%d:00:00 %s' % (result['DateObserved'], result['HourObserved'], result['LocalTimeZone'], )
            #print(reading_timestamp)
except Exception as error:
    print('AirNow exception')
    print(error)

max_aqi = -1
for aqi_source in aqis:
    print(aqi_source)
    aqi = aqis[aqi_source]
    max_aqi = max(max_aqi, aqi)
    print(aqi)
    level_info = aqi_rating(aqi)
    print(level_info)

print('')
print(max_aqi)
level_info = aqi_rating(max_aqi)
print(level_info)

#!/usr/bin/env python

import datetime
import os
import sys
import time

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

def my_ugm3_to_us_epa_aqi(pm25):
    # modified constants, Slide 11 https://www.epa.gov/sites/production/files/2014-05/documents/zell-aqi.pdf
    # ug/m3         US EPA       AQI Category
    pm1 = 0;         aqi1 = 0;    # Good
    pm2 = 12;        aqi2 = 50;   # Moderate
    pm3 = 35.4;      aqi3 = 100;  # USG
    pm4 = 55.4;      aqi4 = 150;  # Unhealthy
    pm5 = 150.4;     aqi5 = 200;  # Very Unhealthy
    pm6 = 250.4;     aqi6 = 300;  # Hazardous
    pm7 = 350.4;     aqi7 = 400;
    pm8 = 500.4;     aqi8 = 500;

    aqipm25 = 0
    pm25 = float(pm25)

    if (pm25 >= pm1 and pm25 <= pm2):
        aqipm25 = ((aqi2 - aqi1) / (pm2 - pm1)) * (pm25 - pm1) + aqi1
    elif (pm25 >= pm2 and pm25 <= pm3):
        aqipm25 = ((aqi3 - aqi2) / (pm3 - pm2)) * (pm25 - pm2) + aqi2
    elif (pm25 >= pm3 and pm25 <= pm4):
        aqipm25 = ((aqi4 - aqi3) / (pm4 - pm3)) * (pm25 - pm3) + aqi3
    elif (pm25 >= pm4 and pm25 <= pm5):
        aqipm25 = ((aqi5 - aqi4) / (pm5 - pm4)) * (pm25 - pm4) + aqi4
    elif (pm25 >= pm5 and pm25 <= pm6):
        aqipm25 = ((aqi6 - aqi5) / (pm6 - pm5)) * (pm25 - pm5) + aqi5
    elif (pm25 >= pm6 and pm25 <= pm7):
        aqipm25 = ((aqi7 - aqi6) / (pm7 - pm6)) * (pm25 - pm6) + aqi6
    elif (pm25 >= pm7 and pm25 <= pm8):
        aqipm25 = ((aqi8 - aqi7) / (pm8 - pm7)) * (pm25 - pm7) + aqi7

    return aqipm25


# TODO config file
config = {
    'mqtt': {
        'mqtt_broker': 'localhost',
        'mqtt_port': 1883,
        'mqtt_topic': 'aqi',
    },
    'aqi_sources': {},  # TODO
    'sleep_period': 30 * 60,   # 30 mins, expressed in seconds
}
aqicn_city, aqicn_token = 'california/coast-and-central-bay/san-francisco', 'TOKEN'
airnow_zip, airnow_token = '94016', 'TOKEN'
# PurpleAir - no API key needed
purple_sensors = ('62421', '68885')  # note strings, not integers

if config['mqtt']:
    import paho.mqtt.publish as publish  # pip install paho-mqtt


def main(argv=None):
    if argv is None:
        argv = sys.argv

    last_state = aqi_levels[0][2]

    while 1:
        aqis = {}

        # https://aqicn.org support
        url = 'https://api.waqi.info/feed/' + aqicn_city + '/?token=' + aqicn_token  # FIXME use a template
        #print(url)
        # NOTE got bad gateway on API site
        #url = 'https://api.waqi.info/feed/california/coast-and-central-bay/san-francisco/?token=TOKEN_HERE'
        # but https://aqicn.org/california/coast-and-central-bay/san-francisco/ was still up and scrape-able
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

        # PurpleAir - no API key needed
        url = 'https://www.purpleair.com/json?show=' + '|'.join(purple_sensors)
        print(url)
        try:
            data = get_json(url)
            #print(json.dumps(data, indent=4, sort_keys=True))
            for sensor in data['results']:
                """
                #print(sensor['DEVICE_LOCATIONTYPE'])  # NOT always available
                print(sensor['ID'])
                print(sensor['Label'])
                print(sensor.get('DEVICE_LOCATIONTYPE'))  # NOT always available; assume indoors if None/missing?
                print(sensor['LastSeen'])
                print(time.ctime(sensor['LastSeen']))  # TODO ISO format
                print(sensor['p_2_5_um'])  # this needs conversion
                print(sensor['pm2_5_atm'])  # this needs conversion
                print(sensor['pm2_5_cf_1'])  # this needs conversion (same as above)
                print(sensor['pm1_0_atm'])  # this needs conversion
                print(sensor['pm10_0_cf_1'])  # this needs conversion (same as above)
                print(sensor['Lat'])
                print(sensor['Lon'])
                """

                """
                result = aqi_conversion.to_iaqi(aqi_conversion.POLLUTANT_PM25, sensor['pm2_5_atm'], algo=aqi_conversion.ALGO_EPA)
                print('')
                print(result)
                result = aqi_conversion.to_aqi([
                    (aqi_conversion.POLLUTANT_PM25, sensor['p_2_5_um']),
                    (aqi_conversion.POLLUTANT_PM10, sensor['pm1_0_atm']),
                ])
                print(result)
                """
                #print(my_ugm3_to_us_epa_aqi(sensor['p_2_5_um']))
                aqis['purpleair_' + sensor['Label']] = my_ugm3_to_us_epa_aqi(sensor['p_2_5_um'])
                #print('')
        except Exception as error:
            print('PurpleAir exception')
            print(error)


        max_aqi = -1
        for aqi_source in aqis:
            print(aqi_source)
            print(datetime.datetime.now())
            aqi = aqis[aqi_source]
            max_aqi = max(max_aqi, aqi)
            print(aqi)
            level_info = aqi_rating(aqi)
            print(level_info)
        level_info = aqi_rating(max_aqi)
        # save last_aqi and compare?

        # TODO handle lookup failure, where max_aqi == -1
        """
        print('')
        print(max_aqi)
        level_info = aqi_rating(max_aqi)
        print(level_info)
        print(level_info[2])
        print(last_state)
        """

        current_state = level_info[2]
        if last_state != current_state:
            # TODO show whether improvement/deteriorated in notification?
            # notify
            description1, description2 = (level_info[3], level_info[4])  # TODO color
            message = "AQI %d %s - %s. %s" % (max_aqi, current_state, description1, description2)
            print('*' * 65)
            print(message)
            # TODO catch exceptions and ignore?
            if config['mqtt']:
                mqtt_message = message
                publish.single(config['mqtt']['mqtt_topic'], mqtt_message, hostname=config['mqtt']['mqtt_broker'], port=config['mqtt']['mqtt_port'])


        last_state = current_state
        time.sleep(config['sleep_period'])

    return 0


if __name__ == "__main__":
    sys.exit(main())

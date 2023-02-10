# -*- coding: utf-8 -*-
"""
Created on Fri Apr 13 08:43:19 2018

@author: DCMicrogrid
"""
import requests

deviceID =  '0001950000037E1C'
timeStamp = '2018-13-04 08:45:00'
data = "+0001950000037E1C|Ch1 V243.3 F50.00 I0.032 P0.1 E0.05 +0001950000037E1C|Ch2 V243.3 F50.00 I0.038 P1.3 E0.00 +0001950000037E1C|Ch3 V243.2 F50.00 I0.038 P0.4 E0.87 +0001950000037E1C|Ch4 V243.2 F49.96 I0.038 P0.8 E0.93";
payload = {'data': data , 'deviceID' : deviceID, 'timestamp': timeStamp}
print(data)
r = requests.post("http://40.65.181.20:5000/write_api", data=payload)
if r.status_code == 404:
    print("ERROR")
elif r.status_code == 200:
    print(r.text)
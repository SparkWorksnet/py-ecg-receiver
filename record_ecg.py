#!/usr/bin/python
import asyncio
import getopt
import logging
import sys

import paho.mqtt.client as mqtt
from bleak import BleakScanner
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import ASYNCHRONOUS

from device_utils import connect

help_line = 'record_ecg.py -n <name> -d <device> -s <scantime> -r <recordtime> -m <mqtt_url> -t <mqtt_topic> -i <influxdb>'


async def start_connection(d, record_time, mqtt_client, mqtt_topic, influxdb_api, influxdb_bucket):
    """
    Start connection to ECG device
    :param d: the ECG device
    :param record_time: the duration of the recording
    :param mqtt_client: the mqtt client to send the data
    :param mqtt_topic: the mqtt topic to send the data
    :param influxdb_api: the influxdb write api to append the data
    :param influxdb_bucket: the influxdb bucket to append the data
    """
    services_detected = d.metadata['uuids']
    logging.info(
        f'starting connection for: {record_time} to: {d.name}[{d.address}], rssi:{d.rssi}, services:{services_detected}')
    await connect(d, record_time=record_time, mqtt_client=mqtt_client, mqtt_topic=mqtt_topic, influxdb_api=influxdb_api,
                  influxdb_bucket=influxdb_bucket)


async def main(argv):
    device_name = 'ECG2.0-n'
    device_address = None
    scan_time = 5.0
    record_time = 120.0
    mqtt_address = None
    influxdb_address = None
    influxdb_database = None
    topic = None

    logging.basicConfig(level=logging.INFO)
    try:
        opts, args = getopt.getopt(argv, "vhn:d:s:r:m:t:i:",
                                   ["name=", "device=", "scantime=", "recordtime=", "mqtt=", "topic=", "influxdb="])
    except getopt.GetoptError:
        logging.error(help_line)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            logging.info(help_line)
            sys.exit()
        elif opt in ('-n', '--name'):
            device_name = arg
        elif opt in ('-d', '--device'):
            device_address = arg
        elif opt in ('-s', '--scantime'):
            scan_time = float(arg)
        elif opt in ('-r', '--recordtime'):
            record_time = float(arg)
        elif opt in ('-m', '--mqtt'):
            mqtt_address = arg
        elif opt in ('-i', '--influxdb'):
            parts = arg.split('/')
            if 'http://' in arg or 'https://' in arg:
                influxdb_address = parts[0] + '//' + parts[2]
                influxdb_database = parts[1]
            else:
                influxdb_address = parts[0]
                influxdb_database = parts[1]
        elif opt in ('-t', '--topic'):
            topic = arg
    if device_name is None:
        logging.info(help_line)
    else:
        client = None
        influxdb_write_api = None
        if mqtt_address is not None:
            parts = mqtt_address.split(":")
            host = parts[0]
            port = int(parts[1])
            client = mqtt.Client("py-ecg-receiver")
            client.connect(host=host, port=port)
            client.loop_start()
        if influxdb_address is not None:
            influxdb_write_api = InfluxDBClient(url=influxdb_address, token=influxdb_database,
                                                org=influxdb_database).write_api(write_options=ASYNCHRONOUS)

        logging.info(f'staring scanner for {scan_time} seconds')
        scanner = BleakScanner()
        await scanner.start()
        await asyncio.sleep(scan_time)
        await scanner.stop()
        connected_device = None
        for d in scanner.discovered_devices:
            if device_address is None and d.name is not None and d.name == device_name:
                connected_device = d
                await start_connection(d, record_time, mqtt_client=client, mqtt_topic=f'{topic}/{d.address}',
                                       influxdb_api=influxdb_write_api, influxdb_bucket=influxdb_database)
                break
            elif device_address is not None and d.address is not None and d.address == device_address:
                connected_device = d
                await start_connection(d, record_time, mqtt_client=client, mqtt_topic=f'{topic}/{d.address}',
                                       influxdb_api=influxdb_write_api, influxdb_bucket=influxdb_database)
                break
        if connected_device is None:
            logging.error(f'Failed to find any device to connect!')


asyncio.run(main(sys.argv[1:]))

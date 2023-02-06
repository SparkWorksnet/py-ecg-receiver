import asyncio
import logging
import getopt
import sys
import paho.mqtt.client as mqtt

from bleak import BleakScanner

from device_utils import connect

help_line = 'record_ecg.py -n <name> -d <device> -s <scantime> -r <recordtime>'


async def start_connection(d, record_time, mqtt_client, mqtt_topic):
    """
    Start connection to ECG device
    :param d: the ECG device
    :param record_time: the duration of the recording
    :param mqtt_client: the mqtt client to send the data
    :param mqtt_topic: the mqtt topic to send the data
    """
    services_detected = d.metadata['uuids']
    logging.info(f'starting connection to: {d.name}[{d.address}], rssi:{d.rssi}, services:{services_detected}')
    await connect(d, record_time, mqtt_client=mqtt_client, mqtt_topic=mqtt_topic)


async def main(argv):
    device_name = 'ECG2.0-n'
    device_address = None
    scan_time = 5.0
    record_time = 120.0
    mqtt_address = None
    topic = None

    logging.basicConfig(level=logging.INFO)
    try:
        opts, args = getopt.getopt(argv, "vhn:d:s:r:m:t:",
                                   ["name=", "device=", "scantime=", "recordtime=", "mqtt=", "topic="])
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
        elif opt in ('-t', '--topic'):
            topic = arg
    if device_name is None:
        logging.info(help_line)
    else:
        client = None
        if mqtt_address is not None:
            parts = mqtt_address.split(":")
            host = parts[0]
            port = int(parts[1])
            client = mqtt.Client("py-ecg-receiver")
            client.connect(host=host, port=port)
            client.loop_start()

        logging.info(f'staring scanner for {scan_time} seconds')
        scanner = BleakScanner()
        await scanner.start()
        await asyncio.sleep(scan_time)
        await scanner.stop()
        connected_device = None
        for d in scanner.discovered_devices:
            if device_address is None and d.name is not None and d.name == device_name:
                connected_device = d
                await start_connection(d, record_time, mqtt_client=client, mqtt_topic=f'{topic}/{d.address}')
                break
            elif device_address is not None and d.address is not None and d.address == device_address:
                connected_device = d
                await start_connection(d, record_time, mqtt_client=client, mqtt_topic=f'{topic}/{d.address}')
                break
        if connected_device is None:
            logging.error(f'Failed to find any device to connect!')


asyncio.run(main(sys.argv[1:]))

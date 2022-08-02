import asyncio
import logging
import getopt
import sys

from bleak import BleakScanner

from device_utils import connect

help_line = 'record_ecg.py -n <name> -d <device> -s <scantime> -r <recordtime>'

_scan_time = 5.0
_record_time = 120.0
_device_name = 'ECG2.0-n'
_device_address = None


async def start_connection(d, record_time):
    """
    Start connection to ECG device
    :param d: the ECG device
    :param record_time: the duration of the recording
    """
    services_detected = d.metadata['uuids']
    logging.info(f'starting connection to: {d.name}[{d.address}], rssi:{d.rssi}, services:{services_detected}')
    await connect(d, record_time)


async def main(argv):
    global _device_name, _device_address, _scan_time, _record_time
    logging.basicConfig(level=logging.INFO)
    try:
        opts, args = getopt.getopt(argv, "vhn:d:s:r:", ["name=", "device=", "scantime=", "recordtime="])
    except getopt.GetoptError:
        logging.error(help_line)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            logging.info(help_line)
            sys.exit()
        elif opt in ('-n', '--name'):
            _device_name = arg
        elif opt in ('-d', '--device'):
            _device_address = arg
        elif opt in ('-s', '--scantime'):
            _scan_time = float(arg)
        elif opt in ('-r', '--recordtime'):
            _record_time = float(arg)
    if _device_name is None:
        logging.info(help_line)
    else:
        logging.info(f'staring scanner for {_scan_time} seconds')
        scanner = BleakScanner()
        await scanner.start()
        await asyncio.sleep(_scan_time)
        await scanner.stop()
        connected_device = None
        for d in scanner.discovered_devices:
            if _device_address is None and d.name is not None and d.name == _device_name:
                connected_device = d
                await start_connection(d, _record_time)
                break
            elif _device_address is not None and d.address is not None and d.address == _device_address:
                connected_device = d
                await start_connection(d, _record_time)
                break
        if connected_device is None:
            logging.error(f'Failed to find any device to connect!')


asyncio.run(main(sys.argv[1:]))

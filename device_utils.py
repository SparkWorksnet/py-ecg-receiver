import logging
import asyncio
import time
from ecg_utils import process_ecg_data, process_battery_data, set_battery
from acc_utils import process_accelerometer_data
from bleak import BleakClient

battery_service_uuid = '0000180f-0000-1000-8000-00805f9b34fb'
name_service_uuid = '0000180a-0000-1000-8000-00805f9b34fb'
data_service_uuid = '87301801-d487-4fa7-960c-27955f3e4c2c'

battery_c_uuid = '00002a19-0000-1000-8000-00805f9b34fb'
cardio_command_c_uuid = '87301803-d487-4fa7-960c-27955f3e4c2c'
cardio_datastream_c_uuid = '87301805-d487-4fa7-960c-27955f3e4c2c'
cardio_accelerometer_ch_uuid = '87301807-d487-4fa7-960c-27955f3e4c2c'
cardio_features_c_uuid = '8730180c-d487-4fa7-960c-27955f3e4c2c'


async def connect(d, record_ecg=True, record_acc=False, record_time=None, mqtt_client=None, mqtt_topic=None,
                  influxdb_api=None, influxdb_bucket=None):
    """
    Connects to the ECG device and records an ECG recording
    :param d: the ECG device
    :param record_ecg: whether to record ECG data or not
    :param record_acc: whether to record ACC data or not
    :param record_time: the duration of the recording
    :param mqtt_client: the mqtt client to send the data
    :param mqtt_topic: the mqtt topic to send the data
    :param influxdb_api: the influxdb write api to append the data
    :param influxdb_bucket: the influxdb bucket to append the data
    """
    logging.info(f'record_time={record_time}')
    client = BleakClient(d.address, device='hci0')
    try:
        await client.connect()
        filename = f'{int(round(time.time()))}'
        with open(f'{filename}.ecg', "w") as ecg_file, open(f'{filename}.acc', "w") as acc_file:
            battery_bytes = await client.read_gatt_char(battery_c_uuid)
            received_battery = int.from_bytes(battery_bytes, "big")
            set_battery(received_battery)

            def battery_callback(sender, data):
                process_battery_data(data)

            def data_callback(sender, data):
                process_ecg_data(data, file=ecg_file, mqtt_client=mqtt_client, mqtt_topic=mqtt_topic,
                                 influxdb_api=influxdb_api, influxdb_bucket=influxdb_bucket)

            def acc_callback(sender, data):
                process_accelerometer_data(data, file=acc_file, mqtt_client=mqtt_client, mqtt_topic=mqtt_topic)

            await client.start_notify(battery_c_uuid, battery_callback)
            if record_ecg:
                await client.write_gatt_char(cardio_command_c_uuid, data=bytes((2,)))
            if record_acc:
                await client.write_gatt_char(cardio_command_c_uuid, data=bytes((6,)))
            await client.start_notify(cardio_datastream_c_uuid, data_callback)
            await client.start_notify(cardio_accelerometer_ch_uuid, acc_callback)
            start = time.time()
            logging.info(f'recording for {record_time} seconds, time={time.time()}')
            await asyncio.sleep(record_time)
            logging.info(f'stopped at time={time.time() - start}')
            if record_ecg:
                await client.write_gatt_char(cardio_command_c_uuid, data=bytes((3,)))
            if record_acc:
                await client.write_gatt_char(cardio_command_c_uuid, data=bytes((7,)))

    except Exception as e:
        logging.error(e)
    finally:
        await client.disconnect()

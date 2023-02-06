import logging

acc_header_len = 5
acc_data_frame_len = 12
last_packet_received = -1
recording_timestamp = -1
sample_interval_millis = 1000.0 / 100.0


def convert_sample_to_line(sample_time, data, verbose=False):
    """
    Convert an accelerometer sample to a data line
    :param sample_time: the timestamp of this sample
    :param data: the accelerometer data
    :param verbose: flag used to show data in terminal
    """
    values = [sample_time]
    values.extend(data)
    line = ','.join([str(i) for i in values])
    if verbose:
        logging.info(line)
    return line


def write_sample_to_file(data_line, file=None):
    """
    Write a sample's data to the recording's file
    :param data_line: the line of data to store
    :param file: the file where data are stored
    """
    if file is not None:
        file.write(data_line + '\n')


def write_sample_to_mqtt(data_line, mqtt_client=None, mqtt_topic=None):
    """
    Write a sample's data to the recording's file
    :param data_line: the line of data to publish
    :param mqtt_client: the mqtt client to send the data
    :param mqtt_topic: the mqtt topic to send the data
    """
    if mqtt_client is not None:
        mqtt_client.publish(f"{mqtt_topic}", data_line)


def process_accelerometer_data(data, file=None, mqtt_client=None, mqtt_topic=None):
    """
    Processes the accelerometer data received by the ECG Vest
    :param data: the accelerometer data received
    :param file: the file where data are stored
    """
    global recording_timestamp
    packet_sequence_number = data[0]
    update_sample_time(packet_sequence_number, file)
    for frame in range(19):
        acc_data_sample = []
        for j in [0, 1, 2]:
            index = acc_header_len + frame * acc_data_frame_len + j * 2
            acc_data_sample.append(lsm6dsrx_from_fs2g_to_g(data[index + 1], data[index]))
        for j in [3, 4, 5]:
            index = acc_header_len + frame * acc_data_frame_len + j * 2
            acc_data_sample.append(lsm6dsrx_from_fs250dps_to_dps(data[index + 1], data[index]))
        data_line = convert_sample_to_line(recording_timestamp, acc_data_sample)
        write_sample_to_file(data_line, file=file)
        write_sample_to_mqtt(data_line, mqtt_client=mqtt_client, mqtt_topic=f"{mqtt_topic}/acc")
        recording_timestamp += sample_interval_millis


def lsm6dsrx_from_fs2g_to_g(msb, lsb):
    """
    Convert received data to G values. Accelerometer is set to LSM6DSRX_2g
    :param msb: the msb of the value received
    :param lsb: the lsb of the value received
    :return: the converted acceleration value is Gs
    """
    return round(((msb * 256 + lsb) * 0.061) / 1000, 2)


def lsm6dsrx_from_fs250dps_to_dps(msb, lsb):
    """
    Convert received data to dps values. Gyro is set to LSM6DSRX_250dps
    :param msb: the msb of the value received
    :param lsb: the lsb of the value received
    :return: the converted gyroscope value in dps
    """
    return round(((msb * 256 + lsb) * 8.75) / 1000, 2)


def update_sample_time(sequence_no, file=None):
    """
    Updates the timestamp for beginning of the current packet based on its sequence number
    :param sequence_no: the sequence number of the currently processed packet
    :param file: the file where data are stored
    """
    global recording_timestamp, last_packet_received
    if recording_timestamp == -1:
        recording_timestamp = 0

    missing_count = 0

    was_last_packet_received = last_packet_received

    if ((sequence_no != 0 or last_packet_received != 254)
            and (sequence_no != (last_packet_received + 1))):
        if sequence_no > last_packet_received:
            while last_packet_received < (sequence_no - 1):
                last_packet_received = last_packet_received + 1
                missing_count = missing_count + 1
        else:
            while last_packet_received < 255:
                last_packet_received = last_packet_received + 1
                missing_count = missing_count + 1
            last_packet_received = -1
            while last_packet_received < sequence_no - 1:
                last_packet_received = last_packet_received + 1
                missing_count = missing_count + 1
    if missing_count > 0 and file is not None:
        logging.warn(
            f'# [ecg] missed {missing_count} packets - last was {was_last_packet_received} but received {sequence_no}')
        write_missing_to_file(sequence_no, was_last_packet_received, missing_count, file)
    recording_timestamp = recording_timestamp + missing_count * sample_interval_millis
    last_packet_received = sequence_no


def write_missing_to_file(current, last, missed, file=None):
    """
    Report missing packets to the file of the recording
    :param current: the current packet sequence number
    :param last: the last received packet sequence number
    :param missed: the missed packets
    :param file: the file where data are stored
    """
    if file is not None:
        file.write(f'# [acc] missed {missed} packets - last was {last} but received {current}\n')

import logging
import numpy as np

int_values = []
single_sample_length = 8
sample_interval_millis = 1000.0 / 500.0

received_battery = 0

last_packet_received = -1
recording_timestamp = -1


def convert_sample_to_line(sample_time, channel_data, avg_qrs=0, avg_qrs_millis=0, is_qrs=0, battery=0, verbose=False):
    """
    Convert an ecg sample to a data line
    :param sample_time: the timestamp of this sample
    :param channel_data: the 12 ECG channel data
    :param avg_qrs: current qes duration in samples
    :param avg_qrs_millis: current qrs duration in milliseconds
    :param is_qrs: flag that shows if this is the spike of the QRS complex
    :param battery: the battery of the ECG device
    :param verbose: flag used to show data in terminal
    """
    values = [sample_time]
    values.extend(channel_data)
    values.extend([avg_qrs, avg_qrs_millis, is_qrs, battery])
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


def write_missing_to_file(current, last, missed, file=None):
    """
    Report missing packets to the file of the recording
    :param current: the current packet sequence number
    :param last: the last received packet sequence number
    :param missed: the missed packets
    :param file: the file where data are stored
    """
    if file is not None:
        file.write(f'# [ecg] missed {missed} packets - last was {last} but received {current}\n')


def produce_channel_data_from_lead_values(in_data):
    """
    Generates the 12 ECG channel data from the values received for the 10 leads.
    :param in_data: the 10 lead data received
    :return: the 12 ECG channel data
    """
    channels = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    #
    # after july 30 and with avr "fixed"
    #
    l1 = in_data[0]
    # - ECGCommConstants.ecgLeadsBaseLine
    # subtracting the baseline here was a temp thing - only to facilitate proper placement in the graph when this was later included by the visualization code (Signal.java redraw())
    l2 = in_data[1]
    # - ECGCommConstants.ecgLeadsBaseLine
    # subtracting the baseline here was a temp thing - only to facilitate proper placement in the graph when this was later included by the visualization code (Signal.java redraw())
    l3 = (l2 - l1)
    # avr = -l2 + l3 / 2
    avr = (-(l1 + l2) / 2)  # confirmed = same as previous
    avl = (l1 - l2 / 2)  # confirmed
    avf = (l3 + l1 / 2)  # confirmed
    # LA
    channels[0] = l1
    # RA
    channels[1] = l2
    # I = LA-RA
    channels[2] = l3
    # + ECGCommConstants.ecgLeadsBaseLine
    # adding the baseline here was a temp thing - only to facilitate proper placement in the graph when this was later included by the visualization code (Signal.java redraw())
    channels[3] = avr
    # + ECGCommConstants.ecgLeadsBaseLine
    # adding the baseline here was a temp thing - only to facilitate proper placement in the graph when this was later included by the visualization code (Signal.java redraw())
    channels[4] = avl
    # + ECGCommConstants.ecgLeadsBaseLine
    # adding the baseline here was a temp thing - only to facilitate proper placement in the graph when this was later included by the visualization code (Signal.java redraw())
    channels[5] = avf
    # + ECGCommConstants.ecgLeadsBaseLine
    # adding the baseline here was a temp thing - only to facilitate proper placement in the graph when this was later included by the visualization code (Signal.java redraw())
    channels[6] = in_data[2]
    channels[7] = in_data[3]
    channels[8] = in_data[4]
    channels[9] = in_data[5]
    channels[10] = in_data[6]
    channels[11] = in_data[7]

    return channels


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


def process_ecg_data(data, file=None, mqtt_client=None, mqtt_topic=None):
    """
    Processes the ecg data received by the ECG Vest
    :param data: the ecg data received
    :param file: the file where data are stored
    :param mqtt_client: the mqtt client to send the data
    :param mqtt_topic: the mqtt topic to send the data
    """
    global recording_timestamp
    packet_sequence_number = data.pop(0)
    update_sample_time(packet_sequence_number, file)

    header = [data.pop(0), data.pop(0), data.pop(0), data.pop(0)]

    rem = len(data)

    a = np.array(data)
    hex_string = a.astype(np.uint8).data.hex()

    measurements = []
    n = 6  # chunk length
    chunks = [hex_string[i:i + n] for i in range(0, len(hex_string), n)]

    # extract measurements from chunks (3 measurements are fit in every two bytes - 12bits per measurement)
    for item in chunks:
        measurements.append(item[3] + item[0] + item[1])  # a1+a2+a3
        measurements.append(item[4] + item[5] + item[2])  # b1+b2+b3

    new_int_values = [int(m, base=16) for m in measurements]
    int_values.extend(new_int_values)

    while len(int_values) > single_sample_length:
        leads = []
        for i in range(single_sample_length):
            leads.append(int_values.pop(0))
        channel_data = produce_channel_data_from_lead_values(leads)
        data_line = convert_sample_to_line(recording_timestamp, channel_data, battery=received_battery)
        write_sample_to_file(data_line=data_line, file=file)
        write_sample_to_mqtt(data_line=data_line, mqtt_client=mqtt_client, mqtt_topic=f"{mqtt_topic}/ecg")
        recording_timestamp += sample_interval_millis


def set_battery(battery):
    """
    Set the value of the ECG device battery
    :param battery: the value to set for the ECG device battery
    """
    global received_battery
    received_battery = battery
    logging.info(f'Battery: {received_battery}')


def process_battery_data(data):
    """
    Processes the battery data received by the ECG Vest
    :param data: the battery data received
    """
    global received_battery
    received_battery = int.from_bytes(data[0], "big")
    logging.info(f'Battery: {received_battery}')

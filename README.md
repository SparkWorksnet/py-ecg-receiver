# py-ecg-receiver

This repository is used to receive ecg recordings from the Sparks ECG Vest.

## Execution

````shell
./record_ecg.py -v -h -n[--name] -s[--scantime] -r[--recordtime] -m[--mqtt] -t[--topic]
````

* v : verbose output
* h : help output
* n : bluetooth name of the ecg device
* s : scan time for detecting the ecg device in seconds
* r : total duration of the recording in seconds
* m : mqtt address in the format of `host:port`
* t : mqtt topic prefix

## Outputs

The data collected can be outputed to two sources:

* File
* MQTT

### File Output

Using the file output each recording produces two files. One file (.ecg extension) contains the ECG recorded data and
second file (.acc extension) contains the accelerometer data.

For the ecg file the contents are the following:

* Time Since the beginning in ms
* 12 channel data
* `avg_qrs`
* `avg_qrs_millis`
* `is_qrs`
* Device Battery

For the accelerometer file the contents are the following:

* Time Since the beginning in ms
* X Y Z Acceleration
* X Y Z Gyroscope

### MQTT Output

Using the MQTT output each recording produces new mqtt messages in two MQTT topics:

* `{prefix}/{ecg_address}/ecg` : with data regarding ECG information (in the format presented above)
* `{prefix}/{ecg_address}/acc` : with data regarding Accelerometer information (in the format presented

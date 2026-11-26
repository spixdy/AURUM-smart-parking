# MQTT setup (HiveMQ Cloud or EMQX Cloud)

Both services give you a free serverless/cloud broker with TLS on port **8883**.

## HiveMQ Cloud
1. Create a free cluster at https://console.hivemq.cloud.
2. *Access Management* → create credentials (username + password) with publish **and** subscribe rights.
3. Copy the cluster hostname (looks like `abc123.s1.eu.hivemq.cloud`).

## EMQX Cloud
1. Create a Serverless deployment at https://cloud.emqx.com.
2. *Authentication* → add a username/password; *Overview* shows the host and TLS port (8883).

## Configure AURUM
In `.env` (or your cloud app settings):
```
MQTT_HOST=<your host>
MQTT_PORT=8883
MQTT_USERNAME=<user>
MQTT_PASSWORD=<password>
MQTT_TOPIC_PREFIX=aurum/parking
```
TLS turns on automatically for 8883/8084 and verifies the broker certificate.

## Test it
```bash
python -m aurum.ingest                 # terminal 1: subscriber
python -m aurum.simulator --interval 5 # terminal 2: publishes 12 readings per tick
```
You can also publish by hand from the broker's web client to
`aurum/parking/igi/occupancy` with `{"occupied": 2100}`.

## Troubleshooting
- *Connection refused / timeout*: check host, port and that your network allows outbound 8883.
- *Not authorised*: the credential needs publish and subscribe permission on `aurum/parking/#`.
- *Messages ignored*: the ingest log prints the rejection reason (unknown place, bad JSON, out of range).

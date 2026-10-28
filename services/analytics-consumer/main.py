import json
import logging
import os
import time
from datetime import datetime, timezone

from azure.core.exceptions import ResourceExistsError
from azure.storage.filedatalake import DataLakeServiceClient
from confluent_kafka import Consumer

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("rideflow-analytics-consumer")

BOOTSTRAP = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
TOPIC = os.getenv("KAFKA_TOPIC", "trips")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "rideflow-analytics-consumer")
ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]
FILESYSTEM = os.getenv("AZURE_STORAGE_FILESYSTEM", "trip-analytics")
DIRECTORY = os.getenv("AZURE_STORAGE_DIRECTORY", "raw/trip-events")
SAS_TOKEN = os.environ["AZURE_STORAGE_SAS_TOKEN"].lstrip("?")

service = DataLakeServiceClient(
    account_url=f"https://{ACCOUNT}.dfs.core.windows.net",
    credential=SAS_TOKEN,
)
filesystem = service.get_file_system_client(FILESYSTEM)

try:
    filesystem.create_file_system()
except ResourceExistsError:
    pass

consumer = Consumer({
    "bootstrap.servers": BOOTSTRAP,
    "group.id": GROUP_ID,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
})

def persist_event(event):
    event_id = event["event_id"]
    path = f"{DIRECTORY}/{event_id}.json"
    file_client = filesystem.get_file_client(path)

    # Event IDs make retries idempotent in ADLS.
    if file_client.exists():
        logger.info("Already stored event_id=%s", event_id)
        return

    payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
    file_client.create_file()
    file_client.append_data(data=payload, offset=0, length=len(payload))
    file_client.flush_data(len(payload))
    logger.info(
        "Stored event_id=%s type=%s path=%s",
        event_id, event.get("event_type"), path,
    )

def main():
    consumer.subscribe([TOPIC])
    logger.info("Consuming topic=%s group=%s", TOPIC, GROUP_ID)

    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                logger.error("Kafka message error: %s", message.error())
                continue

            while True:
                try:
                    event = json.loads(message.value().decode("utf-8"))
                    if not isinstance(event, dict):
                        raise ValueError("Kafka event must be a JSON object")

                    if not all(k in event for k in ("event_id", "event_type", "trip")):
                        if "source" in event and "event_type" in event:
                            logger.info(
                                "Skipping non-trip control event type=%s source=%s",
                                event.get("event_type"),
                                event.get("source"),
                            )
                            consumer.commit(message=message, asynchronous=False)
                            break

                        raise ValueError("Unexpected RideFlow event schema")

                    persist_event(event)

                    # Commit only after the event is confirmed in ADLS.
                    consumer.commit(message=message, asynchronous=False)
                    break
                except Exception:
                    logger.exception(
                        "Processing failed; retrying the same message in 5 seconds."
                    )
                    time.sleep(5)
    finally:
        consumer.close()
        service.close()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import datetime
import subprocess
import time
import logging
import configparser
import websocket
import json
import httpx
import psutil


from glonax import client as gclient
from glonax.client import GlonaxServiceBase
from glonax.message import VMS, Engine, ModuleStatus, Gnss
from rms import RemoteManagementService


logging.basicConfig(
    level=logging.DEBUG,
)

config = configparser.ConfigParser()
logger = logging.getLogger()


glonax_store = {}


def on_message(ws, message):
    try:
        data = json.loads(message)  # Assuming JSON messages
        print("Received:", data)
    except json.JSONDecodeError:
        print("Received raw message:", message)


def on_error(ws, error):
    print("Error:", error)


def on_close(ws):
    print("Connection closed")


is_connected = False


def on_open(ws):
    global is_connected

    message = {
        "type": "notify",
        "topic": "boot",
    }
    ws.send(json.dumps(message))

    is_connected = True


ws = websocket.WebSocketApp(
    # "wss://edge.laixer.equipment/78adc7fc-6f60-4fc7-81ed-91396892f4a1/ws",
    "ws://localhost:8000/api/78adc7fc-6f60-4fc7-81ed-91396892f4a1/ws",
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
    on_open=on_open,
)

from pydantic import BaseModel


class ChannelMessage(BaseModel):
    type: str
    topic: str | None = None
    data: dict | None = None


# class GlonaxStreamListener(threading.Thread):
#     def __init__(self):
#         super().__init__()

#     def run(self):
#         glonax_address = config["glonax"]["address"]
#         glonax_port = config["glonax"]["port"]

#         client = gclient.Client(glonax_address, int(glonax_port))
#         client.connect()

#         vms_last: VMS | None = None
#         engine_last: Engine | None = None

#         while True:
#             message_type, message = client.recv()

#             if message_type == MessageType.STATUS:
#                 status = ModuleStatus.from_bytes(message)
#                 print(status)

#                 message = ChannelMessage(
#                     type="signal", topic="status", data=status.model_dump()
#                 )

#                 # TODO: Only send if the connection is open
#                 # ws.send(message.model_dump_json())

#             elif message_type == MessageType.VMS:
#                 vms = VMS.from_bytes(message)
#                 print(vms)

#                 if vms_last == vms:
#                     print("VMS is the same")
#                     continue

#                 message = ChannelMessage(
#                     type="signal", topic="vms", data=vms.model_dump()
#                 )

#                 # TODO: Only send if the connection is open
#                 # ws.send(message.model_dump_json())

#                 vms_last = vms

#             elif message_type == MessageType.ENGINE:
#                 engine = Engine.from_bytes(message)
#                 print(engine)

#                 if engine_last == engine:
#                     print("Engine is the same")
#                     continue

#                 message = ChannelMessage(
#                     type="signal", topic="engine", data=engine.model_dump()
#                 )

#                 # TODO: Only send if the connection is open
#                 # ws.send(message.model_dump_json())

#                 engine_last = engine

#             #     glonax_store["engine"] = engine

#             #     # logger.debug(f"Engine: {engine}")
#             # elif message_type == MessageType.GNSS:
#             #     gnss = Gnss.from_bytes(message)
#             #     glonax_store["gnss"] = gnss

#             # logger.debug(f"GNSS: {gnss}")
#             # else:
#             #     logger.warning(f"Unknown message type: {message_type}")


def remote_probe():
    server_config = config["server"]

    host = server_config["host"]
    auth = server_config["authkey"]

    vms = glonax_store.get("vms")
    instance = glonax_store.get("instance")

    if not instance or not vms:
        return

    rms = RemoteManagementService(host, auth, instance)
    rms.register_telemetry(vms)


def remote_manifest():
    server_config = config["server"]

    host = server_config["host"]
    auth = server_config["authkey"]

    instance = glonax_store.get("instance")

    if not instance:
        return

    rms = RemoteManagementService(host, auth, instance)
    manifest = rms.fetch_manifest()
    print(f"Manifest: {manifest}")


# def main():
#     logger.debug("Reading configuration file")

#     config.read("config.ini")

#     glonax_listener = GlonaxStreamListener()
#     glonax_listener.start()


class GlonaxService(GlonaxServiceBase):
    global is_connected

    gnss_last: Gnss | None = None
    vms_last: VMS | None = None
    engine_last: Engine | None = None

    def on_status(self, client: gclient.GlonaxClient, status: ModuleStatus):
        print(status)

        message = ChannelMessage(
            type="signal", topic="status", data=status.model_dump()
        )

        if is_connected:
            # TODO: Only send if the connection is open
            ws.send(message.model_dump_json())

    def on_gnss(self, client: gclient.GlonaxClient, gnss: Gnss):
        if self.gnss_last == gnss:
            print(gnss)
            message = ChannelMessage(
                type="signal", topic="gnss", data=gnss.model_dump()
            )

            if is_connected:
                # TODO: Only send if the connection is open
                ws.send(message.model_dump_json())

            self.gnss_last = gnss

    def on_engine(self, client: gclient.GlonaxClient, engine: Engine):
        if self.engine_last != engine:
            print(engine)
            message = ChannelMessage(
                type="signal", topic="engine", data=engine.model_dump()
            )

            if is_connected:
                # TODO: Only send if the connection is open
                ws.send(message.model_dump_json())

            self.engine_last = engine

    def on_vms(self, client: gclient.GlonaxClient, vms: VMS):
        # TODO: Check if too much time has passed, then send a signal
        if self.vms_last != vms:
            print(vms)
            message = ChannelMessage(type="signal", topic="vms", data=vms.model_dump())

            if is_connected:
                # TODO: Only send if the connection is open
                ws.send(message.model_dump_json())

            self.vms_last = vms


class Telemetry(BaseModel):
    memory_used: float
    disk_used: float
    cpu_freq: float
    cpu_load: tuple[float, float, float]
    uptime: int
    created_at: datetime.timedelta | None = None


def create_telemetry() -> Telemetry:
    def seconds_elapsed() -> int:
        return round(time.time() - psutil.boot_time())

    telemetry = Telemetry(
        memory_used=psutil.virtual_memory().percent,
        disk_used=psutil.disk_usage("/").percent,
        cpu_freq=psutil.cpu_freq().current,
        cpu_load=psutil.getloadavg(),
        uptime=seconds_elapsed(),
    )
    return telemetry


class HostConfig(BaseModel):
    # instance: UUID # TODO: Add this field
    name: str | None = None
    hostname: str
    kernel: str
    # memory_total: int # TODO: Add this field
    # cpu_count: int # TODO: Add this field
    model: str
    version: int
    serial_number: str


def create_host_config() -> HostConfig:
    hostname = subprocess.check_output(["hostname"]).decode().strip()
    kernel = subprocess.check_output(["uname", "-r"]).decode().strip()

    host_config = HostConfig(
        hostname=hostname,
        kernel=kernel,
        model="test",
        version=378,
        serial_number="test",
    )
    return host_config


if __name__ == "__main__":
    config.read("config.ini")

    # glonax_address = config["glonax"]["address"]
    # glonax_port = config["glonax"]["port"]

    instance = config["glonax"]["instance"]

    headers = {"Authorization": "Bearer " + config["server"]["authkey"]}

    def update_host():
        data = create_host_config().model_dump()

        host = config["server"]["host"].rstrip("/")

        r = httpx.put(f"{host}/{instance}/host", json=data, headers=headers)
        r.raise_for_status()

    def update_telemetry():
        data = create_telemetry().model_dump()

        host = config["server"]["host"].rstrip("/")

        r = httpx.post(f"{host}/{instance}/telemetry", json=data, headers=headers)
        r.raise_for_status()

    update_host()

    while True:
        update_telemetry()

        time.sleep(60)

    # glonax_service = GlonaxService()

    # client = gclient.GlonaxClient(glonax_address)
    # client.listen(glonax_service)

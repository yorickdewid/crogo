#!/usr/bin/env python3

import logging
import configparser
import websocket
import json
import httpx


from glonax import client as gclient
from glonax.client import GlonaxServiceBase
from glonax.message import VMS, Engine, ModuleStatus, Gnss
from pydantic import BaseModel


logging.basicConfig(
    level=logging.DEBUG,
)

config = configparser.ConfigParser()
logger = logging.getLogger()


glonax_store = {}


class ChannelMessage(BaseModel):
    type: str
    topic: str | None = None
    data: dict | None = None


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
        pass
        # TODO: Check if too much time has passed, then send a signal
        # if self.vms_last != vms:
        #     print(vms)
        #     message = ChannelMessage(type="signal", topic="vms", data=vms.model_dump())

        #     if is_connected:
        #         # TODO: Only send if the connection is open
        #         ws.send(message.model_dump_json())

        #     self.vms_last = vms


if __name__ == "__main__":
    config.read("config.ini")

    glonax_address = config["glonax"]["address"]
    # glonax_port = config["glonax"]["port"]

    instance = config["glonax"]["instance"]

    glonax_service = GlonaxService()

    client = gclient.GlonaxClient(glonax_address)
    client.listen(glonax_service)

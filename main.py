#!/usr/bin/env python3

import time
import logging
import threading
import configparser
import websocket
import json

from glonax import client as gclient
from glonax.client import GlonaxServiceBase
from glonax.message import Engine, ModuleStatus, Gnss
from pydantic import BaseModel, ValidationError


logging.basicConfig(
    level=logging.DEBUG,
)

config = configparser.ConfigParser()
logger = logging.getLogger()

is_connected = False

ws: websocket.WebSocketApp | None = None


class ChannelMessage(BaseModel):
    type: str
    topic: str | None = None
    data: dict | None = None


def on_message(ws, message):
    try:
        data = json.loads(message)  # Assuming JSON messages

        message = ChannelMessage(**data)

        print("Received message:", message)

    except json.JSONDecodeError:
        print("Received raw message:", message)
    except ValidationError as e:
        print("Validation error:", e)


def on_error(ws, error):
    print("Error:", error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws):
    global is_connected

    is_connected = True


class GlonaxService(GlonaxServiceBase):
    global is_connected

    status_map = {}
    status_map_last_update = {}
    gnss_last: Gnss | None = None
    gnss_last_update = time.time()
    engine_last: Engine | None = None
    engine_last_update = time.time()

    def on_status(self, client: gclient.GlonaxClient, status: ModuleStatus):
        val = self.status_map.get(status.name)
        last_update = self.status_map_last_update.get(status.name, 0)
        last_update_elapsed = time.time() - last_update
        if val is None or val != status or last_update_elapsed > 15:
            logger.info(f"Status: {status}")

            message = ChannelMessage(
                type="signal", topic="status", data=status.model_dump()
            )

            if is_connected and ws:
                # TODO: Only send if the connection is open
                ws.send(message.model_dump_json())

            self.status_map[status.name] = status
            self.status_map_last_update[status.name] = time.time()

    def on_gnss(self, client: gclient.GlonaxClient, gnss: Gnss):
        gnss_last_update_elapsed = time.time() - self.gnss_last_update
        if self.gnss_last == gnss or gnss_last_update_elapsed > 15:
            logger.info(f"GNSS: {gnss}")

            message = ChannelMessage(
                type="signal", topic="gnss", data=gnss.model_dump()
            )

            if is_connected and ws:
                # TODO: Only send if the connection is open
                ws.send(message.model_dump_json())

            self.gnss_last = gnss
            self.gnss_last_update = time.time()

    def on_engine(self, client: gclient.GlonaxClient, engine: Engine):
        engine_last_update_elapsed = time.time() - self.engine_last_update
        if self.engine_last != engine or engine_last_update_elapsed > 15:
            logger.info(f"Engine: {engine}")
            message = ChannelMessage(
                type="signal", topic="engine", data=engine.model_dump()
            )

            if is_connected and ws:
                # TODO: Only send if the connection is open
                ws.send(message.model_dump_json())

            self.engine_last = engine
            self.engine_last_update = time.time()


if __name__ == "__main__":
    config.read("config.ini")

    glonax_address = config["glonax"]["address"]
    # glonax_port = config["glonax"]["port"]

    instance = config["glonax"]["instance"]

    ws = websocket.WebSocketApp(
        # f"wss://edge.laixer.equipment/api/{instance}/ws",
        f"ws://localhost:8000/{instance}/ws",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )

    def glonax_function():
        glonax_service = GlonaxService()

        client = gclient.GlonaxClient(glonax_address)
        client.listen(glonax_service)

    x = threading.Thread(target=glonax_function)
    x.start()

    ws.run_forever()

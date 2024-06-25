#!/usr/bin/env python3

import datetime
import subprocess
import threading
import time
import requests
import logging
import configparser
import schedule


from glonax import client as gclient
from glonax.client import VMS, Engine, Gnss, MessageType, Control, Request, ModuleStatus
from rms import RemoteManagementService


logging.basicConfig(
    level=logging.DEBUG,
)

config = configparser.ConfigParser()
logger = logging.getLogger()


glonax_store = {}


# def get_hostname():
#     """Run the hostname command and return the output as a string"""
#     result = subprocess.run(["hostname"], capture_output=True, text=True, check=True)
#     return result.stdout.strip()


# def get_kernel_version():
#     """Run the uname command and return the kernel version"""
#     result = subprocess.run(["uname", "-r"], capture_output=True, text=True, check=True)
#     return result.stdout.strip()


def reboot():
    """Run the reboot command"""
    subprocess.run(["sudo", "shutdown", "-r", "now"])


# class NetworkDiscovery(threading.Thread):
#     def __init__(self):
#         super().__init__()
#         self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
#         self.sock.bind(("", 30050))

#     def run(self):
#         print("Starting network discovery")

#         while True:
#             data, addr = self.sock.recvfrom(1024)
#             # network_map[addr[0]] = data

#             message_type, _ = client.Frame.parse(data)
#             f = client.Frame.parse_message(data[10:], message_type)
#             print(f"Received message: {f} from: {addr}")


# class NetworkAnnouncer(threading.Thread):
#     def __init__(self):
#         super().__init__()
#         self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)

#     def run(self):
#         print("Starting network announcement")

#         while True:
#             data = client.Frame.status(client.Status.HEALTHY)

#             self.sock.sendto(data, ("ff02::1", 30050))

#             time.sleep(3)


class GlonaxStreamListener(threading.Thread):
    def __init__(self):
        super().__init__()

    def run(self):
        glonax_address = config["glonax"]["address"]
        glonax_port = config["glonax"]["port"]

        client = gclient.Client(glonax_address, int(glonax_port))
        client.connect()

        config["DEFAULT"]["instance"] = str(client.machine.id)

        glonax_store["instance"] = client.machine

        while True:
            message_type, message = client.recv()

            if message_type == MessageType.STATUS:
                status = ModuleStatus.from_bytes(message)

                # logger.debug(f"Status: {status}")
            elif message_type == MessageType.VMS:
                vms = VMS.from_bytes(message)
                glonax_store["vms"] = vms

                logger.info(f"{vms}")
            elif message_type == MessageType.ENGINE:
                engine = Engine.from_bytes(message)
                glonax_store["engine"] = engine

                logger.debug(f"Engine: {engine}")
            elif message_type == MessageType.GNSS:
                gnss = Gnss.from_bytes(message)
                glonax_store["gnss"] = gnss

                logger.debug(f"GNSS: {gnss}")
            # else:
            #     logger.warning(f"Unknown message type: {message_type}")


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


def remote_command():
    server_config = config["server"]

    host = server_config["host"]
    auth = server_config["authkey"]

    instance = glonax_store.get("instance")

    if not instance:
        return

    rms = RemoteManagementService(host, auth, instance)
    cmds = rms.fetch_commands()
    for cmd in cmds:
        command = cmd["command"]
        # print(f"Command: {command}")
        if command == "reboot":
            # reboot()
            pass
        elif command == "engine_start":
            pass
        elif command == "engine_stop":
            pass


def main():
    logger.debug("Reading configuration file")

    config.read("config.ini")

    glonax_listener = GlonaxStreamListener()
    glonax_listener.start()

    schedule.every(10).seconds.do(remote_probe)
    # schedule.every(10).seconds.do(remote_command)

    while True:
        schedule.run_pending()
        time.sleep(1)

    # TODO: join all threads


if __name__ == "__main__":
    main()

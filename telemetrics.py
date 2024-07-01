#!/usr/bin/env python3

import datetime
import subprocess
import time
import logging
import configparser
import httpx
import psutil

from pydantic import BaseModel
from rms import RemoteManagementService


logging.basicConfig(
    level=logging.DEBUG,
)

config = configparser.ConfigParser()
logger = logging.getLogger()


class Telemetry(BaseModel):
    memory_used: float
    disk_used: float
    cpu_freq: float
    cpu_load: tuple[float, float, float]
    uptime: int
    created_at: datetime.timedelta | None = None


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


def remote_manifest():
    server_config = config["server"]

    host = server_config["host"]
    auth = server_config["authkey"]

    if not instance:
        return

    rms = RemoteManagementService(host, auth, instance)
    manifest = rms.fetch_manifest()
    print(f"Manifest: {manifest}")


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

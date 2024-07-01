import datetime
import subprocess
import logging
import requests

logger = logging.getLogger(__name__)


def get_hostname():
    """Run the hostname command and return the output as a string"""
    result = subprocess.run(["hostname"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def get_kernel_version():
    """Run the uname command and return the kernel version"""
    result = subprocess.run(["uname", "-r"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


class RemoteManagementService:
    def __init__(self, host, auth, instance):
        self.host = host
        self.auth = auth
        self.instance = instance

    def _call_headers(self):
        return {
            "Authorization": f"Bearer {self.auth}",
        }

    def register_telemetry(self, vms):
        url = f"{self.host}/api/{self.instance.id}/telemetry"

        try:
            hostname = get_hostname()
            kernel_version = get_kernel_version()
            utc_now = datetime.datetime.now(datetime.timezone.utc)

            data = {
                "instance": {
                    "id": str(self.instance.id),
                    "model": self.instance.model,
                    # TODO: Add machine type
                    "version": self.instance.version,
                    "serial_number": self.instance.serial_number,
                },
                "meta": {
                    "hostname": hostname,
                    "kernel": kernel_version,
                    "datetime": utc_now.isoformat(),
                },
            }

            # TODO: Why not use psutil?
            data["host"] = {
                "cpu1": vms.cpu_load[0],
                "cpu5": vms.cpu_load[1],
                "cpu15": vms.cpu_load[2],
                "mem_used": vms.memory[0],
                "mem_total": vms.memory[1],
                "uptime": vms.uptime,
            }

            # TODO: Connect to the actual engine
            data["engine"] = {
                "rpm": 0,
            }

            # print(f"Data: {data}")
            response = requests.post(
                url, json=data, headers=self._call_headers(), timeout=15
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error: {e}")

    def fetch_manifest(self):
        url = f"{self.host}{self.instance.id}/manifest"

        try:
            response = requests.get(url, headers=self._call_headers(), timeout=5)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logger.error(f"Error: {e}")

    def fetch_commands(self):
        url = f"{self.host}{self.instance.id}/command"

        try:
            response = requests.get(url, headers=self._call_headers(), timeout=5)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logger.error(f"Error: {e}")

    def get_remote_client(self):
        url = f"{self.host}/client"

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logger.error(f"Error: {e}")

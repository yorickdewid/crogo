import datetime
import struct
from uuid import UUID

from pydantic import BaseModel, Field


class Instance(BaseModel):
    id: UUID
    model: str
    machine_type: int
    version: tuple[int, int, int]
    serial_number: str

    def from_bytes(data):
        id = UUID(bytes=data[:16])
        machine_type = data[16]
        version = struct.unpack("BBB", data[17:20])

        model_length = struct.unpack(">H", data[20:22])[0]
        model = data[22 : 22 + model_length].decode("utf-8")

        serial_number_length = struct.unpack(
            ">H", data[22 + model_length : 24 + model_length]
        )[0]
        serial_number = data[
            24 + model_length : 24 + model_length + serial_number_length
        ].decode("utf-8")

        return Instance(
            id=id,
            model=model,
            machine_type=machine_type,
            version=version,
            serial_number=serial_number,
        )

    def to_bytes(self):
        return (
            self.id.bytes
            + struct.pack("B", self.machine_type)
            + struct.pack("BBB", *self.version)
            + struct.pack(">H", len(self.model))
            + self.model.encode("utf-8")
            + struct.pack(">H", len(self.serial_number))
            + self.serial_number.encode("utf-8")
        )


class ModuleStatus(BaseModel):
    name: str
    state: int
    error_code: int

    def from_bytes(data):
        name_length = struct.unpack(">H", data[0:2])[0]
        name = data[2 : 2 + name_length].decode("utf-8")

        state = data[2 + name_length]
        error_code = data[3 + name_length]

        return ModuleStatus(name=name, state=state, error_code=error_code)

    def to_bytes(self):
        return (
            struct.pack(">H", len(self.name))
            + self.name.encode("utf-8")
            + struct.pack("BB", self.state, self.error_code)
        )


# TODO: Can be removed
class VMS(BaseModel):
    memory_used: int
    memory_total: int  # TODO: Remove, should not change
    swap_used: int  # TODO: Remove, swap should always be 0
    swap_total: int  # TODO: Remove, swap should always be 0
    cpu_load: list[float]
    uptime: int
    timestamp: datetime.datetime

    @property
    def memory_used_mb(self):
        return self.memory_used / 1024 / 1024

    @property
    def memory_total_mb(self):
        return self.memory_total / 1024 / 1024

    @property
    def swap_used_mb(self):
        return self.swap_used / 1024 / 1024

    @property
    def swap_total_mb(self):
        return self.swap_total / 1024 / 1024

    def from_bytes(data):
        memory_used = struct.unpack(">Q", data[:8])[0]
        memory_total = struct.unpack(">Q", data[8:16])[0]
        swap_used = struct.unpack(">Q", data[16:24])[0]
        swap_total = struct.unpack(">Q", data[24:32])[0]
        cpu_load = struct.unpack(">ddd", data[32:56])
        uptime = struct.unpack(">Q", data[56:64])[0]
        timestamp = struct.unpack(">q", data[64:72])[0]

        return VMS(
            memory_used=memory_used,
            memory_total=memory_total,
            swap_used=swap_used,
            swap_total=swap_total,
            cpu_load=cpu_load,
            uptime=uptime,
            timestamp=datetime.datetime.fromtimestamp(timestamp),
        )

    def to_bytes(self):
        return (
            struct.pack(">Q", self.memory_used)
            + struct.pack(">Q", self.memory_total)
            + struct.pack(">Q", self.swap_used)
            + struct.pack(">Q", self.swap_total)
            + struct.pack(">ddd", *self.cpu_load)
            + struct.pack(">Q", self.uptime)
            + struct.pack(">q", self.timestamp.timestamp())
        )


class Engine(BaseModel):
    driver_demand: int
    actual_engine: int
    rpm: int = Field(default=0, ge=0, le=8000)

    def from_bytes(data):
        driver_demand = data[0]
        actual_engine = data[1]
        rpm = struct.unpack(">H", data[2:4])[0]

        return Engine(driver_demand=driver_demand, actual_engine=actual_engine, rpm=rpm)

    def to_bytes(self):
        return bytes([self.driver_demand, self.actual_engine]) + struct.pack(
            ">H", self.rpm
        )


class Gnss(BaseModel):
    location: tuple[float, float]
    altitude: float
    speed: float
    heading: float
    satellites: int

    def from_bytes(data):
        location = struct.unpack("ff", data[:8])
        altitude, speed, heading = struct.unpack("fff", data[8:20])
        satellites = struct.unpack("B", data[20:21])

        return Gnss(
            location=location,
            altitude=altitude,
            speed=speed,
            heading=heading,
            satellites=satellites[0],
        )

    def to_bytes(self):
        return (
            struct.pack("ff", *self.location)
            + struct.pack("fff", self.altitude, self.speed, self.heading)
            + struct.pack("B", self.satellites)
        )

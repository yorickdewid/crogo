import socket
import struct
import time
import uuid
import logging
from random import randbytes
from enum import Enum
from time import sleep

logger = logging.getLogger(__name__)


class StatusType(Enum):
    HEALTHY = 0xF8
    DEGRADED = 0xF9
    FAULTY = 0xFA
    EMERGENCY = 0xFB

    def __str__(self):
        if self == StatusType.HEALTHY:
            return "healthy"
        elif self == StatusType.DEGRADED:
            return "degraded"
        elif self == StatusType.FAULTY:
            return "faulty"
        elif self == StatusType.EMERGENCY:
            return "emergency"


class MachineType(Enum):
    EXCAVATOR = 1
    WHEEL_LOADER = 2
    DOZER = 3
    GRADER = 4
    HAULER = 5
    FORESTRY = 6

    def __str__(self):
        if self == MachineType.EXCAVATOR:
            return "excavator"
        elif self == MachineType.WHEEL_LOADER:
            return "wheel loader"
        elif self == MachineType.DOZER:
            return "dozer"
        elif self == MachineType.GRADER:
            return "grader"
        elif self == MachineType.HAULER:
            return "hauler"
        elif self == MachineType.FORESTRY:
            return "forestry"


class MessageType(Enum):
    ERROR = 0x00
    ECHO = 0x01
    SESSION = 0x10
    SHUTDOWN = 0x11
    REQUEST = 0x12
    INSTANCE = 0x15
    STATUS = 0x16
    MOTION = 0x20
    SIGNAL = 0x31
    ACTOR = 0x40
    VMS = 0x41
    GNSS = 0x42
    ENGINE = 0x43
    TARGET = 0x44
    CONTROL = 0x45


class Packet:
    def to_bytes(self):
        pass

    def from_bytes(data):
        pass


class Echo(Packet):
    def __init__(self):
        self.data = randbytes(4)

    def to_bytes(self):
        return self.data

    def from_bytes(data):
        echo = Echo()
        echo.data = data
        return echo

    def __eq__(self, __value: object) -> bool:
        return self.data == __value.data


class Session(Packet):
    def __init__(self, name):
        self.name = name

    def to_bytes(self):
        data = struct.pack("B", 3)
        data += self.name.encode("utf-8")

        return data

    def from_bytes(data):
        name = data[1:].decode("utf-8")
        return Session(name)


class Request(Packet):
    def __init__(self, type):
        self.type = type

    def to_bytes(self):
        return struct.pack("B", self.type.value)

    def from_bytes(data):
        return Request(MessageType(data[0]))


class ModuleStatus(Packet):
    def __init__(self, name, state, error_code):
        self.name = name
        self.state = state
        self.error_code = error_code

    def to_bytes(self):
        return struct.pack("B", self.type.value)

    def from_bytes(data):
        name_length = struct.unpack(">H", data[0:2])[0]
        name = data[2 : 2 + name_length].decode("utf-8")

        state = data[2 + name_length]
        error_code = data[3 + name_length]

        return ModuleStatus(name, state, error_code)

    def __str__(self):
        return f"Name: {self.name}, State: {self.state}, Error code: {self.error_code}"


class Instance(Packet):
    def __init__(self, id, model, machine_type, version, serial_number):
        self.id = id
        self.model = model
        self.machine_type = machine_type
        self.version = version
        self.serial_number = serial_number

    def to_bytes(self):
        data = self.id.bytes
        data += struct.pack("B", self.machine_type.value)
        data += struct.pack("BBB", *self.version)
        data += struct.pack(">H", len(self.model))
        data += self.model.encode("utf-8")

        return data

    def from_bytes(data):
        id = uuid.UUID(bytes=data[:16])
        machine_type = MachineType(data[16])
        version = struct.unpack("BBB", data[17:20])

        model_length = struct.unpack(">H", data[20:22])[0]
        model = data[22 : 22 + model_length].decode("utf-8")

        serial_number_length = struct.unpack(
            ">H", data[22 + model_length : 24 + model_length]
        )[0]
        serial_number = data[
            24 + model_length : 24 + model_length + serial_number_length
        ].decode("utf-8")

        return Instance(id, model, machine_type, version, serial_number)

    def __str__(self):
        return f"ID: {self.id}, Model: {self.model}, Type: {self.machine_type}, Version: {self.version[0]}.{self.version[1]}.{self.version[2]}, Serial number: {self.serial_number}"


class VMS(Packet):
    def __init__(self, memory, swap, cpu_load, uptime, timestamp):
        self.memory = memory
        self.swap = swap
        self.cpu_load = cpu_load
        self.uptime = uptime
        self.timestamp = timestamp

    def to_bytes(self):
        data = struct.pack(">QQ", *self.memory)
        data += struct.pack(">QQ", *self.swap)
        data += struct.pack(">ddd", *self.cpu_load)
        data += struct.pack(">Q", self.uptime)
        data += struct.pack(">q", self.timestamp)

        return data

    def from_bytes(data):
        memory = struct.unpack(">QQ", data[:16])
        swap = struct.unpack(">QQ", data[16:32])
        cpu_load = struct.unpack(">ddd", data[32:56])
        uptime = struct.unpack(">Q", data[56:64])[0]
        timestamp = struct.unpack(">q", data[64:72])[0]

        return VMS(memory, swap, cpu_load, uptime, timestamp)

    def __str__(self):
        memory_used = self.memory[0] / 1024 / 1024 / 1024
        memory_total = self.memory[1] / 1024 / 1024 / 1024
        swap_used = self.swap[0] / 1024 / 1024 / 1024
        swap_total = self.swap[1] / 1024 / 1024 / 1024
        return f"Memory usage: {memory_used:.2f}GB / {memory_total:.2f}GB, Swap usage: {swap_used:.2f}GB / {swap_total:.2f}GB, CPU load: {self.cpu_load[0]:.1f}% {self.cpu_load[1]:.1f}%, {self.cpu_load[2]:.1f}%, Uptime: {self.uptime}s, Timestamp: {self.timestamp}"


class Engine(Packet):
    def __init__(self, driver_demand, actual_engine, rpm):
        self.driver_demand = driver_demand
        self.actual_engine = actual_engine
        self.rpm = rpm
        # self.status = status

    def to_bytes(self):
        data = struct.pack("BB", self.driver_demand, self.actual_engine)
        data += struct.pack(">H", self.rpm)
        data += struct.pack("B", self.status.value)

        return data

    def from_bytes(data):
        driver_demand = data[0]
        actual_engine = data[1]
        rpm = struct.unpack(">H", data[2:4])[0]
        # status = EngineStatus(data[4])

        return Engine(driver_demand, actual_engine, rpm)

    def __str__(self):
        return f"Driver demand: {self.driver_demand}%, Actual engine: {self.actual_engine}%, RPM: {self.rpm}"


class Control(Packet):
    class ControlType(Enum):
        ENGINE_REQUEST = 0x01
        ENGINE_SHUTDOWN = 0x02
        HYDRAULIC_QUICK_DISCONNECT = 0x5
        HYDRAULIC_LOCK = 0x6
        MACHINE_SHUTDOWN = 0x1B
        MACHINE_ILLUMINATION = 0x1C
        MACHINE_LIGHTS = 0x2D
        MACHINE_HORN = 0x1E

    def __init__(self, type, value):
        self.type = type
        self.value = value

    def to_bytes(self):
        data = struct.pack("B", self.type.value)
        if self.type == Control.ControlType.ENGINE_REQUEST:
            data += struct.pack(">H", self.value)
        elif self.type == Control.ControlType.HYDRAULIC_QUICK_DISCONNECT:
            data += struct.pack("B", self.value)
        elif self.type == Control.ControlType.HYDRAULIC_LOCK:
            data += struct.pack("B", self.value)
        elif self.type == Control.ControlType.MACHINE_ILLUMINATION:
            data += struct.pack("B", self.value)
        elif self.type == Control.ControlType.MACHINE_LIGHTS:
            data += struct.pack("B", self.value)
        elif self.type == Control.ControlType.MACHINE_HORN:
            data += struct.pack("B", self.value)

        return data

    def from_bytes(data):
        type = Control.ControlType(data[0])
        if type == Control.ControlType.ENGINE_REQUEST:
            value = struct.unpack(">H", data[1:3])[0]
        elif type == Control.ControlType.HYDRAULIC_QUICK_DISCONNECT:
            value = bool(data[1])
        elif type == Control.ControlType.HYDRAULIC_LOCK:
            value = bool(data[1])
        elif type == Control.ControlType.MACHINE_ILLUMINATION:
            value = bool(data[1])
        elif type == Control.ControlType.MACHINE_LIGHTS:
            value = bool(data[1])
        elif type == Control.ControlType.MACHINE_HORN:
            value = bool(data[1])
        return Control(type, value)


class Gnss(Packet):
    def __init__(self, location, altitude, speed, heading, satellites):
        self.location = location
        self.altitude = altitude
        self.speed = speed
        self.heading = heading
        self.satellites = satellites
        # self.status = status

    def to_bytes(self):
        data = struct.pack("ff", *self.location)
        data += struct.pack("ff", self.altitude, self.speed, self.heading)
        data += struct.pack("B", self.satellites)
        # data += struct.pack("BB", self.satellites, self.status.value)

        return data

    def from_bytes(data):
        location = struct.unpack("ff", data[:8])
        altitude, speed, heading = struct.unpack("fff", data[8:20])
        satellites = struct.unpack("B", data[20:21])

        return Gnss(location, altitude, speed, heading, satellites[0])

    def __str__(self):
        return f"Location: {self.location}, Altitude: {self.altitude}, Speed: {self.speed}, Heading: {self.heading}, Satellites: {self.satellites}"


class Frame:
    def parse(data):
        if data[:3] != b"LXR":
            print("Invalid header received")
            return

        if data[3:4] != b"\x02":
            print("Invalid protocol version")
            return

        message_type = MessageType(struct.unpack("B", data[4:5])[0])
        message_length = struct.unpack(">H", data[5:7])[0]

        if data[7:10] != b"\x00\x00\x00":
            print("Invalid message checksum")
            return

        return message_type, message_length

    def parse_message(data, message_type):
        if message_type == MessageType.STATUS:
            status_value = struct.unpack("B", data[:1])[0]
            status = Status(status_value)
            return status

        elif message_type == MessageType.VMS:
            memory = struct.unpack(">QQ", data[:16])
            swap = struct.unpack(">QQ", data[16:32])
            cpu_load = struct.unpack(">ddd", data[32:56])
            uptime = struct.unpack(">Q", data[56:64])
            timestamp = struct.unpack(">q", data[64:72])

            return memory, swap, cpu_load, uptime, timestamp

    def _header(type, length):
        header = b"LXR\x02"
        header += struct.pack("B", type.value)
        header += struct.pack(">H", length)
        header += b"\x00\x00\x00"
        return header

    def status(status):
        header = Frame._header(MessageType.STATUS, 1)
        return header + struct.pack("B", status.value)


class Client:
    def __init__(self, server_ip, server_port, user_agent="pyglonax/0.2"):
        self.server_ip = server_ip
        self.server_port = server_port
        self.user_agent = user_agent

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        logger.debug(f"Connecting to {self.server_ip}:{self.server_port}")

        self.sock.connect((self.server_ip, self.server_port))

        logger.debug("Connected to the Glonax server")

        self._handshake()

    def send(self, type, data):
        header = b"LXR\x03"
        header += struct.pack("B", type.value)
        header += struct.pack(">H", len(data))

        header += b"\x00\x00\x00"

        self.sock.sendall(header + data)

    def recv(self):
        header = self.sock.recv(10)

        if header[:3] != b"LXR":
            print("Invalid header received")
            return

        if header[3:4] != b"\x03":
            print("Invalid protocol version")
            return

        message_type = MessageType(struct.unpack("B", header[4:5])[0])
        message_length = struct.unpack(">H", header[5:7])[0]

        if header[7:10] != b"\x00\x00\x00":
            print("Invalid header padding")
            return

        message = self.sock.recv(message_length)

        if len(message) != message_length:
            print("Invalid message length")
            return

        return message_type, message

    def _probe(self):
        """
        Sends an echo message to the server and measures the elapsed time for the response.

        Returns:
            float: The elapsed time in seconds.
        """
        snd_echo = Echo()
        start_time = time.time()
        self.send(MessageType.ECHO, snd_echo.to_bytes())

        message_type, message = self.recv()
        end_time = time.time()
        if message_type == MessageType.ECHO:
            rcv_echo = Echo.from_bytes(message)
            if snd_echo != rcv_echo:
                print("Invalid echo response from server")

        elapsed_time = end_time - start_time
        return elapsed_time

    def _handshake(self):
        """
        Performs the handshake process with the Glonax server.

        This method sends a session message to the server and receives the response.
        If the response is an instance message, it sets the `machine` attribute of the client.

        Raises:
            SomeException: If an error occurs during the handshake process.
        """
        self._probe()

        session = Session(self.user_agent)
        self.send(MessageType.SESSION, session.to_bytes())

        message_type, message = self.recv()
        if message_type == MessageType.INSTANCE:
            self.machine = Instance.from_bytes(message)

            logger.debug(f"Instance ID: {self.machine.id}")
            logger.debug(f"Instance model: {self.machine.model}")
            logger.debug(f"Instance type: {self.machine.machine_type}")
            logger.debug(
                f"Instance version: {self.machine.version[0]}.{self.machine.version[1]}.{self.machine.version[2]}"
            )
            logger.debug(f"Instance serial number: {self.machine.serial_number}")

    # def status(self):
    #     self.send(MessageType.REQUEST, Request(MessageType.STATUS).to_bytes())

    #     message_type, message = self.recv()
    #     if message_type == MessageType.STATUS:
    #         return Status.from_bytes(message)
    #     raise Exception("Invalid message type received")

    # def vms(self):
    #     self.send(MessageType.REQUEST, Request(MessageType.VMS).to_bytes())

    #     message_type, message = self.recv()
    #     if message_type == MessageType.VMS:
    #         return VMS.from_bytes(message)
    #     raise Exception("Invalid message type received")

    # def engine(self):
    #     self.send(MessageType.REQUEST, Request(MessageType.ENGINE).to_bytes())

    #     message_type, message = self.recv()
    #     if message_type == MessageType.ENGINE:
    #         return Engine.from_bytes(message)
    #     raise Exception("Invalid message type received")

    # def gnss(self):
    #     self.send(MessageType.REQUEST, Request(MessageType.GNSS).to_bytes())

    #     message_type, message = self.recv()
    #     if message_type == MessageType.GNSS:
    #         return Gnss.from_bytes(message)
    #     raise Exception("Invalid message type received")

    def horn(self, value: bool):
        """
        Sends a control message to activate the machine horn.

        Args:
            value (bool): The value to set the machine horn.
        """
        self.send(
            MessageType.CONTROL,
            Control(Control.ControlType.MACHINE_HORN, value).to_bytes(),
        )

    def lights(self, value: bool):
        """
        Sends a control message to activate the machine lights.

        Args:
            value (bool): The value to set the machine lights.
        """
        self.send(
            MessageType.CONTROL,
            Control(Control.ControlType.MACHINE_LIGHTS, value).to_bytes(),
        )

    def illumination(self, value: bool):
        """
        Controls the machine illumination.

        Args:
            value (bool): The value to set for the machine illumination. True to turn on the illumination, False to turn it off.
        """
        self.send(
            MessageType.CONTROL,
            Control(Control.ControlType.MACHINE_ILLUMINATION, value).to_bytes(),
        )

    def shutdown(self):
        self.send(
            MessageType.CONTROL,
            Control(Control.ControlType.MACHINE_SHUTDOWN, 0).to_bytes(),
        )

    def hydraulic_lock(self, value: bool):
        self.send(
            MessageType.CONTROL,
            Control(Control.ControlType.HYDRAULIC_LOCK, value).to_bytes(),
        )

    def hydraulic_quick_disconnect(self, value: bool):
        self.send(
            MessageType.CONTROL,
            Control(Control.ControlType.HYDRAULIC_QUICK_DISCONNECT, value).to_bytes(),
        )

    def engine_request(self, value: int):
        self.send(
            MessageType.CONTROL,
            Control(Control.ControlType.ENGINE_REQUEST, value).to_bytes(),
        )

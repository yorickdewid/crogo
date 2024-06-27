import datetime
import socket
import struct
import time
import uuid
import logging
from enum import Enum
from time import sleep
from typing import Any, Callable
from abc import abstractmethod
from random import randbytes


logger = logging.getLogger(__name__)


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
    ROTATOR = 0x46


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


class TcpConnection:
    def __init__(
        self,
        address: str = "localhost",
        port: str | int = 30051,
        on_connect: Callable[[Any], None] | None = None,
    ):
        self.server_ip = address
        self.server_port = port

        self.on_connect = on_connect

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        logger.debug(f"Connecting to {self.server_ip}:{self.server_port}")

        self.sock.connect((self.server_ip, self.server_port))

        logger.debug("Connected to the Glonax server")

        if self.on_connect:
            self.on_connect()

    def send(self, type, data):
        header = b"LXR\x03"
        header += struct.pack("B", type.value)
        header += struct.pack(">H", len(data))

        header += b"\x00\x00\x00"

        self.sock.sendall(header + data)

    def recv(self) -> tuple[MessageType, bytes]:
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


from glonax.message import Instance, ModuleStatus, VMS, Engine, Gnss


APPLICATION_TYPES = [
    MessageType.STATUS,
    MessageType.MOTION,
    MessageType.VMS,
    MessageType.GNSS,
    MessageType.ENGINE,
    MessageType.TARGET,
    MessageType.CONTROL,
    MessageType.ROTATOR,
]


class GlonaxClient:
    def __init__(
        self,
        address: str = "localhost",
        port: str | int = 30051,
        user_agent: str = "pyglonax/0.2",
        on_connect: Callable[[Any], None] | None = None,
        on_reconnect: Callable[[Any], None] | None = None,
        on_message: Callable[[Any, MessageType, bytes], None] | None = None,
        on_error: Callable[[Any, Any], None] | None = None,
        on_close: Callable[[Any, Any], None] | None = None,
    ):
        self.server_ip = address
        self.server_port = port
        self.user_agent = user_agent

        self.on_connect = on_connect
        self.on_reconnect = on_reconnect
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close

        self.conn = TcpConnection(
            address=address,
            port=port,
            on_connect=self._on_connect,
        )
        self.conn.connect()

    def _on_connect(self):
        latency = self.probe()
        logger.debug(f"Conection latency: {latency:.2f} seconds")

        self._handshake()

        if self.on_connect:
            self.on_connect(self)

    def ping(self) -> float:
        """
        Sends an echo message to the server and measures the elapsed time for the response.

        Returns:
            float: The elapsed time in milliseconds.
        """
        return self.probe()

    def probe(self) -> float:
        """
        Sends an echo message to the server and measures the elapsed time for the response.

        Returns:
            float: The elapsed time in milliseconds.
        """
        snd_echo = Echo()
        start_time = time.time()
        self.conn.send(MessageType.ECHO, snd_echo.to_bytes())

        message_type, message = self.conn.recv()
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
        session = Session(self.user_agent)
        self.conn.send(MessageType.SESSION, session.to_bytes())

        message_type, message = self.conn.recv()
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
        self.conn.send(
            MessageType.CONTROL,
            Control(Control.ControlType.MACHINE_HORN, value).to_bytes(),
        )

    def lights(self, value: bool):
        """
        Sends a control message to activate the machine lights.

        Args:
            value (bool): The value to set the machine lights.
        """
        self.conn.send(
            MessageType.CONTROL,
            Control(Control.ControlType.MACHINE_LIGHTS, value).to_bytes(),
        )

    def illumination(self, value: bool):
        """
        Controls the machine illumination.

        Args:
            value (bool): The value to set for the machine illumination. True to turn on the illumination, False to turn it off.
        """
        self.conn.send(
            MessageType.CONTROL,
            Control(Control.ControlType.MACHINE_ILLUMINATION, value).to_bytes(),
        )

    def hydraulic_lock(self, value: bool):
        self.conn.send(
            MessageType.CONTROL,
            Control(Control.ControlType.HYDRAULIC_LOCK, value).to_bytes(),
        )

    def hydraulic_quick_disconnect(self, value: bool):
        self.conn.send(
            MessageType.CONTROL,
            Control(Control.ControlType.HYDRAULIC_QUICK_DISCONNECT, value).to_bytes(),
        )

    # TODO: Implementaton is invalid
    def engine_request(self, value: int):
        self.conn.send(
            MessageType.CONTROL,
            Control(Control.ControlType.ENGINE_REQUEST, value).to_bytes(),
        )

    def listen(
        self, on_message: Callable[[Any, MessageType, bytes], None] | None = None
    ):
        if on_message:
            self.on_message = on_message

        while True:
            message_type, message = self.conn.recv()

            if message_type in APPLICATION_TYPES:
                if self.on_message:
                    self.on_message(self, message_type, message)


# TODO: Rename to ServiceBase, move to a separate file
class GlonaxServiceBase:
    def __call__(self, client, message_type, message):
        if message_type == MessageType.STATUS:
            status = ModuleStatus.from_bytes(message)
            self.on_status(client, status)
        elif message_type == MessageType.VMS:
            vms = VMS.from_bytes(message)
            self.on_vms(client, vms)
        elif message_type == MessageType.ENGINE:
            engine = Engine.from_bytes(message)
            self.on_engine(client, engine)
        elif message_type == MessageType.GNSS:
            gnss = Gnss.from_bytes(message)
            self.on_gnss(client, gnss)

    @abstractmethod
    def on_status(self, client: GlonaxClient, status: ModuleStatus):
        pass

    @abstractmethod
    def on_motion(
        self,
        client: GlonaxClient,
    ):
        pass

    @abstractmethod
    def on_vms(self, client: GlonaxClient, vms: VMS):
        pass

    @abstractmethod
    def on_gnss(self, client: GlonaxClient, gnss: Gnss):
        pass

    @abstractmethod
    def on_engine(self, client: GlonaxClient, engine: Engine):
        pass

    @abstractmethod
    def on_target(self, client: GlonaxClient, target):
        pass

    @abstractmethod
    def on_control(self, client: GlonaxClient):
        pass

    @abstractmethod
    def on_rotator(self, client: GlonaxClient):
        pass

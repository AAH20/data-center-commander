"""Read-only smart meter adapter for Modbus TCP, BACnet/IP, and SNMP.

Provides bounded, safe reads from energy meters without persistence or
actuation. All network operations use explicit timeouts and size limits.
No credentials or secrets are stored in source; connection parameters
are supplied by the caller (typically from a secret manager reference).
"""
from __future__ import annotations

import dataclasses
import ipaddress
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MeterAdapterError(Exception):
    """Base exception for meter adapter failures."""


class ConnectionError_(MeterAdapterError):
    """Network or protocol-level connection failure."""


class TimeoutError_(MeterAdapterError):
    """Operation exceeded the configured timeout."""


class ProtocolError_(MeterAdapterError):
    """Malformed or unexpected protocol response."""


class ValidationError_(MeterAdapterError):
    """Input validation failed before network access."""


class QualityStatus(str, Enum):
    """Reading quality classification."""

    GOOD = "good"
    ESTIMATED = "estimated"
    SUSPECT = "suspect"
    BAD = "bad"
    STALE = "stale"
    UNCALIBRATED = "uncalibrated"


@dataclass(frozen=True, slots=True)
class MeterReading:
    """A single bounded meter reading with provenance."""

    meter_id: str
    observed_at: str  # ISO 8601 UTC
    value: float
    unit: str
    quality: QualityStatus
    protocol: str
    source_address: str
    register_address: int | None = None
    oid: str | None = None
    raw_value: int | float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

_MAX_REGISTERS = 125          # Modbus limit per request
_MAX_OIDS = 50                # SNMP limit per request
_MAX_RESPONSE_BYTES = 65536  # Hard cap on any single response
_DEFAULT_TIMEOUT = 5.0       # seconds
_MAX_TIMEOUT = 30.0
_MIN_TIMEOUT = 0.1


def _validate_host(host: str) -> str:
    """Validate and normalize a hostname or IP address."""
    host = host.strip()
    if not host or len(host) > 253:
        raise ValidationError_("host must be 1-253 characters")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    # Allow simple hostnames
    if not all(c.isalnum() or c in ".-" for c in host):
        raise ValidationError_("host contains invalid characters")
    return host


def _validate_port(port: int) -> int:
    """Validate a TCP/UDP port number."""
    if not isinstance(port, int) or isinstance(port, bool):
        raise ValidationError_("port must be an integer")
    if not 1 <= port <= 65535:
        raise ValidationError_("port must be 1-65535")
    return port


def _validate_timeout(timeout: float) -> float:
    """Validate the network timeout."""
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise ValidationError_("timeout must be a number")
    timeout = float(timeout)
    if not _MIN_TIMEOUT <= timeout <= _MAX_TIMEOUT:
        raise ValidationError_(f"timeout must be {_MIN_TIMEOUT}-{_MAX_TIMEOUT} seconds")
    return timeout


def _validate_unit_id(unit_id: int) -> int:
    """Validate a Modbus unit ID (1-247)."""
    if not isinstance(unit_id, int) or isinstance(unit_id, bool):
        raise ValidationError_("unit_id must be an integer")
    if not 1 <= unit_id <= 247:
        raise ValidationError_("Modbus unit_id must be 1-247")
    return unit_id


def _validate_register(address: int) -> int:
    """Validate a Modbus register address (0-65535)."""
    if not isinstance(address, int) or isinstance(address, bool):
        raise ValidationError_("register address must be an integer")
    if not 0 <= address <= 65535:
        raise ValidationError_("register address must be 0-65535")
    return address


def _validate_oid(oid: str) -> str:
    """Validate an SNMP OID string."""
    oid = oid.strip()
    if not oid or len(oid) > 256:
        raise ValidationError_("OID must be 1-256 characters")
    parts = oid.lstrip(".").split(".")
    if not all(p.isdigit() for p in parts):
        raise ValidationError_("OID must contain only dot-separated integers")
    return oid


def _validate_meter_id(meter_id: str) -> str:
    """Validate a meter identifier."""
    meter_id = meter_id.strip()
    if not meter_id or len(meter_id) > 120:
        raise ValidationError_("meter_id must be 1-120 characters")
    return meter_id


# ---------------------------------------------------------------------------
# Modbus TCP
# ---------------------------------------------------------------------------

_MODBUS_TCP_PORT = 502
_MODBUS_READ_HOLDING = 0x03
_MODBUS_READ_INPUT = 0x04
_MODBUS_HEADER_SIZE = 7
_MODBUS_MAX_PDU = 253


def _modbus_crc16(data: bytes) -> int:
    """Compute Modbus CRC-16."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def _build_modbus_request(
    transaction_id: int,
    unit_id: int,
    function_code: int,
    start_address: int,
    quantity: int,
) -> bytes:
    """Build a Modbus TCP request frame."""
    pdu = struct.pack(">BHH", function_code, start_address, quantity)
    length = len(pdu) + 1  # +1 for unit ID in MBAP
    header = struct.pack(">HHHB", transaction_id, 0, length, unit_id)
    frame = header + pdu
    # For TCP, no CRC; the MBAP header handles framing
    return frame


def _parse_modbus_response(
    data: bytes,
    transaction_id: int,
    unit_id: int,
    function_code: int,
) -> list[int]:
    """Parse a Modbus TCP response and return register values."""
    if len(data) < _MODBUS_HEADER_SIZE:
        raise ProtocolError_("Modbus response too short")
    resp_tid, resp_pid, resp_len, resp_uid = struct.unpack(">HHHB", data[:7])
    if resp_tid != transaction_id:
        raise ProtocolError_("Modbus transaction ID mismatch")
    if resp_uid != unit_id:
        raise ProtocolError_("Modbus unit ID mismatch")
    if resp_len != len(data) - 6:
        raise ProtocolError_("Modbus length field mismatch")
    if len(data) < 9:
        raise ProtocolError_("Modbus response missing PDU")
    resp_fc = data[7]
    if resp_fc & 0x80:
        exception_code = data[8] if len(data) > 8 else 0
        raise ProtocolError_(f"Modbus exception 0x{exception_code:02X}")
    if resp_fc != function_code:
        raise ProtocolError_("Modbus function code mismatch")
    byte_count = data[8]
    if len(data) < 9 + byte_count:
        raise ProtocolError_("Modbus response truncated")
    registers = []
    for i in range(byte_count // 2):
        registers.append(struct.unpack(">H", data[9 + i * 2 : 11 + i * 2])[0])
    return registers


def _decode_register_value(
    registers: list[int],
    data_type: str,
    scale: float,
    unit: str,
) -> tuple[float, int | float]:
    """Decode raw register values into a scaled reading."""
    if data_type == "uint16":
        if len(registers) < 1:
            raise ProtocolError_("Insufficient registers for uint16")
        raw = registers[0]
        return raw * scale, raw
    if data_type == "int16":
        if len(registers) < 1:
            raise ProtocolError_("Insufficient registers for int16")
        raw = struct.unpack(">h", struct.pack(">H", registers[0]))[0]
        return raw * scale, raw
    if data_type == "uint32":
        if len(registers) < 2:
            raise ProtocolError_("Insufficient registers for uint32")
        raw = (registers[0] << 16) | registers[1]
        return raw * scale, raw
    if data_type == "int32":
        if len(registers) < 2:
            raise ProtocolError_("Insufficient registers for int32")
        raw = struct.unpack(">i", struct.pack(">HH", registers[0], registers[1]))[0]
        return raw * scale, raw
    if data_type == "float32":
        if len(registers) < 2:
            raise ProtocolError_("Insufficient registers for float32")
        raw = struct.unpack(">f", struct.pack(">HH", registers[0], registers[1]))[0]
        return raw * scale, raw
    raise ValidationError_(f"unsupported data_type: {data_type}")


def _read_modbus_tcp(
    *,
    host: str,
    port: int,
    unit_id: int,
    registers: list[dict[str, Any]],
    timeout: float,
) -> list[MeterReading]:
    """Read from a Modbus TCP meter. Read-only (function codes 0x03/0x04)."""
    if not registers:
        raise ValidationError_("at least one register mapping is required")
    if len(registers) > _MAX_REGISTERS:
        raise ValidationError_(f"at most {_MAX_REGISTERS} registers per request")

    # Validate all register parameters before any network access
    for reg in registers:
        _validate_register(reg["address"])
        fc = reg.get("function_code", _MODBUS_READ_HOLDING)
        if fc not in (_MODBUS_READ_HOLDING, _MODBUS_READ_INPUT):
            raise ValidationError_(f"unsupported Modbus function code: {fc}")
        data_type = reg.get("data_type", "uint16")
        if data_type not in ("uint16", "int16", "uint32", "int32", "float32"):
            raise ValidationError_(f"unsupported data_type: {data_type}")
        unit = str(reg.get("unit", "")).strip()
        if not unit:
            raise ValidationError_(f"register {reg['address']}: unit is required")
        meter_id = reg.get("meter_id", f"modbus-{unit_id}-{reg['address']}")
        _validate_meter_id(meter_id)

    # Group registers by function code and contiguous ranges
    holding_regs: dict[int, dict[str, Any]] = {}
    input_regs: dict[int, dict[str, Any]] = {}
    for reg in registers:
        addr = _validate_register(reg["address"])
        fc = reg.get("function_code", _MODBUS_READ_HOLDING)
        if fc == _MODBUS_READ_HOLDING:
            holding_regs[addr] = reg
        else:
            input_regs[addr] = reg

    readings: list[MeterReading] = []
    transaction_id = 1

    for fc, reg_map in ((_MODBUS_READ_HOLDING, holding_regs), (_MODBUS_READ_INPUT, input_regs)):
        if not reg_map:
            continue
        sorted_addrs = sorted(reg_map)
        # Build contiguous ranges
        ranges: list[tuple[int, int]] = []
        range_start = sorted_addrs[0]
        range_end = sorted_addrs[0]
        for addr in sorted_addrs[1:]:
            if addr == range_end + 1:
                range_end = addr
            else:
                ranges.append((range_start, range_end))
                range_start = addr
                range_end = addr
        ranges.append((range_start, range_end))

        for start_addr, end_addr in ranges:
            quantity = end_addr - start_addr + 1
            if quantity > _MAX_REGISTERS:
                raise ValidationError_(f"register range {start_addr}-{end_addr} exceeds {_MAX_REGISTERS} registers")

            request = _build_modbus_request(transaction_id, unit_id, fc, start_addr, quantity)
            transaction_id += 1

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                sock.connect((host, port))
                sock.sendall(request)
                # Read MBAP header first
                header = b""
                while len(header) < 7:
                    chunk = sock.recv(7 - len(header))
                    if not chunk:
                        raise ConnectionError_("Modbus TCP connection closed during header read")
                    header += chunk
                resp_tid, resp_pid, resp_len, resp_uid = struct.unpack(">HHHB", header)
                remaining = resp_len - 1
                body = b""
                while len(body) < remaining:
                    chunk = sock.recv(min(4096, remaining - len(body)))
                    if not chunk:
                        raise ConnectionError_("Modbus TCP connection closed during body read")
                    body += chunk
                response = header + body
                if len(response) > _MAX_RESPONSE_BYTES:
                    raise ProtocolError_("Modbus response exceeded size limit")
                raw_registers = _parse_modbus_response(response, resp_tid, unit_id, fc)
            except socket.timeout:
                raise TimeoutError_(f"Modbus TCP read from {host}:{port} timed out after {timeout}s") from None
            except OSError as exc:
                raise ConnectionError_(f"Modbus TCP connection to {host}:{port} failed: {exc}") from None
            finally:
                sock.close()

            # Map raw registers back to meter readings
            for i, addr in enumerate(range(start_addr, end_addr + 1)):
                if addr not in reg_map:
                    continue
                reg = reg_map[addr]
                data_type = reg.get("data_type", "uint16")
                scale = float(reg.get("scale", 1.0))
                unit = str(reg.get("unit", "")).strip()
                meter_id = _validate_meter_id(reg.get("meter_id", f"modbus-{unit_id}-{addr}"))
                if not unit:
                    raise ValidationError_(f"register {addr}: unit is required")

                # For multi-register types, we need the right slice
                type_registers = 2 if data_type in ("uint32", "int32", "float32") else 1
                reg_slice = raw_registers[i : i + type_registers]
                if len(reg_slice) < type_registers:
                    raise ProtocolError_(f"insufficient data for {data_type} at register {addr}")

                value, raw_value = _decode_register_value(reg_slice, data_type, scale, unit)
                quality = QualityStatus.GOOD
                if reg.get("stale_after_seconds"):
                    age = time.time() - reg.get("last_seen", time.time())
                    if age > reg["stale_after_seconds"]:
                        quality = QualityStatus.STALE

                readings.append(MeterReading(
                    meter_id=meter_id,
                    observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    value=round(value, 9),
                    unit=unit,
                    quality=quality,
                    protocol="modbus_tcp",
                    source_address=f"{host}:{port}",
                    register_address=addr,
                    raw_value=raw_value,
                    metadata={
                        "unit_id": unit_id,
                        "function_code": fc,
                        "data_type": data_type,
                        "scale": scale,
                    },
                ))

    return readings


# ---------------------------------------------------------------------------
# BACnet/IP
# ---------------------------------------------------------------------------

_BACNET_IP_PORT = 47808
_BACNET_BVLC_HEADER = 4
_BACNET_NPDU_HEADER = 2
_BACNET_APDU_MIN = 4
_BACNET_READ_PROPERTY = 0x0C
_BACNET_OBJECT_ANALOG_INPUT = 0
_BACNET_OBJECT_ANALOG_VALUE = 2
_BACNET_PROPERTY_PRESENT_VALUE = 85


def _build_bacnet_read_request(
    device_id: int,
    object_type: int,
    object_instance: int,
    property_id: int,
) -> bytes:
    """Build a BACnet/IP ReadProperty request."""
    # BVLC header
    bvlc = struct.pack(">BBBB", 0x81, 0x0B, 0x00, 0x00)  # BVLC type, function, length placeholder
    # NPDU
    npdu = struct.pack(">BB", 0x01, 0x00)  # Version, control
    # APDU: ReadProperty
    # PDX: 0x00 (no segmentation, max APDU 1476, invoke ID 1)
    apdu_header = struct.pack(">BBBB", 0x00, 0x05, 0x01, 0x00)
    # Object identifier: type (3 bits) + instance (21 bits)
    obj_id = (object_type << 22) | object_instance
    obj_id_bytes = struct.pack(">I", obj_id)
    # Property identifier: context tag 0, property ID
    prop_bytes = struct.pack(">BB", 0x09, property_id)  # context tag 0, length 1
    apdu = apdu_header + obj_id_bytes + prop_bytes
    # Update BVLC length
    total_len = len(bvlc) + len(npdu) + len(apdu)
    bvlc = struct.pack(">BBBB", 0x81, 0x0B, (total_len >> 8) & 0xFF, total_len & 0xFF)
    return bvlc + npdu + apdu


def _parse_bacnet_response(data: bytes, device_id: int) -> float:
    """Parse a BACnet/IP ReadProperty response and return the present value."""
    if len(data) < _BACNET_BVLC_HEADER + _BACNET_NPDU_HEADER + _BACNET_APDU_MIN:
        raise ProtocolError_("BACnet response too short")
    # Skip BVLC
    offset = _BACNET_BVLC_HEADER
    # NPDU
    if data[offset] != 0x01:
        raise ProtocolError_("BACnet NPDU version mismatch")
    offset += _BACNET_NPDU_HEADER
    # APDU: expect ComplexACK (0x30) for ReadProperty-ACK
    apdu_type = data[offset] >> 4
    if apdu_type != 0x03:  # ComplexACK
        raise ProtocolError_(f"BACnet APDU type {apdu_type} is not ComplexACK")
    offset += 1
    # Skip invoke ID and service choice
    offset += 2
    # Object identifier: context tag 0, length 4
    if data[offset] != 0x0C:
        raise ProtocolError_("BACnet object identifier tag mismatch")
    offset += 5
    # Property identifier: context tag 1, length 1
    if data[offset] != 0x19:
        raise ProtocolError_("BACnet property identifier tag mismatch")
    offset += 2
    # Opening tag for property value
    if data[offset] != 0x2E:
        raise ProtocolError_("BACnet opening tag expected")
    offset += 1
    # Real value: application tag 4, length 4
    if data[offset] != 0x44:
        raise ProtocolError_("BACnet real value tag expected")
    offset += 1
    value = struct.unpack(">f", data[offset : offset + 4])[0]
    return value


def _read_bacnet_ip(
    *,
    host: str,
    port: int,
    device_id: int,
    objects: list[dict[str, Any]],
    timeout: float,
) -> list[MeterReading]:
    """Read from a BACnet/IP meter. Read-only (ReadProperty service)."""
    if not objects:
        raise ValidationError_("at least one object mapping is required")
    if len(objects) > _MAX_OIDS:
        raise ValidationError_(f"at most {_MAX_OIDS} objects per request")

    readings: list[MeterReading] = []
    for obj in objects:
        obj_type = obj.get("object_type", _BACNET_OBJECT_ANALOG_INPUT)
        obj_instance = obj.get("instance")
        if not isinstance(obj_instance, int) or isinstance(obj_instance, bool):
            raise ValidationError_("BACnet object instance must be an integer")
        if obj_type not in (_BACNET_OBJECT_ANALOG_INPUT, _BACNET_OBJECT_ANALOG_VALUE):
            raise ValidationError_(f"unsupported BACnet object type: {obj_type}")

        meter_id = _validate_meter_id(obj.get("meter_id", f"bacnet-{device_id}-{obj_type}-{obj_instance}"))
        unit = str(obj.get("unit", "")).strip()
        if not unit:
            raise ValidationError_(f"BACnet object {obj_instance}: unit is required")
        scale = float(obj.get("scale", 1.0))

        request = _build_bacnet_read_request(device_id, obj_type, obj_instance, _BACNET_PROPERTY_PRESENT_VALUE)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(request, (host, port))
            data, _ = sock.recvfrom(_MAX_RESPONSE_BYTES)
            if len(data) > _MAX_RESPONSE_BYTES:
                raise ProtocolError_("BACnet response exceeded size limit")
            raw_value = _parse_bacnet_response(data, device_id)
        except socket.timeout:
            raise TimeoutError_(f"BACnet/IP read from {host}:{port} timed out after {timeout}s") from None
        except OSError as exc:
            raise ConnectionError_(f"BACnet/IP connection to {host}:{port} failed: {exc}") from None
        finally:
            sock.close()

        value = raw_value * scale
        quality = QualityStatus.GOOD
        if obj.get("stale_after_seconds"):
            age = time.time() - obj.get("last_seen", time.time())
            if age > obj["stale_after_seconds"]:
                quality = QualityStatus.STALE

        readings.append(MeterReading(
            meter_id=meter_id,
            observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            value=round(value, 9),
            unit=unit,
            quality=quality,
            protocol="bacnet_ip",
            source_address=f"{host}:{port}",
            oid=f"{obj_type}:{obj_instance}",
            raw_value=raw_value,
            metadata={
                "device_id": device_id,
                "object_type": obj_type,
                "object_instance": obj_instance,
                "property_id": _BACNET_PROPERTY_PRESENT_VALUE,
                "scale": scale,
            },
        ))

    return readings


# ---------------------------------------------------------------------------
# SNMP
# ---------------------------------------------------------------------------

_SNMP_PORT = 161
_SNMP_GET_REQUEST = 0xA0
_SNMP_GET_RESPONSE = 0xA2
_SNMP_OID_TAG = 0x06
_SNMP_INTEGER_TAG = 0x02
_SNMP_OCTET_STR_TAG = 0x04
_SNMP_COUNTER32_TAG = 0x41
_SNMP_COUNTER64_TAG = 0x46
_SNMP_GAUGE32_TAG = 0x42
_SNMP_TIMETICKS_TAG = 0x43
_SNMP_NULL_TAG = 0x05
_SNMP_NO_SUCH_OBJECT = 0x80
_SNMP_NO_SUCH_INSTANCE = 0x81
_SNMP_END_OF_MIB_VIEW = 0x82


def _snmp_encode_length(length: int) -> bytes:
    """Encode an SNMP length field."""
    if length < 128:
        return bytes([length])
    if length < 256:
        return bytes([0x81, length])
    return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])


def _snmp_encode_oid(oid: str) -> bytes:
    """Encode an OID into SNMP format."""
    parts = [int(p) for p in oid.lstrip(".").split(".")]
    if len(parts) < 2:
        raise ValidationError_("OID must have at least two components")
    # First two components encoded as 40*first + second
    encoded = bytes([40 * parts[0] + parts[1]])
    for part in parts[2:]:
        if part < 0:
            raise ValidationError_("OID components must be non-negative")
        if part < 128:
            encoded += bytes([part])
        else:
            # Multi-byte encoding
            bytes_list = []
            temp = part
            while temp:
                bytes_list.insert(0, (temp & 0x7F) | 0x80)
                temp >>= 7
            bytes_list[-1] &= 0x7F
            encoded += bytes(bytes_list)
    return encoded


def _snmp_build_get_request(
    request_id: int,
    community: str,
    oids: list[str],
) -> bytes:
    """Build an SNMPv1 GetRequest PDU."""
    # Varbind list
    varbind_list = b""
    for oid in oids:
        oid_bytes = _snmp_encode_oid(oid)
        # Varbind: OID + NULL value
        varbind = bytes([_SNMP_OID_TAG]) + _snmp_encode_length(len(oid_bytes)) + oid_bytes
        varbind += bytes([_SNMP_NULL_TAG, 0x00])
        varbind_list += bytes([_SNMP_OID_TAG]) + _snmp_encode_length(len(varbind)) + varbind

    # PDU: GetRequest
    pdu_content = struct.pack(">I", request_id) + b"\x00\x02\x01\x00" + b"\x00\x02\x01\x00"  # request ID, error status, error index
    pdu_content += bytes([_SNMP_OID_TAG]) + _snmp_encode_length(len(varbind_list)) + varbind_list
    pdu = bytes([_SNMP_GET_REQUEST]) + _snmp_encode_length(len(pdu_content)) + pdu_content

    # Community string
    comm_bytes = community.encode("utf-8")
    comm_field = bytes([_SNMP_OCTET_STR_TAG]) + _snmp_encode_length(len(comm_bytes)) + comm_bytes

    # Version: SNMPv1 = 0
    version_field = bytes([_SNMP_INTEGER_TAG, 0x01, 0x00])

    # Message: version + community + PDU
    message_content = version_field + comm_field + pdu
    message = bytes([0x30]) + _snmp_encode_length(len(message_content)) + message_content
    return message


def _snmp_parse_response(data: bytes) -> list[tuple[str, Any]]:
    """Parse an SNMP response and return (OID, value) pairs."""
    if len(data) < 10:
        raise ProtocolError_("SNMP response too short")
    offset = 0
    # SEQUENCE
    if data[offset] != 0x30:
        raise ProtocolError_("SNMP response: expected SEQUENCE")
    offset += 1
    # Length
    if data[offset] & 0x80:
        length_bytes = data[offset] & 0x7F
        offset += 1 + length_bytes
    else:
        offset += 1
    # Version: INTEGER TLV
    if data[offset] != _SNMP_INTEGER_TAG:
        raise ProtocolError_("SNMP response: expected INTEGER for version")
    offset += 1
    ver_len = data[offset]
    offset += 1 + ver_len
    # Community: OCTET STRING TLV
    if data[offset] != _SNMP_OCTET_STR_TAG:
        raise ProtocolError_("SNMP response: expected OCTET STRING for community")
    offset += 1
    comm_len = data[offset]
    offset += 1 + comm_len
    # PDU
    if data[offset] != _SNMP_GET_RESPONSE:
        raise ProtocolError_("SNMP response: expected GetResponse PDU")
    offset += 1
    # PDU length
    if data[offset] & 0x80:
        length_bytes = data[offset] & 0x7F
        pdu_len = int.from_bytes(data[offset + 1 : offset + 1 + length_bytes], "big")
        offset += 1 + length_bytes
    else:
        pdu_len = data[offset]
        offset += 1
    pdu_end = offset + pdu_len
    # Request ID: INTEGER TLV
    if data[offset] != _SNMP_INTEGER_TAG:
        raise ProtocolError_("SNMP response: expected INTEGER for request ID")
    offset += 1
    req_id_len = data[offset]
    offset += 1 + req_id_len
    # Error status: INTEGER TLV
    if data[offset] != _SNMP_INTEGER_TAG:
        raise ProtocolError_("SNMP response: expected INTEGER for error status")
    offset += 1
    err_status_len = data[offset]
    offset += 1
    error_status = int.from_bytes(data[offset : offset + err_status_len], "big")
    offset += err_status_len
    if error_status != 0:
        raise ProtocolError_(f"SNMP error status: {error_status}")
    # Error index: INTEGER TLV
    if data[offset] != _SNMP_INTEGER_TAG:
        raise ProtocolError_("SNMP response: expected INTEGER for error index")
    offset += 1
    err_idx_len = data[offset]
    offset += 1 + err_idx_len
    # Varbind list: SEQUENCE of VarBind
    if data[offset] != 0x30:
        raise ProtocolError_("SNMP response: expected SEQUENCE for varbind list")
    offset += 1
    if data[offset] & 0x80:
        length_bytes = data[offset] & 0x7F
        offset += 1 + length_bytes
    else:
        offset += 1

    results: list[tuple[str, Any]] = []
    while offset < pdu_end:
        if data[offset] != 0x30:
            raise ProtocolError_("SNMP response: expected SEQUENCE for varbind")
        offset += 1
        if data[offset] & 0x80:
            length_bytes = data[offset] & 0x7F
            vb_len = int.from_bytes(data[offset + 1 : offset + 1 + length_bytes], "big")
            offset += 1 + length_bytes
        else:
            vb_len = data[offset]
            offset += 1
        vb_end = offset + vb_len
        # OID
        if data[offset] != _SNMP_OID_TAG:
            raise ProtocolError_("SNMP response: expected OBJECT IDENTIFIER")
        offset += 1
        oid_len = data[offset]
        offset += 1
        oid_bytes = data[offset : offset + oid_len]
        offset += oid_len
        # Decode OID
        if len(oid_bytes) < 1:
            raise ProtocolError_("SNMP response: empty OID")
        first = oid_bytes[0]
        oid_parts = [first // 40, first % 40]
        i = 1
        while i < len(oid_bytes):
            value = 0
            while i < len(oid_bytes) and oid_bytes[i] & 0x80:
                value = (value << 7) | (oid_bytes[i] & 0x7F)
                i += 1
            if i < len(oid_bytes):
                value = (value << 7) | oid_bytes[i]
                i += 1
            oid_parts.append(value)
        oid_str = ".".join(str(p) for p in oid_parts)
        # Value
        value_tag = data[offset]
        offset += 1
        # Read length (short or long form)
        if data[offset] & 0x80:
            length_bytes = data[offset] & 0x7F
            offset += 1
            value_len = int.from_bytes(data[offset : offset + length_bytes], "big")
            offset += length_bytes
        else:
            value_len = data[offset]
            offset += 1
        value_bytes = data[offset : offset + value_len]
        offset += value_len

        if value_tag == _SNMP_NULL_TAG:
            results.append((oid_str, None))
        elif value_tag == _SNMP_NO_SUCH_OBJECT:
            results.append((oid_str, None))
        elif value_tag == _SNMP_NO_SUCH_INSTANCE:
            results.append((oid_str, None))
        elif value_tag == _SNMP_END_OF_MIB_VIEW:
            results.append((oid_str, None))
        elif value_tag == _SNMP_INTEGER_TAG:
            results.append((oid_str, int.from_bytes(value_bytes, "big", signed=True)))
        elif value_tag == _SNMP_COUNTER32_TAG:
            results.append((oid_str, int.from_bytes(value_bytes, "big")))
        elif value_tag == _SNMP_COUNTER64_TAG:
            results.append((oid_str, int.from_bytes(value_bytes, "big")))
        elif value_tag == _SNMP_GAUGE32_TAG:
            results.append((oid_str, int.from_bytes(value_bytes, "big")))
        elif value_tag == _SNMP_TIMETICKS_TAG:
            results.append((oid_str, int.from_bytes(value_bytes, "big")))
        elif value_tag == _SNMP_OCTET_STR_TAG:
            results.append((oid_str, value_bytes.decode("utf-8", errors="replace")))
        else:
            results.append((oid_str, value_bytes.hex()))
        offset = vb_end

    return results


def _read_snmp(
    *,
    host: str,
    port: int,
    community: str,
    oids: list[dict[str, Any]],
    timeout: float,
) -> list[MeterReading]:
    """Read from an SNMP meter. Read-only (GetRequest)."""
    if not community or len(community) > 128:
        raise ValidationError_("SNMP community string must be 1-128 characters")
    if not oids:
        raise ValidationError_("at least one OID mapping is required")
    if len(oids) > _MAX_OIDS:
        raise ValidationError_(f"at most {_MAX_OIDS} OIDs per request")

    oid_list = [_validate_oid(o["oid"]) for o in oids]
    request = _snmp_build_get_request(1, community, oid_list)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(request, (host, port))
        data, _ = sock.recvfrom(_MAX_RESPONSE_BYTES)
        if len(data) > _MAX_RESPONSE_BYTES:
            raise ProtocolError_("SNMP response exceeded size limit")
        results = _snmp_parse_response(data)
    except socket.timeout:
        raise TimeoutError_(f"SNMP read from {host}:{port} timed out after {timeout}s") from None
    except OSError as exc:
        raise ConnectionError_(f"SNMP connection to {host}:{port} failed: {exc}") from None
    finally:
        sock.close()

    readings: list[MeterReading] = []
    for i, (oid_str, raw_value) in enumerate(results):
        if raw_value is None:
            continue
        oid_cfg = oids[i]
        meter_id = _validate_meter_id(oid_cfg.get("meter_id", f"snmp-{oid_str}"))
        unit = str(oid_cfg.get("unit", "")).strip()
        if not unit:
            raise ValidationError_(f"OID {oid_str}: unit is required")
        scale = float(oid_cfg.get("scale", 1.0))

        if isinstance(raw_value, (int, float)):
            value = float(raw_value) * scale
        else:
            # Try to parse string values
            try:
                value = float(raw_value) * scale
            except (ValueError, TypeError):
                raise ProtocolError_(f"OID {oid_str}: cannot parse value {raw_value!r}")

        quality = QualityStatus.GOOD
        if oid_cfg.get("stale_after_seconds"):
            age = time.time() - oid_cfg.get("last_seen", time.time())
            if age > oid_cfg["stale_after_seconds"]:
                quality = QualityStatus.STALE

        readings.append(MeterReading(
            meter_id=meter_id,
            observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            value=round(value, 9),
            unit=unit,
            quality=quality,
            protocol="snmp",
            source_address=f"{host}:{port}",
            oid=oid_str,
            raw_value=raw_value,
            metadata={
                "scale": scale,
                "value_type": type(raw_value).__name__,
            },
        ))

    return readings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_meter_data(
    *,
    protocol: str,
    host: str,
    port: int | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
    # Modbus parameters
    unit_id: int | None = None,
    registers: list[dict[str, Any]] | None = None,
    # BACnet parameters
    device_id: int | None = None,
    objects: list[dict[str, Any]] | None = None,
    # SNMP parameters
    community: str | None = None,
    oids: list[dict[str, Any]] | None = None,
) -> list[MeterReading]:
    """Read meter data from a smart meter using the specified protocol.

    This is a read-only operation. No data is persisted, no commands are
    sent to the meter, and no configuration is changed.

    Parameters
    ----------
    protocol : {"modbus_tcp", "bacnet_ip", "snmp"}
        The meter communication protocol.
    host : str
        Meter IP address or hostname.
    port : int, optional
        Protocol port. Defaults: Modbus 502, BACnet 47808, SNMP 161.
    timeout : float, optional
        Network timeout in seconds (0.1-30). Default 5.0.
    unit_id : int, optional
        Modbus unit ID (1-247). Required for modbus_tcp.
    registers : list[dict], optional
        Modbus register mappings. Each dict must have:
        - address: int (0-65535)
        - unit: str (measurement unit, e.g. "kW", "kWh")
        - meter_id: str (optional, defaults to generated)
        - data_type: str (optional, default "uint16")
          One of: uint16, int16, uint32, int32, float32
        - scale: float (optional, default 1.0)
        - function_code: int (optional, default 0x03)
          0x03 for holding registers, 0x04 for input registers
    device_id : int, optional
        BACnet device ID. Required for bacnet_ip.
    objects : list[dict], optional
        BACnet object mappings. Each dict must have:
        - instance: int (object instance number)
        - unit: str (measurement unit)
        - meter_id: str (optional, defaults to generated)
        - object_type: int (optional, default 0 for Analog Input)
          0 = Analog Input, 2 = Analog Value
        - scale: float (optional, default 1.0)
    community : str, optional
        SNMP community string. Required for snmp.
    oids : list[dict], optional
        SNMP OID mappings. Each dict must have:
        - oid: str (e.g. "1.3.6.1.4.1.9.9.109.1.1.1.1.5.0")
        - unit: str (measurement unit)
        - meter_id: str (optional, defaults to generated)
        - scale: float (optional, default 1.0)

    Returns
    -------
    list[MeterReading]
        Bounded list of meter readings with quality and provenance.

    Raises
    ------
    ValidationError_
        If any input parameter is invalid.
    ConnectionError_
        If the meter cannot be reached.
    TimeoutError_
        If the operation exceeds the timeout.
    ProtocolError_
        If the meter returns a malformed or unexpected response.
    """
    protocol = protocol.strip().lower()
    host = _validate_host(host)
    timeout = _validate_timeout(timeout)

    if protocol == "modbus_tcp":
        if unit_id is None:
            raise ValidationError_("unit_id is required for modbus_tcp")
        if registers is None:
            raise ValidationError_("registers is required for modbus_tcp")
        unit_id = _validate_unit_id(unit_id)
        port = _validate_port(port or _MODBUS_TCP_PORT)
        return _read_modbus_tcp(
            host=host, port=port, unit_id=unit_id,
            registers=registers, timeout=timeout,
        )

    if protocol == "bacnet_ip":
        if device_id is None:
            raise ValidationError_("device_id is required for bacnet_ip")
        if objects is None:
            raise ValidationError_("objects is required for bacnet_ip")
        if not isinstance(device_id, int) or isinstance(device_id, bool):
            raise ValidationError_("device_id must be an integer")
        if not 0 <= device_id <= 4194303:
            raise ValidationError_("BACnet device_id must be 0-4194303")
        port = _validate_port(port or _BACNET_IP_PORT)
        return _read_bacnet_ip(
            host=host, port=port, device_id=device_id,
            objects=objects, timeout=timeout,
        )

    if protocol == "snmp":
        if community is None:
            raise ValidationError_("community is required for snmp")
        if oids is None:
            raise ValidationError_("oids is required for snmp")
        port = _validate_port(port or _SNMP_PORT)
        return _read_snmp(
            host=host, port=port, community=community,
            oids=oids, timeout=timeout,
        )

    raise ValidationError_(f"unsupported protocol: {protocol!r}. Use 'modbus_tcp', 'bacnet_ip', or 'snmp'")


def reading_to_dict(reading: MeterReading) -> dict[str, Any]:
    """Convert a MeterReading to a plain dictionary."""
    return dataclasses.asdict(reading)

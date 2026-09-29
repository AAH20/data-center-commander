"""Tests for the smart meter adapter (Modbus TCP, BACnet/IP, SNMP)."""
import struct
import unittest
from unittest.mock import patch, MagicMock

from dcc.adapters.meter import (
    ConnectionError_,
    MeterAdapterError,
    MeterReading,
    ProtocolError_,
    QualityStatus,
    TimeoutError_,
    ValidationError_,
    _build_modbus_request,
    _build_bacnet_read_request,
    _decode_register_value,
    _modbus_crc16,
    _parse_modbus_response,
    _parse_bacnet_response,
    _snmp_build_get_request,
    _snmp_encode_oid,
    _snmp_parse_response,
    read_meter_data,
    reading_to_dict,
)


class ValidationTests(unittest.TestCase):
    """Input validation must reject bad parameters before any network access."""

    def test_rejects_unsupported_protocol(self):
        with patch("dcc.adapters.meter.socket.socket") as mock_socket:
            with self.assertRaisesRegex(ValidationError_, "unsupported protocol"):
                read_meter_data(protocol="http", host="10.0.0.1")
        mock_socket.assert_not_called()

    def test_rejects_invalid_host(self):
        for host in ("", "a" * 254, "host;rm -rf", "host name"):
            with self.subTest(host=host), self.assertRaises(ValidationError_):
                read_meter_data(protocol="modbus_tcp", host=host, unit_id=1, registers=[])

    def test_rejects_invalid_port(self):
        for port in (0, -1, 65536, "502", True):
            with self.subTest(port=port), self.assertRaises(ValidationError_):
                read_meter_data(protocol="modbus_tcp", host="10.0.0.1", port=port, unit_id=1, registers=[])

    def test_rejects_invalid_timeout(self):
        for timeout in (0, -1, 31, "5", True):
            with self.subTest(timeout=timeout), self.assertRaises(ValidationError_):
                read_meter_data(protocol="modbus_tcp", host="10.0.0.1", timeout=timeout, unit_id=1, registers=[])

    def test_rejects_invalid_modbus_unit_id(self):
        for uid in (0, 248, -1, "1", True):
            with self.subTest(unit_id=uid), self.assertRaises(ValidationError_):
                read_meter_data(protocol="modbus_tcp", host="10.0.0.1", unit_id=uid, registers=[])

    def test_rejects_invalid_register_address(self):
        for addr in (-1, 65536, "0", True):
            with self.subTest(address=addr), self.assertRaises(ValidationError_):
                read_meter_data(protocol="modbus_tcp", host="10.0.0.1", unit_id=1,
                                registers=[{"address": addr, "unit": "kW"}])

    def test_rejects_too_many_registers(self):
        regs = [{"address": i, "unit": "kW"} for i in range(126)]
        with self.assertRaisesRegex(ValidationError_, "at most 125"):
            read_meter_data(protocol="modbus_tcp", host="10.0.0.1", unit_id=1, registers=regs)

    def test_rejects_invalid_data_type(self):
        with self.assertRaisesRegex(ValidationError_, "unsupported data_type"):
            read_meter_data(protocol="modbus_tcp", host="10.0.0.1", unit_id=1,
                            registers=[{"address": 0, "unit": "kW", "data_type": "float64"}])

    def test_rejects_invalid_function_code(self):
        with self.assertRaisesRegex(ValidationError_, "unsupported Modbus function code"):
            read_meter_data(protocol="modbus_tcp", host="10.0.0.1", unit_id=1,
                            registers=[{"address": 0, "unit": "kW", "function_code": 0x06}])

    def test_rejects_missing_unit_for_register(self):
        with self.assertRaisesRegex(ValidationError_, "unit is required"):
            read_meter_data(protocol="modbus_tcp", host="10.0.0.1", unit_id=1,
                            registers=[{"address": 0, "unit": ""}])

    def test_rejects_missing_modbus_params(self):
        with self.assertRaisesRegex(ValidationError_, "unit_id is required"):
            read_meter_data(protocol="modbus_tcp", host="10.0.0.1", registers=[])
        with self.assertRaisesRegex(ValidationError_, "registers is required"):
            read_meter_data(protocol="modbus_tcp", host="10.0.0.1", unit_id=1)

    def test_rejects_invalid_bacnet_device_id(self):
        for did in (-1, 4194304, "1", True):
            with self.subTest(device_id=did), self.assertRaises(ValidationError_):
                read_meter_data(protocol="bacnet_ip", host="10.0.0.1", device_id=did, objects=[])

    def test_rejects_invalid_bacnet_object_type(self):
        with self.assertRaisesRegex(ValidationError_, "unsupported BACnet object type"):
            read_meter_data(protocol="bacnet_ip", host="10.0.0.1", device_id=1,
                            objects=[{"instance": 0, "unit": "kW", "object_type": 99}])

    def test_rejects_missing_bacnet_params(self):
        with self.assertRaisesRegex(ValidationError_, "device_id is required"):
            read_meter_data(protocol="bacnet_ip", host="10.0.0.1", objects=[])
        with self.assertRaisesRegex(ValidationError_, "objects is required"):
            read_meter_data(protocol="bacnet_ip", host="10.0.0.1", device_id=1)

    def test_rejects_invalid_oid(self):
        for oid in ("", "a.b.c", "1", "1.2.3." + "9" * 300):
            with self.subTest(oid=oid), self.assertRaises(ValidationError_):
                read_meter_data(protocol="snmp", host="10.0.0.1", community="public",
                                oids=[{"oid": oid, "unit": "kW"}])

    def test_rejects_too_many_oids(self):
        oids = [{"oid": f"1.3.6.1.4.1.9.9.109.1.1.1.1.5.{i}", "unit": "kW"} for i in range(51)]
        with self.assertRaisesRegex(ValidationError_, "at most 50"):
            read_meter_data(protocol="snmp", host="10.0.0.1", community="public", oids=oids)

    def test_rejects_missing_snmp_params(self):
        with self.assertRaisesRegex(ValidationError_, "community is required"):
            read_meter_data(protocol="snmp", host="10.0.0.1", oids=[])
        with self.assertRaisesRegex(ValidationError_, "oids is required"):
            read_meter_data(protocol="snmp", host="10.0.0.1", community="public")

    def test_rejects_empty_community(self):
        with self.assertRaisesRegex(ValidationError_, "community string"):
            read_meter_data(protocol="snmp", host="10.0.0.1", community="", oids=[])

    def test_rejects_invalid_meter_id(self):
        for mid in ("", "a" * 121):
            with self.subTest(meter_id=mid), self.assertRaises(ValidationError_):
                read_meter_data(protocol="modbus_tcp", host="10.0.0.1", unit_id=1,
                                registers=[{"address": 0, "unit": "kW", "meter_id": mid}])


class ModbusEncodingTests(unittest.TestCase):
    """Modbus frame building and parsing."""

    def test_crc16_known_value(self):
        # Standard Modbus CRC test: "123456789" -> 0x4B37
        self.assertEqual(_modbus_crc16(b"123456789"), 0x4B37)

    def test_build_modbus_request_structure(self):
        frame = _build_modbus_request(1, 1, 0x03, 100, 10)
        self.assertEqual(len(frame), 12)  # 7 MBAP + 5 PDU
        tid, pid, length, uid = struct.unpack(">HHHB", frame[:7])
        self.assertEqual(tid, 1)
        self.assertEqual(pid, 0)
        self.assertEqual(length, 6)  # 1 unit + 5 PDU
        self.assertEqual(uid, 1)
        self.assertEqual(frame[7], 0x03)  # function code
        self.assertEqual(struct.unpack(">H", frame[8:10])[0], 100)  # start address
        self.assertEqual(struct.unpack(">H", frame[10:12])[0], 10)  # quantity

    def test_parse_modbus_response_success(self):
        # Build a valid response: TID=1, PID=0, LEN=6, UID=1, FC=0x03, BC=4, data
        registers_data = struct.pack(">HH", 1000, 2000)
        pdu = struct.pack(">BB", 0x03, 4) + registers_data
        header = struct.pack(">HHHB", 1, 0, 1 + len(pdu), 1)
        response = header + pdu
        result = _parse_modbus_response(response, 1, 1, 0x03)
        self.assertEqual(result, [1000, 2000])

    def test_parse_modbus_response_transaction_mismatch(self):
        pdu = struct.pack(">BB", 0x03, 0)
        header = struct.pack(">HHHB", 2, 0, 1 + len(pdu), 1)
        with self.assertRaisesRegex(ProtocolError_, "transaction ID mismatch"):
            _parse_modbus_response(header + pdu, 1, 1, 0x03)

    def test_parse_modbus_response_exception(self):
        pdu = struct.pack(">BB", 0x83, 0x02)  # exception code 2
        header = struct.pack(">HHHB", 1, 0, 1 + len(pdu), 1)
        with self.assertRaisesRegex(ProtocolError_, "Modbus exception"):
            _parse_modbus_response(header + pdu, 1, 1, 0x03)

    def test_decode_uint16(self):
        value, raw = _decode_register_value([1000], "uint16", 0.001, "kW")
        self.assertEqual(raw, 1000)
        self.assertAlmostEqual(value, 1.0)

    def test_decode_int16_negative(self):
        value, raw = _decode_register_value([0xFFFF], "int16", 1.0, "kW")
        self.assertEqual(raw, -1)
        self.assertAlmostEqual(value, -1.0)

    def test_decode_uint32(self):
        value, raw = _decode_register_value([0x0001, 0x0000], "uint32", 0.01, "kWh")
        self.assertEqual(raw, 65536)
        self.assertAlmostEqual(value, 655.36)

    def test_decode_float32(self):
        # 1.5 as IEEE 754 float32
        raw_bytes = struct.pack(">f", 1.5)
        regs = struct.unpack(">HH", raw_bytes)
        value, raw = _decode_register_value(list(regs), "float32", 1.0, "kW")
        self.assertAlmostEqual(raw, 1.5)
        self.assertAlmostEqual(value, 1.5)

    def test_decode_invalid_type(self):
        with self.assertRaisesRegex(ValidationError_, "unsupported data_type"):
            _decode_register_value([0], "float64", 1.0, "kW")


class ModbusTCPTests(unittest.TestCase):
    """Modbus TCP read operations."""

    def _make_modbus_response(self, tid, uid, fc, registers):
        reg_bytes = b"".join(struct.pack(">H", r) for r in registers)
        pdu = struct.pack(">BB", fc, len(reg_bytes)) + reg_bytes
        header = struct.pack(">HHHB", tid, 0, 1 + len(pdu), uid)
        return header + pdu

    def test_read_modbus_tcp_success(self):
        response = self._make_modbus_response(1, 1, 0x03, [1500])

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [
            response[:7],           # MBAP header
            response[7:],           # body
        ]
        mock_sock.connect = MagicMock()
        mock_sock.sendall = MagicMock()
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            readings = read_meter_data(
                protocol="modbus_tcp", host="10.0.0.1", port=502,
                unit_id=1, registers=[{"address": 0, "unit": "kW", "scale": 0.001}],
            )

        self.assertEqual(len(readings), 1)
        r = readings[0]
        self.assertEqual(r.meter_id, "modbus-1-0")
        self.assertAlmostEqual(r.value, 1.5)
        self.assertEqual(r.unit, "kW")
        self.assertEqual(r.quality, QualityStatus.GOOD)
        self.assertEqual(r.protocol, "modbus_tcp")
        self.assertEqual(r.source_address, "10.0.0.1:502")
        self.assertEqual(r.register_address, 0)
        self.assertEqual(r.raw_value, 1500)

    def test_read_modbus_tcp_timeout(self):
        mock_sock = MagicMock()
        mock_sock.connect = MagicMock()
        mock_sock.sendall = MagicMock()
        mock_sock.recv.side_effect = TimeoutError("timed out")
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            with self.assertRaisesRegex(TimeoutError_, "timed out"):
                read_meter_data(
                    protocol="modbus_tcp", host="10.0.0.1", port=502,
                    unit_id=1, registers=[{"address": 0, "unit": "kW"}],
                )

    def test_read_modbus_tcp_connection_refused(self):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = OSError("Connection refused")
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            with self.assertRaisesRegex(ConnectionError_, "Connection refused"):
                read_meter_data(
                    protocol="modbus_tcp", host="10.0.0.1", port=502,
                    unit_id=1, registers=[{"address": 0, "unit": "kW"}],
                )

    def test_read_modbus_tcp_multiple_registers(self):
        # Two separate register reads
        resp1 = self._make_modbus_response(1, 1, 0x03, [100])
        resp2 = self._make_modbus_response(2, 1, 0x03, [200])

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [
            resp1[:7], resp1[7:],
            resp2[:7], resp2[7:],
        ]
        mock_sock.connect = MagicMock()
        mock_sock.sendall = MagicMock()
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            readings = read_meter_data(
                protocol="modbus_tcp", host="10.0.0.1", port=502,
                unit_id=1, registers=[
                    {"address": 0, "unit": "kW", "scale": 0.01},
                    {"address": 10, "unit": "kWh", "scale": 0.1},
                ],
            )

        self.assertEqual(len(readings), 2)
        self.assertEqual(readings[0].register_address, 0)
        self.assertAlmostEqual(readings[0].value, 1.0)
        self.assertEqual(readings[1].register_address, 10)
        self.assertAlmostEqual(readings[1].value, 20.0)

    def test_read_modbus_tcp_stale_quality(self):
        response = self._make_modbus_response(1, 1, 0x03, [100])

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [response[:7], response[7:]]
        mock_sock.connect = MagicMock()
        mock_sock.sendall = MagicMock()
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            readings = read_meter_data(
                protocol="modbus_tcp", host="10.0.0.1", port=502,
                unit_id=1, registers=[{
                    "address": 0, "unit": "kW",
                    "stale_after_seconds": 60,
                    "last_seen": 0,  # Very old
                }],
            )

        self.assertEqual(readings[0].quality, QualityStatus.STALE)

    def test_read_modbus_tcp_oversized_response(self):
        # Build a header that claims a very large body
        header = struct.pack(">HHHB", 1, 0, 0xFFFF, 1)
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [header, b"\x00" * 70000]
        mock_sock.connect = MagicMock()
        mock_sock.sendall = MagicMock()
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            with self.assertRaisesRegex(ProtocolError_, "size limit"):
                read_meter_data(
                    protocol="modbus_tcp", host="10.0.0.1", port=502,
                    unit_id=1, registers=[{"address": 0, "unit": "kW"}],
                )


class BACnetEncodingTests(unittest.TestCase):
    """BACnet frame building and parsing."""

    def test_build_bacnet_request_structure(self):
        frame = _build_bacnet_read_request(1, 0, 0, 85)
        self.assertGreater(len(frame), 8)
        # BVLC type
        self.assertEqual(frame[0], 0x81)
        # BVLC function
        self.assertEqual(frame[1], 0x0B)
        # NPDU version
        self.assertEqual(frame[4], 0x01)

    def test_parse_bacnet_response_success(self):
        # Build a minimal BACnet response with a float value of 25.5
        value_bytes = struct.pack(">f", 25.5)
        # APDU: ComplexACK (0x30), invoke ID 1, service choice 0x0C (ReadProperty-ACK)
        apdu = struct.pack(">BBB", 0x30, 0x01, 0x0C)
        # Object ID: context tag 0, length 4
        obj_id = struct.pack(">I", (0 << 22) | 0)  # Analog Input, instance 0
        apdu += bytes([0x0C]) + obj_id
        # Property ID: context tag 1, length 1, property 85
        apdu += bytes([0x19, 0x55])
        # Opening tag
        apdu += bytes([0x2E])
        # Real value: application tag 4, length 4
        apdu += bytes([0x44]) + value_bytes
        # Closing tag
        apdu += bytes([0x2F])
        # NPDU
        npdu = struct.pack(">BB", 0x01, 0x00)
        # BVLC
        bvlc_len = 4 + len(npdu) + len(apdu)
        bvlc = struct.pack(">BBBB", 0x81, 0x0B, (bvlc_len >> 8) & 0xFF, bvlc_len & 0xFF)
        response = bvlc + npdu + apdu
        result = _parse_bacnet_response(response, 1)
        self.assertAlmostEqual(result, 25.5)

    def test_parse_bacnet_response_too_short(self):
        with self.assertRaisesRegex(ProtocolError_, "too short"):
            _parse_bacnet_response(b"\x81\x0b", 1)


class BACnetIPTests(unittest.TestCase):
    """BACnet/IP read operations."""

    def _make_bacnet_response(self, value):
        value_bytes = struct.pack(">f", value)
        apdu = struct.pack(">BBB", 0x30, 0x01, 0x0C)  # ComplexACK
        obj_id = struct.pack(">I", (0 << 22) | 0)
        apdu += bytes([0x0C]) + obj_id
        apdu += bytes([0x19, 0x55])
        apdu += bytes([0x2E])
        apdu += bytes([0x44]) + value_bytes
        apdu += bytes([0x2F])
        npdu = struct.pack(">BB", 0x01, 0x00)
        bvlc_len = 4 + len(npdu) + len(apdu)
        bvlc = struct.pack(">BBBB", 0x81, 0x0B, (bvlc_len >> 8) & 0xFF, bvlc_len & 0xFF)
        return bvlc + npdu + apdu

    def test_read_bacnet_ip_success(self):
        response = self._make_bacnet_response(42.0)

        mock_sock = MagicMock()
        mock_sock.sendto = MagicMock()
        mock_sock.recvfrom.return_value = (response, ("10.0.0.1", 47808))
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            readings = read_meter_data(
                protocol="bacnet_ip", host="10.0.0.1", port=47808,
                device_id=1, objects=[{"instance": 0, "unit": "kW", "scale": 1.0}],
            )

        self.assertEqual(len(readings), 1)
        r = readings[0]
        self.assertEqual(r.meter_id, "bacnet-1-0-0")
        self.assertAlmostEqual(r.value, 42.0)
        self.assertEqual(r.unit, "kW")
        self.assertEqual(r.quality, QualityStatus.GOOD)
        self.assertEqual(r.protocol, "bacnet_ip")
        self.assertEqual(r.source_address, "10.0.0.1:47808")
        self.assertEqual(r.oid, "0:0")

    def test_read_bacnet_ip_timeout(self):
        mock_sock = MagicMock()
        mock_sock.sendto = MagicMock()
        mock_sock.recvfrom.side_effect = TimeoutError("timed out")
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            with self.assertRaisesRegex(TimeoutError_, "timed out"):
                read_meter_data(
                    protocol="bacnet_ip", host="10.0.0.1", port=47808,
                    device_id=1, objects=[{"instance": 0, "unit": "kW"}],
                )

    def test_read_bacnet_ip_analog_value_object(self):
        response = self._make_bacnet_response(99.5)

        mock_sock = MagicMock()
        mock_sock.sendto = MagicMock()
        mock_sock.recvfrom.return_value = (response, ("10.0.0.1", 47808))
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            readings = read_meter_data(
                protocol="bacnet_ip", host="10.0.0.1", port=47808,
                device_id=1, objects=[{
                    "instance": 5, "unit": "kWh", "scale": 0.01,
                    "object_type": 2,  # Analog Value
                }],
            )

        self.assertEqual(readings[0].oid, "2:5")
        self.assertAlmostEqual(readings[0].value, 0.995)


class SNMPCodingTests(unittest.TestCase):
    """SNMP frame building and parsing."""

    def test_encode_oid_simple(self):
        result = _snmp_encode_oid("1.3.6.1")
        # 1.3 -> 40*1+3 = 43 = 0x2B
        self.assertEqual(result[0], 0x2B)
        self.assertEqual(result[1], 0x06)
        self.assertEqual(result[2], 0x01)

    def test_encode_oid_multi_byte(self):
        # 1.3.6.1.4.1.9.9.109 -> 109 needs multi-byte encoding
        result = _snmp_encode_oid("1.3.6.1.4.1.9.9.109")
        self.assertEqual(result[0], 0x2B)  # 1.3
        # 109 = 0x6D, which is < 128 so single byte
        self.assertIn(0x6D, result)

    def test_build_snmp_get_request_structure(self):
        request = _snmp_build_get_request(1, "public", ["1.3.6.1.2.1.1.1.0"])
        self.assertGreater(len(request), 10)
        # SEQUENCE tag
        self.assertEqual(request[0], 0x30)

    def test_parse_snmp_response_integer(self):
        # Build a minimal SNMP response with integer value 42
        oid_bytes = _snmp_encode_oid("1.3.6.1.2.1.1.1.0")
        inner = bytes([0x06, len(oid_bytes)]) + oid_bytes
        inner += bytes([0x02, 0x01, 0x2A])  # INTEGER 42
        varbind = bytes([0x30, len(inner)]) + inner  # VarBind SEQUENCE
        # PDU content: request ID, error status, error index, varbind list
        pdu_content = bytes([0x02, 0x01, 0x01])  # request ID = 1
        pdu_content += bytes([0x02, 0x01, 0x00])  # error status = 0
        pdu_content += bytes([0x02, 0x01, 0x00])  # error index = 0
        pdu_content += bytes([0x30, len(varbind)]) + varbind
        pdu = bytes([0xA2]) + bytes([len(pdu_content)]) + pdu_content
        comm = b"public"
        comm_field = bytes([0x04, len(comm)]) + comm
        version_field = bytes([0x02, 0x01, 0x00])
        msg_content = version_field + comm_field + pdu
        message = bytes([0x30, len(msg_content)]) + msg_content
        results = _snmp_parse_response(message)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "1.3.6.1.2.1.1.1.0")
        self.assertEqual(results[0][1], 42)

    def test_parse_snmp_response_counter32(self):
        oid_bytes = _snmp_encode_oid("1.3.6.1.2.1.2.2.1.10.1")
        inner = bytes([0x06, len(oid_bytes)]) + oid_bytes
        inner += bytes([0x41, 0x04]) + struct.pack(">I", 1000000)  # Counter32
        varbind = bytes([0x30, len(inner)]) + inner  # VarBind SEQUENCE
        pdu_content = bytes([0x02, 0x01, 0x01])  # request ID = 1
        pdu_content += bytes([0x02, 0x01, 0x00])  # error status = 0
        pdu_content += bytes([0x02, 0x01, 0x00])  # error index = 0
        pdu_content += bytes([0x30, len(varbind)]) + varbind
        pdu = bytes([0xA2]) + bytes([len(pdu_content)]) + pdu_content
        comm = b"public"
        comm_field = bytes([0x04, len(comm)]) + comm
        version_field = bytes([0x02, 0x01, 0x00])
        msg_content = version_field + comm_field + pdu
        message = bytes([0x30, len(msg_content)]) + msg_content
        results = _snmp_parse_response(message)
        self.assertEqual(results[0][1], 1000000)

    def test_parse_snmp_response_null_value(self):
        oid_bytes = _snmp_encode_oid("1.3.6.1.2.1.1.1.0")
        inner = bytes([0x06, len(oid_bytes)]) + oid_bytes
        inner += bytes([0x05, 0x00])  # NULL
        varbind = bytes([0x30, len(inner)]) + inner  # VarBind SEQUENCE
        pdu_content = bytes([0x02, 0x01, 0x01])  # request ID = 1
        pdu_content += bytes([0x02, 0x01, 0x00])  # error status = 0
        pdu_content += bytes([0x02, 0x01, 0x00])  # error index = 0
        pdu_content += bytes([0x30, len(varbind)]) + varbind
        pdu = bytes([0xA2]) + bytes([len(pdu_content)]) + pdu_content
        comm = b"public"
        comm_field = bytes([0x04, len(comm)]) + comm
        version_field = bytes([0x02, 0x01, 0x00])
        msg_content = version_field + comm_field + pdu
        message = bytes([0x30, len(msg_content)]) + msg_content
        results = _snmp_parse_response(message)
        self.assertIsNone(results[0][1])

    def test_parse_snmp_response_too_short(self):
        with self.assertRaisesRegex(ProtocolError_, "too short"):
            _snmp_parse_response(b"\x30\x00")


class SNMPTests(unittest.TestCase):
    """SNMP read operations."""

    def _make_snmp_response(self, value, tag=0x02):
        oid_bytes = _snmp_encode_oid("1.3.6.1.4.1.9.9.109.1.1.1.1.5.0")
        inner = bytes([0x06, len(oid_bytes)]) + oid_bytes
        if tag == 0x02:  # INTEGER
            inner += bytes([0x02, 0x04]) + struct.pack(">i", value)
        elif tag == 0x41:  # Counter32
            inner += bytes([0x41, 0x04]) + struct.pack(">I", value)
        elif tag == 0x42:  # Gauge32
            inner += bytes([0x42, 0x04]) + struct.pack(">I", value)
        elif tag == 0x05:  # NULL
            inner += bytes([0x05, 0x00])
        varbind = bytes([0x30, len(inner)]) + inner  # VarBind SEQUENCE
        pdu_content = bytes([0x02, 0x01, 0x01])  # request ID = 1
        pdu_content += bytes([0x02, 0x01, 0x00])  # error status = 0
        pdu_content += bytes([0x02, 0x01, 0x00])  # error index = 0
        pdu_content += bytes([0x30, len(varbind)]) + varbind
        pdu = bytes([0xA2]) + bytes([len(pdu_content)]) + pdu_content
        comm = b"public"
        comm_field = bytes([0x04, len(comm)]) + comm
        version_field = bytes([0x02, 0x01, 0x00])
        msg_content = version_field + comm_field + pdu
        return bytes([0x30, len(msg_content)]) + msg_content

    def test_read_snmp_success(self):
        response = self._make_snmp_response(5000)

        mock_sock = MagicMock()
        mock_sock.sendto = MagicMock()
        mock_sock.recvfrom.return_value = (response, ("10.0.0.1", 161))
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            readings = read_meter_data(
                protocol="snmp", host="10.0.0.1", port=161,
                community="public",
                oids=[{"oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.5.0", "unit": "kW", "scale": 0.001}],
            )

        self.assertEqual(len(readings), 1)
        r = readings[0]
        self.assertEqual(r.meter_id, "snmp-1.3.6.1.4.1.9.9.109.1.1.1.1.5.0")
        self.assertAlmostEqual(r.value, 5.0)
        self.assertEqual(r.unit, "kW")
        self.assertEqual(r.quality, QualityStatus.GOOD)
        self.assertEqual(r.protocol, "snmp")
        self.assertEqual(r.source_address, "10.0.0.1:161")
        self.assertEqual(r.oid, "1.3.6.1.4.1.9.9.109.1.1.1.1.5.0")
        self.assertEqual(r.raw_value, 5000)

    def test_read_snmp_timeout(self):
        mock_sock = MagicMock()
        mock_sock.sendto = MagicMock()
        mock_sock.recvfrom.side_effect = TimeoutError("timed out")
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            with self.assertRaisesRegex(TimeoutError_, "timed out"):
                read_meter_data(
                    protocol="snmp", host="10.0.0.1", port=161,
                    community="public",
                    oids=[{"oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.5.0", "unit": "kW"}],
                )

    def test_read_snmp_null_value_skipped(self):
        response = self._make_snmp_response(0, tag=0x05)  # NULL

        mock_sock = MagicMock()
        mock_sock.sendto = MagicMock()
        mock_sock.recvfrom.return_value = (response, ("10.0.0.1", 161))
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            readings = read_meter_data(
                protocol="snmp", host="10.0.0.1", port=161,
                community="public",
                oids=[{"oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.5.0", "unit": "kW"}],
            )

        self.assertEqual(len(readings), 0)

    def test_read_snmp_oversized_response(self):
        mock_sock = MagicMock()
        mock_sock.sendto = MagicMock()
        mock_sock.recvfrom.return_value = (b"\x00" * 70000, ("10.0.0.1", 161))
        mock_sock.close = MagicMock()
        mock_sock.settimeout = MagicMock()

        with patch("dcc.adapters.meter.socket.socket", return_value=mock_sock):
            with self.assertRaisesRegex(ProtocolError_, "size limit"):
                read_meter_data(
                    protocol="snmp", host="10.0.0.1", port=161,
                    community="public",
                    oids=[{"oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.5.0", "unit": "kW"}],
                )


class MeterReadingTests(unittest.TestCase):
    """MeterReading dataclass and conversion."""

    def test_reading_to_dict(self):
        r = MeterReading(
            meter_id="test-meter",
            observed_at="2026-09-29T12:00:00Z",
            value=42.5,
            unit="kW",
            quality=QualityStatus.GOOD,
            protocol="modbus_tcp",
            source_address="10.0.0.1:502",
            register_address=0,
            raw_value=42500,
            metadata={"scale": 0.001},
        )
        d = reading_to_dict(r)
        self.assertEqual(d["meter_id"], "test-meter")
        self.assertEqual(d["value"], 42.5)
        self.assertEqual(d["unit"], "kW")
        self.assertEqual(d["quality"], "good")
        self.assertEqual(d["protocol"], "modbus_tcp")
        self.assertEqual(d["metadata"]["scale"], 0.001)

    def test_reading_default_metadata(self):
        r = MeterReading(
            meter_id="m1", observed_at="2026-01-01T00:00:00Z",
            value=1.0, unit="kW", quality=QualityStatus.GOOD,
            protocol="snmp", source_address="10.0.0.1:161",
        )
        self.assertEqual(r.metadata, {})
        self.assertIsNone(r.register_address)
        self.assertIsNone(r.oid)
        self.assertIsNone(r.raw_value)


class ExceptionHierarchyTests(unittest.TestCase):
    """Exception hierarchy is correct."""

    def test_all_exceptions_inherit_base(self):
        for exc_cls in (ConnectionError_, TimeoutError_, ProtocolError_, ValidationError_):
            self.assertTrue(issubclass(exc_cls, MeterAdapterError))

    def test_base_is_exception(self):
        self.assertTrue(issubclass(MeterAdapterError, Exception))


if __name__ == "__main__":
    unittest.main()

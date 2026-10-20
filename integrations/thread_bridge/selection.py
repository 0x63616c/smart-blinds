"""Trusted local selection, not a wire/device-supplied commissioning record."""
from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import re


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Invalid {label}')
    return value


@dataclass(frozen=True)
class Selection:
    device_id: str
    host: str
    port: int
    identity: str
    key: bytes = field(repr=False)
    boot: int
    calibration: int
    low_um: int
    high_um: int
    max_speed_um_s: int
    max_accel_um_s2: int
    commissioning_id: str = ''
    commissioned: bool = False

    def validate(self):
        if self.commissioned is not True or not self.commissioning_id:
            raise ValueError('Explicit existing commissioning selection is required')
        for label, value in (('device ID', self.device_id), ('identity', self.identity)):
            if type(value) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,32}', value) is None:
                raise ValueError(f'Invalid {label}')
        if type(self.commissioning_id) is not str or len(self.commissioning_id) > 128:
            raise ValueError('Invalid commissioning identity')
        if type(self.host) is not str or '%' in self.host:
            raise ValueError('Explicit unicast literal address required')
        address = ipaddress.ip_address(self.host)
        if address.is_multicast or address.is_unspecified:
            raise ValueError('Explicit unicast literal address required')
        integer(self.port, 1, 65535, 'port')
        integer(self.boot, 1, 2**64-1, 'boot')
        integer(self.calibration, 1, 2**32-1, 'calibration')
        integer(self.low_um, -10**9, 10**9, 'lower height')
        integer(self.high_um, self.low_um+1, 10**9, 'upper height')
        integer(self.max_speed_um_s, 1, 30000, 'speed')
        integer(self.max_accel_um_s2, 1, 60000, 'acceleration')
        if type(self.key) is not bytes or len(self.key) != 32 or not any(self.key):
            raise ValueError('Explicit per-device PSK required')

    def binding(self):
        self.validate()
        # No secret/key material or movable IP address is persisted in the ledger.
        values = [self.device_id, self.identity, f'{self.boot:016x}', self.calibration,
                  self.low_um, self.high_um, self.max_speed_um_s, self.max_accel_um_s2, self.commissioning_id]
        return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()

"""Durable monotonic reservations. Persist counters only; never replay commands."""
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import sqlite3
from .selection import Selection, integer


class LedgerError(RuntimeError):
    pass


def parse_hex(value):
    if type(value) is not str or len(value) != 16 or any(c not in '0123456789abcdef' for c in value):
        raise LedgerError('Malformed ledger counter')
    return int(value, 16)


@dataclass
class Reservation:
    device_id: str
    boot: int
    command: int
    floor: int
    ceiling: int
    cursor: int
    stopped: bool = False

    def take(self):
        if self.stopped or self.cursor >= self.ceiling:
            raise LedgerError('Reserved ordinary-message range exhausted')
        value = self.cursor
        self.cursor += 1
        return value

    def take_stop(self):
        if self.stopped:
            raise LedgerError('STOP already consumed; never retry it')
        self.stopped = True
        self.cursor = self.ceiling + 1
        return self.ceiling


class Ledger:
    """One local process owns a ledger for its lifetime; all reservations are EXTRA-sync.

    Creation/enrolment are explicit. Restoring a backup/losing the ledger does not
    establish the actual device replay floor; resolve that through commissioning.
    Reserve 4096 messages before a <=240 s job, including highest-number STOP.
    """
    def __init__(self, path: Path, *, create=False):
        if Path(path).is_symlink(): raise LedgerError('Ledger path must not be a symlink')
        self.path = Path(path).absolute()
        self.db = None
        self.lock = None
        made = False
        try:
            self.lock = os.open(str(self.path)+'.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if create:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                os.close(fd); made = True
            elif not self.path.is_file():
                raise LedgerError('Missing ledger; explicit creation/recovery required')
            self.db = sqlite3.connect(self.path.as_uri()+'?mode=rw', uri=True, isolation_level=None, timeout=.1)
            # Keep the database and rollback journal under one committed local
            # filesystem transaction. No fsync occurs on the active motor path.
            self.db.execute('PRAGMA journal_mode=DELETE')
            self.db.execute('PRAGMA synchronous=EXTRA')
            self.db.execute('PRAGMA fullfsync=ON')  # macOS F_FULLFSYNC; harmless elsewhere.
            if (self.db.execute('PRAGMA journal_mode').fetchone() != ('delete',) or
                self.db.execute('PRAGMA synchronous').fetchone() != (3,) or
                self.db.execute('PRAGMA fullfsync').fetchone() != (1,)):
                raise LedgerError('Required durability mode unavailable')
            if made:
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute('CREATE TABLE metadata (version INTEGER NOT NULL)')
                self.db.execute('INSERT INTO metadata VALUES (1)')
                self.db.execute('CREATE TABLE counters (device TEXT NOT NULL, boot TEXT NOT NULL, binding TEXT NOT NULL, command TEXT NOT NULL, message TEXT NOT NULL, PRIMARY KEY(device,boot))')
                self.db.execute('COMMIT')
                parent = os.open(self.path.parent, os.O_RDONLY)
                try: os.fsync(parent)
                finally: os.close(parent)
            if self.db.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or self.db.execute('SELECT version FROM metadata').fetchall() != [(1,)]:
                raise LedgerError('Unsupported or damaged ledger')
        except Exception as error:
            self.close()
            if isinstance(error, LedgerError): raise
            raise LedgerError('Ledger unavailable; no motion reservation made') from error

    def close(self):
        if self.db is not None:
            self.db.close(); self.db = None
        if self.lock is not None:
            os.close(self.lock); self.lock = None

    def __enter__(self): return self
    def __exit__(self, *_): self.close()

    def enroll(self, selected: Selection, *, command_floor: int, message_floor: int):
        """Explicit known floors from trusted recovery, not reported last_message."""
        if self.db is None: raise LedgerError('Ledger is closed')
        selected.validate()
        integer(command_floor, 0, 2**64-1, 'command floor')
        integer(message_floor, 0, 2**64-1, 'message floor')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('INSERT INTO counters VALUES (?,?,?,?,?)', (selected.device_id,
                f'{selected.boot:016x}', selected.binding(), f'{command_floor:016x}', f'{message_floor:016x}'))
            self.db.execute('COMMIT')
        except Exception as error:
            if self.db.in_transaction: self.db.execute('ROLLBACK')
            raise LedgerError('Enrolment failed; existing floors cannot be overwritten') from error

    def floor(self, selected: Selection):
        """Read existing trusted enrollment; never infer a floor from telemetry."""
        if self.db is None: raise LedgerError('Ledger is closed')
        selected.validate()
        row = self.db.execute('SELECT binding, command, message FROM counters WHERE device=? AND boot=?',
            (selected.device_id, f'{selected.boot:016x}')).fetchone()
        if not row or row[0] != selected.binding():
            raise LedgerError('Unknown boot or changed commissioning selection')
        return parse_hex(row[1]), parse_hex(row[2])

    def reserve(self, selections: list[Selection], *, count=4096) -> dict[str, Reservation]:
        if self.db is None: raise LedgerError('Ledger is closed')
        integer(count, 4, 65536, 'reservation size')
        if not 1 <= len(selections) <= 8 or len({s.device_id for s in selections}) != len(selections):
            raise ValueError('Need one to eight unique explicit selections')
        for selected in selections: selected.validate()
        result = {}
        try:
            self.db.execute('BEGIN IMMEDIATE')
            for selected in selections:
                row = self.db.execute('SELECT binding, command, message FROM counters WHERE device=? AND boot=?',
                    (selected.device_id, f'{selected.boot:016x}')).fetchone()
                if not row or row[0] != selected.binding():
                    raise LedgerError('Unknown boot or changed commissioning selection')
                command, floor = parse_hex(row[1])+1, parse_hex(row[2])
                if command >= 2**64 or floor > 2**64-1-count:
                    raise LedgerError('Counter exhausted; explicit recovery required')
                ceiling = floor + count
                result[selected.device_id] = Reservation(selected.device_id, selected.boot, command, floor, ceiling, floor+1)
                self.db.execute('UPDATE counters SET command=?, message=? WHERE device=? AND boot=?',
                    (f'{command:016x}', f'{ceiling:016x}', selected.device_id, f'{selected.boot:016x}'))
            self.db.execute('COMMIT')  # Only now can any reservation escape.
        except Exception as error:
            if self.db.in_transaction: self.db.execute('ROLLBACK')
            if isinstance(error, LedgerError): raise
            raise LedgerError('Reservation failed; no commands may be sent') from error
        return result

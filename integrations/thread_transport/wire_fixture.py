"""Loopback-only UDP recorder for DTLS replay/corruption tests. No keys are stored."""
import select
import socket
import threading


class WireFixture:
    def __init__(self, server_port: int):
        self._incoming = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self._incoming.bind(("::1", 0))
        self.port = self._incoming.getsockname()[1]
        self._upstream = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self._upstream.bind(("::1", 0))
        self._server = ("::1", server_port)
        self._client = None
        self._lock = threading.Lock()
        self._record = None
        self._responses = 0
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run)
        self._worker.start()

    @staticmethod
    def _application_record(packet):
        offset = 0
        while offset + 13 <= len(packet):
            size = int.from_bytes(packet[offset + 11:offset + 13], "big")
            end = offset + 13 + size
            if end > len(packet):
                return None
            if packet[offset] == 23:  # DTLS 1.2 application-data record (encrypted).
                return packet[offset:end]
            offset = end
        return None

    def _run(self):
        while not self._stop.is_set():
            ready, _, _ = select.select([self._incoming, self._upstream], [], [], 0.01)
            for sock in ready:
                packet, sender = sock.recvfrom(2048)
                if sock is self._incoming:
                    self._client = sender
                    record = self._application_record(packet)
                    if record:
                        with self._lock:
                            self._record = record
                    self._upstream.sendto(packet, self._server)
                elif self._client:
                    with self._lock:
                        self._responses += 1
                    self._incoming.sendto(packet, self._client)

    @property
    def responses(self):
        with self._lock:
            return self._responses

    def inject(self, *, corrupt=False):
        with self._lock:
            if self._record is None:
                raise RuntimeError("No encrypted application record captured")
            packet = bytearray(self._record)
        if corrupt:
            # Alter the record sequence and ciphertext: no valid authentication tag.
            packet[10] ^= 0x40
            packet[-1] ^= 1
        self._upstream.sendto(packet, self._server)

    def close(self):
        self._stop.set()
        self._worker.join()
        self._incoming.close()
        self._upstream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

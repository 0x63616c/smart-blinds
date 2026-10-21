"""Single native owner for diagnostics and explicitly reserved motion jobs."""
import struct
from integrations.thread_transport.motion import MotionSession, _integer
from integrations.thread_transport.client import ProtocolError, Rejected, _now_us
from integrations.telemetry_transport.client import decode as telemetry_decode, History as TelemetryHistory
from .handoff import decode as handoff_decode, History as HandoffHistory


class ActorSession(MotionSession):
    _native_constructor = 'sb_actor_client_new'

    def __init__(self, *args, command_floor=0, **kwargs):
        self.command_floor = _integer(command_floor, 0, 2**64-1, 'durable command floor')
        self.reservation = None
        self.telemetry_history, self.handoff_history = TelemetryHistory(), HandoffHistory()
        self.nonce = 0
        self.last_handoff = None
        super().__init__(*args, **kwargs)

    def _query(self, kind, decoder, history):
        with self._lock:
            if self.nonce == 2**64-1: raise ProtocolError('Observation nonce exhausted')
            self.nonce += 1
            sent = _now_us()
            code, body = self._exchange(kind, struct.pack('>QQ', self.expected_boot, self.nonce))
            received = _now_us()
            if code != 69: raise Rejected(code)
            try:
                value = decoder(body, boot=self.expected_boot, nonce=self.nonce,
                                sent_host_us=sent, received_us=received)
                return history.accept(value)
            except ProtocolError:
                self._fail(); raise

    def poll(self):
        return self._query(7, telemetry_decode, self.telemetry_history)

    def handoff(self):
        value = self._query(8, handoff_decode, self.handoff_history)
        if value.received_message > self.consumed_message:
            self._fail(); raise ProtocolError('Device receipt floor exceeds durable local owner')
        self.last_handoff = value
        return value

    def reserve(self, reservation):
        """Owner-only adoption of a range already committed by the ledger.

        A previous attempt that sent motion requires fresh terminal physical OFF
        proof. Known preflight refusal with no motion attempt burns its range but
        needs no invented terminal command. Native failed handles never recover.
        """
        with self._lock:
            if self._failed: raise ProtocolError('Failed owner cannot adopt a range')
            if (reservation.boot != self.expected_boot or reservation.command <= self.command_floor or
                reservation.floor < self.consumed_message or reservation.ceiling-reservation.floor != 4096 or
                not 0 <= reservation.floor < reservation.ceiling < 2**64 or
                not 0 < reservation.command < 2**64 or reservation.stopped or
                reservation.cursor != reservation.floor+1):
                raise ProtocolError('Invalid or decreasing durable reservation')
            if self.reservation and self.consumed_message > self.reservation.floor:
                h = self.last_handoff
                if (h is None or not h.current(_now_us()) or h.command != self.reservation.command or
                    h.received_message < self.consumed_message):
                    raise ProtocolError('Previous motion has no current physical OFF handoff')
            self.reservation = reservation
            self.command_floor = reservation.command
            self._message = reservation.floor
            self._command = self._prepare_message = 0
            self._report = self._clock = None
            self._qualified_clock = False
            self._timeout = 1000

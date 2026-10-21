"""Local scripted application peer; never physical qualification or a device API."""
import ctypes as C
import os
from pathlib import Path
import secrets
import socket
import time

PHASES=('unreferenced','idle','preparing','ready','committed','moving','settling','fault')
EVENTS={1:'connected',2:'queued',3:'telemetry',11:'consume_prepare',12:'consume_commit',
        13:'consume_lease',14:'consume_stop',21:'preparing',22:'script_ready',23:'committed',
        24:'scheduled_start',25:'script_or_stop_settling',26:'script_off',90:'fault'}

class ContractPeer:
    def __init__(self,*,qualified=False,boot=99,limits=None):
        self.boot=boot;self.key=secrets.token_bytes(32)
        with socket.socket(socket.AF_INET6,socket.SOCK_DGRAM) as s:
            s.bind(('::1',0));self.port=s.getsockname()[1]
        # No implicit download/build or substitution for the production library.
        self.library=C.CDLL(str(Path(os.environ['SB_CONTRACT_LIBRARY']).resolve()))
        for name,args,result in (
            ('new',[C.c_uint16,C.c_char_p,C.POINTER(C.c_uint8),C.c_uint64,C.c_bool],C.c_void_p),
            ('new_configured',[C.c_uint16,C.c_char_p,C.POINTER(C.c_uint8),C.c_uint64,C.c_bool,C.c_int64,C.c_int64,C.c_uint32,C.c_uint32],C.c_void_p),
            ('diagnostic',[C.c_void_p,C.POINTER(C.c_uint64),C.c_size_t],C.c_size_t),
            ('decoded',[C.c_void_p,C.POINTER(C.c_uint64),C.c_size_t],C.c_size_t),
            ('free',[C.c_void_p],None),
            ('script',[C.c_void_p,C.c_uint64,C.c_uint,C.c_int64],C.c_bool),
            ('trace',[C.c_void_p,C.POINTER(C.c_uint64),C.c_size_t],C.c_size_t),
            ('phase',[C.c_void_p],C.c_uint)):
            fn=getattr(self.library,'sb_contract_peer_'+name);fn.argtypes=args;fn.restype=result
        key=(C.c_uint8*32).from_buffer_copy(self.key)
        try:
            if limits is None:self.handle=self.library.sb_contract_peer_new(self.port,b'fixture',key,boot,qualified)
            else:self.handle=self.library.sb_contract_peer_new_configured(self.port,b'fixture',key,boot,qualified,*limits)
        finally:C.memset(key,0,32)
        if not self.handle:raise RuntimeError('Scripted loopback peer could not bind')
    def session(self,**kwargs):
        from .motion import MotionSession
        return MotionSession(Path(os.environ['SB_THREAD_LIBRARY']),'::1',self.port,
            kwargs.pop('identity','fixture'),kwargs.pop('key',self.key),expected_boot=self.boot,
            calibration_revision=7,message_floor=kwargs.pop('message_floor',0),**kwargs)
    @property
    def phase(self):return PHASES[self.library.sb_contract_peer_phase(self.handle)]
    @property
    def trace(self):
        data=(C.c_uint64*(4096*4))();count=self.library.sb_contract_peer_trace(self.handle,data,len(data))
        return [dict(at_us=data[4*i],event=EVENTS[data[4*i+1]],command=data[4*i+2],message=data[4*i+3]) for i in range(count)]
    @property
    def diagnostic(self):
        fields=('at_us','command','last_message','reason','predicate','phase','lease_until','lease_origin','lease_error','last_sent','start_local','session_until',
                'current_valid','lifetime_valid','current_error','lifetime_error','probe','clock_reference','lower','upper')
        data=(C.c_uint64*20)();assert self.library.sb_contract_peer_diagnostic(self.handle,data,20)==20
        if not data[0]:return None
        row=dict(zip(fields,data));row['reason']='none accepted stale invalid busy unqualified reference power clock connection deadline control io stopped finished'.split()[row['reason']]
        row['phase']=PHASES[row['phase']]
        for field in ('lower','upper'):row[field]=C.c_int64(row[field]).value
        return row
    @property
    def decoded_requests(self):
        # Passive fixed-size copy. Does not advance the peer clock/state or query a device.
        names=('received_us','connection','kind','calibration','boot','message','command','probe',
               'sent_us','start_us','origin_um','target_um','speed_um_s','accel_um_s2')
        data=(C.c_uint64*(4096*14))();count=self.library.sb_contract_peer_decoded(self.handle,data,len(data))
        rows=[dict(zip(names,data[i*14:(i+1)*14])) for i in range(count)]
        for row in rows:
            for field in ('origin_um','target_um'):row[field]=C.c_int64(row[field]).value
        return rows
    def script(self,command,event,synthetic_height_um=0):
        code={'ready':1,'synthetic_terminal':2,'synthetic_off':3}[event]
        return self.library.sb_contract_peer_script(self.handle,command,code,synthetic_height_um)
    def close(self):
        if self.handle:self.library.sb_contract_peer_free(self.handle);self.handle=None
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

def wait(predicate,timeout=6):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=predicate()
        if value:return value
        time.sleep(.002)
    raise AssertionError('Bounded scripted application wait expired')

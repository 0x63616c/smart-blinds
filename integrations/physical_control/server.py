"""Explicit loopback HA control bridge; no device discovery or commissioning."""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from integrations.physical_bridge.server import Handler as ReadOnlyHandler, load_pairings
from integrations.thread_bridge.selection import Selection
from .service import PhysicalControl

class ControlServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,token,bridge,port=8767):
        if type(token) is not str or len(token)<32 or any(c.isspace() for c in token):raise ValueError('Invalid token')
        self.token,self.bridge=token,bridge
        super().__init__(('127.0.0.1',port),Handler)
    def server_close(self):
        super().server_close();self.bridge.close()

class Handler(ReadOnlyHandler):
    def do_GET(self):
        if not self.authorized():return
        if self.path!='/v3/state':self.reply(404,{'error':'not_found'});return
        self.reply(200,self.server.bridge.state())
    def do_POST(self):
        if not self.authorized():return
        if self.path not in ('/v3/move','/v3/stop'):self.reply(404,{'error':'not_found'});return
        try:
            self.connection.settimeout(1)
            if self.headers.get('Transfer-Encoding'):raise ValueError()
            length=int(self.headers.get('Content-Length','-1'))
            if not 0<=length<=1024:raise ValueError()
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError()
            value=json.loads(raw)
            if type(value) is not dict:raise ValueError()
            if self.path=='/v3/stop':
                if value:raise ValueError()
                result=self.server.bridge.stop()
            else:
                if set(value)!={'target','position','align'}:raise ValueError()
                result=self.server.bridge.move(value['target'],value['position'],align=value['align'])
            self.reply(202,result)
        except (ValueError,TypeError,TimeoutError):self.reply(400,{'error':'invalid_intent'})
        except RuntimeError:self.reply(409,{'error':'unavailable_or_busy'})


def load_selections(path,pairings):
    if path is None:return []
    value=json.loads(path.read_text())
    if type(value) is not dict or set(value)!={'version','devices'} or type(value['version']) is not int or value['version']!=1 or type(value['devices']) is not list:
        raise ValueError('Invalid explicit selection file')
    paired={p.device_id:p for p in pairings};result=[]
    fields={'id','boot','calibration','low_um','high_um','max_speed_um_s','max_accel_um_s2','commissioning_id','commissioned'}
    for item in value['devices']:
        if type(item) is not dict or set(item)!=fields or item['id'] not in paired:raise ValueError('Invalid explicit selection')
        p=paired[item['id']]
        if item['boot']!=f'{p.boot:016x}':raise ValueError('Selection boot mismatch')
        s=Selection(p.device_id,p.host,p.port,p.identity,p.key,p.boot,*(item[k] for k in
            ('calibration','low_um','high_um','max_speed_um_s','max_accel_um_s2','commissioning_id','commissioned')))
        s.validate();result.append(s)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pairings','token-file','library'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--selections',type=Path)
    parser.add_argument('--ledger',type=Path)
    parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args()
    ident,pairings=load_pairings(args.pairings)
    selections=load_selections(args.selections,pairings)
    bridge=PhysicalControl(ident,pairings,selections,args.ledger,args.library)
    try:
        with ControlServer(args.token_file.read_text().strip(),bridge,args.port) as server:server.serve_forever()
    finally:bridge.close()
if __name__=='__main__':main()

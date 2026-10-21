"""Actual HA/HTTP/DTLS application lifecycle with explicitly SCRIPTED evidence.

No MotionExecutor, motor timing, measured fabric level or GPIO OFF is tested.
"""
import json
import os
from pathlib import Path
import tempfile
import threading
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest
from integrations.physical_bridge.service import Pairing
from integrations.physical_control.service import PhysicalControl
from integrations.physical_control.server import ControlServer
from integrations.thread_bridge.ledger import Ledger
from integrations.thread_bridge.selection import Selection
from integrations.thread_transport.contract_fixture import ContractPeer,wait
# Import the actual custom package before HA mounts its test configuration.
from custom_components.smart_blinds.api import validate_control_state

TOKEN='disposable-scripted-application-token-00000000'

@pytest.mark.parametrize('qualified',[False,True])
async def test_scripted_one_owner_ha_http_dtls_lifecycle(hass,socket_enabled,qualified):
    def start():
        folder=tempfile.TemporaryDirectory();path=Path(folder.name)/'ledger'
        peer=ContractPeer(qualified=qualified)
        selected=Selection('blind','::1',peer.port,'fixture',peer.key,peer.boot,7,0,100000,30000,60000,'scripted-fixture-only',True)
        pair=Pairing('blind','Scripted fixture','::1',peer.port,'fixture',peer.key,peer.boot)
        with Ledger(path,create=True) as ledger:
            if qualified:ledger.enroll(selected,command_floor=0,message_floor=0)
        service=PhysicalControl('contract-fixture',[pair],[selected] if qualified else [],path,Path(os.environ['SB_THREAD_LIBRARY']))
        try:wait(lambda:service.state()['devices'][0]['available'])
        except BaseException:service.close();peer.close();folder.cleanup();raise
        server=ControlServer(TOKEN,service,port=0);worker=threading.Thread(target=server.serve_forever);worker.start()
        return folder,path,selected,peer,service,server,worker
    folder,path,selected,peer,service,server,worker=await hass.async_add_executor_job(start)
    entry=MockConfigEntry(domain='smart_blinds',unique_id='contract-fixture',data={
        'base_url':f'http://127.0.0.1:{server.server_port}','access_token':TOKEN,'mode':'physical_control'})
    entry.add_to_hass(hass);passed=False;stage='ha-setup'
    try:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry=er.async_get(hass)
        cover=registry.async_get_entity_id('cover','smart_blinds','contract-fixture:room:cover')
        assert cover is not None
        initial=service.actors['blind'].observation.received_us
        if not qualified:
            assert hass.states.get(cover).state=='unavailable'
            with pytest.raises(HomeAssistantError):await entry.runtime_data.move('room',55)
            assert service.last_operation is None
            assert not peer.script(1,'ready')
            assert not any(t['event']=='queued' for t in peer.trace)
        else:
            assert hass.states.get(cover).attributes.get('current_position') is None
            stage='ha-move'
            await hass.services.async_call('cover','set_cover_position',{'entity_id':cover,'position':55},blocking=True)
            await hass.async_add_executor_job(wait,lambda:peer.phase in ('preparing','fault'))
            assert peer.phase=='preparing'
            command=service.last_operation.reservations['blind'].command
            assert not peer.script(command+1,'ready')
            assert not peer.script(command,'synthetic_off')
            assert not service.last_operation.job.prepared  # queue receipt is not READY
            stage='script-ready';assert peer.script(command,'ready')
            await hass.async_add_executor_job(wait,lambda:peer.phase in ('moving','fault'))
            assert peer.phase=='moving'
            assert service.inflight is not None
            assert not peer.script(command,'synthetic_off')
            stage='script-terminal';assert peer.script(command,'synthetic_terminal',55000)
            await hass.async_add_executor_job(wait,lambda:service.last_operation.workers['blind'].terminal)
            assert service.phase!='complete'
            assert service.last_operation.workers['blind'].completion() is None
            stage='script-off';assert peer.script(command,'synthetic_off')
            await hass.async_add_executor_job(wait,lambda:service.inflight is None and service.phase in ('complete','aborted'))
            assert service.phase=='complete'
            await hass.async_add_executor_job(wait,lambda:service.actors['blind'].observation.received_us>initial)
            stage='ha-state';await entry.runtime_data.async_refresh()
            assert hass.states.get(cover).attributes['current_position']==55
            validate_control_state(service.state())
            assert service.last_operation.workers['blind'].completion().settled_off
            assert len([t for t in peer.trace if t['event']=='connected'])==1
            assert service.actors['blind'].session.handshakes==1
            events=[t['event'] for t in peer.trace]
            for event in ('queued','consume_prepare','script_ready','consume_commit','scheduled_start',
                          'script_or_stop_settling','script_off'):assert event in events
            assert events.index('queued')<events.index('script_ready')<events.index('consume_commit')
            assert events.index('scheduled_start')<events.index('script_off')<len(events)-1
            assert events[-1]=='telemetry'
        assert await hass.config_entries.async_unload(entry.entry_id)
        passed=True
    finally:
        evidence=dict(evidence_kind='synthetic_application_contract',hardware_qualified=False,
            qualified_fixture=qualified,passed=passed,stage=stage,peer_phase=peer.phase,trace=peer.trace,
            application=service.state(),workers=[] if service.last_operation is None else
            [dict(name=name,failure=w.failure,calls=w.calls,reusable=w.reusable) for name,w in service.last_operation.workers.items()])
        if dest:=os.environ.get('SB_CONTRACT_EVIDENCE'):
            with open(dest,'a') as f:f.write(json.dumps(evidence,sort_keys=True)+'\n')
        def close():
            server.shutdown();server.server_close();worker.join(1);peer.close()
        await hass.async_add_executor_job(close)
        if qualified and passed:
            with Ledger(path) as ledger:assert ledger.floor(selected)==(1,4096)
        folder.cleanup()

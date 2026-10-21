"""Real HA cover -> authenticated loopback HTTP -> sole native DTLS actor."""
import asyncio
from pathlib import Path
import tempfile
import threading
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest
from integrations.physical_control.test_actor import selection,pairing,wait
from integrations.physical_control.service import PhysicalControl
from integrations.physical_control.server import ControlServer
from integrations.thread_bridge.ledger import Ledger
from integrations.thread_transport.test_motion import MotionPeer
from integrations.thread_transport.test_transport import LIBRARY
from custom_components.smart_blinds.api import validate_control_state,BridgeError

TOKEN='disposable-loopback-test-token-00000000000'

@pytest.mark.parametrize('qualified',[False,True])
async def test_real_physical_cover_lifecycle(hass,socket_enabled,qualified):
    def start():
        folder=tempfile.TemporaryDirectory();path=Path(folder.name)/'ledger';peer=MotionPeer()
        selected=selection(peer)
        with Ledger(path,create=True) as l:
            if qualified:l.enroll(selected,command_floor=0,message_floor=0)
        service=PhysicalControl('control-fixture',[pairing(peer)],[selected] if qualified else [],path,LIBRARY)
        wait(lambda:service.state()['devices'][0]['available'])
        server=ControlServer(TOKEN,service,port=0);worker=threading.Thread(target=server.serve_forever);worker.start()
        return folder,peer,service,server,worker
    folder,peer,service,server,worker=await hass.async_add_executor_job(start)
    entry=MockConfigEntry(domain='smart_blinds',unique_id='control-fixture',data={
        'base_url':f'http://127.0.0.1:{server.server_port}','access_token':TOKEN,'mode':'physical_control'})
    entry.add_to_hass(hass)
    try:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry=er.async_get(hass)
        cover=registry.async_get_entity_id('cover','smart_blinds','control-fixture:room:cover')
        assert cover is not None
        if not qualified:
            assert hass.states.get(cover).state=='unavailable'
            with pytest.raises(HomeAssistantError):await entry.runtime_data.move('room',55)
            assert service.last_operation is None
            assert peer.off
        else:
            # No simulated position appears before actual preflight/measurements.
            assert hass.states.get(cover).attributes.get('current_position') is None
            await hass.services.async_call('cover','set_cover_position',{'entity_id':cover,'position':55},blocking=True)
            def done():return service.inflight is None and service.phase in ('complete','aborted')
            await hass.async_add_executor_job(wait,done,10)
            assert service.phase=='complete',(service.reason,peer.diagnostics)
            assert peer.off
            await entry.runtime_data.async_refresh()
            assert hass.states.get(cover).attributes['current_position']==55
            assert service.last_operation.workers['blind'].completion().settled_off
        assert await hass.config_entries.async_unload(entry.entry_id)
    finally:
        def close():
            server.shutdown();server.server_close();worker.join(1);peer.close();folder.cleanup()
        await hass.async_add_executor_job(close)


def test_control_mode_and_unknown_authority_are_not_response_selected():
    with pytest.raises(BridgeError):validate_control_state({'schema_version':1,'mode':'simulation'})

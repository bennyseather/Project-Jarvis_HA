"""Narrow, supported-API dashboard edits. Default is a read-only plan.

Never dump the full configuration or Supervisor token. No devices operated.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

DOORS = frozenset(('binary_sensor.magnet_sensor_porch','binary_sensor.magnet_sensor_main_door',
                   'binary_sensor.magnet_sensor_master_bedroom','binary_sensor.ewelink_snzb_04p'))
MOWER = 'lawn_mower.edward_scissorhand_lawn_mower'


def plan(config):
    result = deepcopy(config)
    counts = {'mower':0,'door_badges':0,'calendar':0}
    def walk(node):
        if isinstance(node,list):
            for child in node: walk(child)
        elif isinstance(node,dict):
            kind, entity = node.get('type'), node.get('entity')
            if kind == 'custom:jarvis-mower-card' and entity == MOWER:
                node['out_of_season'] = True
                counts['mower'] += 1
            elif kind == 'custom:jarvis-entity-badge' and entity in DOORS:
                node['display_class'] = 'door'
                counts['door_badges'] += 1
            elif kind == 'custom:jarvis-calendar-card':
                node['view'] = 'day'
                counts['calendar'] += 1
            for child in list(node.values()):
                if isinstance(child,(dict,list)):walk(child)
    walk(result)
    if counts != {'mower':2,'door_badges':4,'calendar':1}:
        raise ValueError('Dashboard structure changed; inspect before editing')
    return result, counts


async def main(apply=False):
    import websockets
    token = os.environ['SUPERVISOR_TOKEN']
    async with websockets.connect('ws://supervisor/core/websocket',open_timeout=10) as ws:
        await asyncio.wait_for(ws.recv(),10)
        await ws.send(json.dumps({'type':'auth','access_token':token}))
        assert json.loads(await asyncio.wait_for(ws.recv(),10))['type']=='auth_ok'
        serial=0
        async def call(kind,**args):
            nonlocal serial
            serial+=1
            await ws.send(json.dumps({'id':serial,'type':kind,**args}))
            while True:
                reply=json.loads(await asyncio.wait_for(ws.recv(),15))
                if reply.get('id') == serial:
                    if not reply.get('success'):raise RuntimeError('Dashboard API rejected operation')
                    return reply.get('result')
        current=await call('lovelace/config',url_path='jarvis-yoga')
        updated,counts=plan(current)
        if not apply:
            print(json.dumps({'read_only_plan':True,'target':'jarvis-yoga','edits':counts,'already_applied':current==updated}))
            return
        if current==updated:
            print(json.dumps({'already_applied':True,'edits':counts}));return
        backup=Path('/homeassistant/.jarvis-recovery')/('household-ui-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(mode=0o700,parents=True)
        with (backup/'dashboard.before.json').open('x') as stream:
            os.fchmod(stream.fileno(),0o600);json.dump(current,stream)
        if await call('lovelace/config',url_path='jarvis-yoga') != current:
            raise RuntimeError('Concurrent dashboard edit; no changes applied')
        await call('lovelace/config/save',url_path='jarvis-yoga',config=updated)
        verified=await call('lovelace/config',url_path='jarvis-yoga')
        if verified != updated:
            raise RuntimeError('Dashboard read-back mismatch; inspect backup and concurrent edits')
        print(json.dumps({'applied_verified':True,'target':'jarvis-yoga','edits':counts,'private_backup':str(backup)}))


if __name__=='__main__':asyncio.run(main(apply=sys.argv[1:]==['--apply']))

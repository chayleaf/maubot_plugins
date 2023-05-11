import aiohttp
import hashlib
import json
from typing import Type, Optional

from mautrix.types import UserID, RoomID, EventType
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command, event

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy('api_url')
        helper.copy('room_ids')

class Valetudo(Plugin):
    async def start(self) -> None:
        await super().start()
        self.on_external_config_update()

    def on_external_config_update(self):
        self.config.load_and_update()

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    async def stop(self) -> None:
        pass

    @command.new('vacuum', help='Clean a room')
    @command.argument('text', pass_raw=True, required=True)
    async def cmd_vacuum(self, evt: MessageEvent, text: str = '') -> None:
        api = self.config['api_url']
        rooms = text.lower().split()
        room_ids = set()
        iters = 1
        for room in rooms:
            if room == '2':
                iters = int(room)
                continue
            if room not in self.config['room_ids'].keys():
                await evt.respond(f'Available rooms: {", ".join(self.config["room_ids"].keys())}. Add "2" to clean two times. API: {api}')
                return
            ids = self.config['room_ids'][room]
            if isinstance(ids, list):
                for id in ids:
                    room_ids.add(str(id))
            else:
                room_ids.add(str(ids))
        if len(room_ids) == 0:
            await evt.respond(f'Available rooms: {", ".join(self.config["room_ids"].keys())}. Add "2" to clean two times. API: {api}')
            return
        rooms = [*room_ids]
        url = api + '/api/v2/robot/capabilities/MapSegmentationCapability'
        data = {
          "action": "start_segment_action",
          "segment_ids": rooms,
          "iterations": 1
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=data) as response:
                    if response.status == 200:
                        await evt.respond('Done!')
                    else:
                        j = await response.json()
                        await evt.respond(f'Status {response.status}. API returned: {j}')
        except Exception as e:
            await evt.respond(f'Exception: {e}')
            raise


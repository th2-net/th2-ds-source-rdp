#  Copyright 2023 Exactpro (Exactpro Systems Limited)
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from typing import Sequence, Optional
from th2_data_services.event_tree import IETCDriver
from th2_data_services.event_tree.etc_driver import Th2EventType
from th2_data_services.event_tree.exceptions import FieldIsNotExist
from th2_data_services.data_source.lwdp_v2_1.commands.http import GetEventsById
from th2_data_services.data_source.lwdp_v2_1.interfaces.data_source import ILwDPDataSource
from th2_data_services.data_source.lwdp_v2_1.struct import EventStruct, http_event_struct
from th2_data_services.data_source.lwdp_v2_1.stub_builder import http_event_stub_builder


class HttpETCDriver(IETCDriver):
    def __init__(
        self,
        data_source: ILwDPDataSource = None,
        event_struct: EventStruct = http_event_struct,
        use_stub: bool = False,
    ):
        """The driver for EventsTreeCollection (HTTP).

        Args:
            event_struct: Structure of the event.
            data_source: LwDPDataSource object.
            use_stub: Build stubs or not.
        """
        super().__init__(data_source=data_source, event_struct=event_struct, use_stub=use_stub)

    def get_events_by_id_from_source(self, ids: Sequence) -> list:
        """Downloads the list of events from the provided data_source.

        Args:
            ids: Events IDs

        Returns:
            list: TH2-Events
        """
        events = self._data_source.command(GetEventsById(ids, use_stub=self.use_stub))
        return events

    def get_event_id(self, event: Th2EventType) -> str:
        """Gets event id from the event.

        Returns:
            Event id.

        Raises:
            FieldIsNotExist: If the event doesn't have an 'event id' field.
        """
        try:
            return event[self.event_struct.EVENT_ID]
        except KeyError:
            raise FieldIsNotExist(self.event_struct.EVENT_ID)

    def get_event_name(self, event: Th2EventType) -> str:
        """Gets event name from the event.

        Returns:
            Event name.

        Raises:
            FieldIsNotExist: If the event doesn't have an 'event name' field.
        """
        try:
            return event[self.event_struct.NAME]
        except KeyError:
            raise FieldIsNotExist(self.event_struct.NAME)

    def get_parent_event_id(self, event) -> Optional[str]:
        """Gets parent event id from event.

        Returns:
            Parent event id.
        """
        return event.get(self.event_struct.PARENT_EVENT_ID)

    def build_stub_event(self, id_: str) -> Th2EventType:
        """Builds stub event.

        Args:
            id_: Event Id.

        Returns:
            Stub event.
        """
        return http_event_stub_builder.build({self.event_struct.EVENT_ID: id_})

    def stub_event_name(self):
        return http_event_stub_builder.template[self.event_struct.NAME]

#  Copyright 2024 Exactpro (Exactpro Systems Limited)
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

from typing import Union

from th2_data_services.data_source.lwdp.data_source import DataSource as LwdpDataSource
from th2_data_services.data_source.lwdp.struct import http_event_struct, http_message_struct
from th2_data_services.data_source.lwdp.stub_builder import http_event_stub_builder, http_message_stub_builder
from th2_data_services.interfaces import IEventStruct, IMessageStruct, IEventStub, IMessageStub
from th2_data_services.data_source.rdp.source_api.http import API

class DataSource(LwdpDataSource):
    def __init__(
        self,
        url: str,
        chunk_length: int = 65536,
        event_struct: IEventStruct = http_event_struct,
        message_struct: IMessageStruct = http_message_struct,
        event_stub_builder: IEventStub = http_event_stub_builder,
        message_stub_builder: IMessageStub = http_message_stub_builder,
        check_connect_timeout: Union[int, float] = 5
    ):
        super().__init__(url, chunk_length, event_struct, message_struct, event_stub_builder, message_stub_builder, check_connect_timeout)
        self._provider_api = API(url, chunk_length)


HTTPDataSource = DataSource

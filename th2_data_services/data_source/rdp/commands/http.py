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

from typing import override, List

from th2_data_services.data_source.lwdp.commands.http import GetBooks as LwdpGetBooks
from th2_data_services.data_source.lwdp.interfaces.command import IHTTPCommand
from th2_data_services.data_source.rdp.data_source.http import DataSource
from th2_data_services.data_source.rdp.source_api.http import API


class GetBooks(LwdpGetBooks):
    @override
    def handle(self, data_source: DataSource) -> List[str]:
        return list(map(lambda book: book['name'], super().handle(data_source)))


class GetMessageAliases(IHTTPCommand):
    @override
    def __init__(self, book_id: str):
        """GetMessageAliases constructor."""
        super().__init__()
        self._book_id = book_id

    @override
    def handle(self, data_source: DataSource) -> List[str]:
        api: API = data_source.source_api
        url = api.get_url_get_message_aliases(self._book_id)
        return api.execute_request(url).json()


class GetEventScopes(IHTTPCommand):
    @override
    def __init__(self, book_id: str):
        """GetEventScopes constructor."""
        super().__init__()
        self._book_id = book_id

    @override
    def handle(self, data_source: DataSource) -> List[str]:
        api: API = data_source.source_api
        url = api.get_url_get_scopes(self._book_id)
        return api.execute_request(url).json()

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

from typing import override

from th2_data_services.data_source.lwdp.source_api import API as LwdpAPI

class API(LwdpAPI):
    @override
    def __encode_url(self, url: str) -> str:
        return self._API__encode_url(url)

    @override
    def get_url_get_books(self) -> str:
        """REST-API `books` call returns a list of books in cradleAPI."""
        return self.__encode_url(f"{self._url}/bookIds")

    @override
    def get_url_get_message_aliases(self, book_id: str, start_timestamp: int = None, end_timestamp: int = None,
                                    chunked_size: int = None) -> str:
        """REST-API `messageStreams?bookId={bookID}` call returns a list of aliases in cradleAPI."""
        url = f"{self._url}/messageStreams?bookId={book_id}"
        return self.__encode_url(url)

    @override
    def get_url_get_scopes(self, book_id: str, start_timestamp: int = None, end_timestamp: int = None,
                           chunked_size: int = None) -> str:
        """REST-API `scopeIds?bookId={bookID}` call returns a list of scopes in cradleAPI."""
        url = f"{self._url}/scopeIds?bookId={book_id}"
        return self.__encode_url(url)


HTTPAPI = API

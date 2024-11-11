#  Copyright 2022-2023 Exactpro (Exactpro Systems Limited)
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

# LOG import logging
from http import HTTPStatus
from typing import List, Generator, Optional, Union

import requests
from requests import Response
from urllib3 import PoolManager, exceptions
from urllib.parse import quote

from th2_data_services.data_source.lwdp_v2_1.interfaces.source_api import IHTTPSourceAPI


# LOG logger = logging.getLogger("th2_data_services")
# LOG logger.setLevel(logging.DEBUG)


class HTTPAPI(IHTTPSourceAPI):
    def __init__(self, url: str, chunk_length: int = 65536):
        """HTTP API.

        Args:
            url: HTTP data source url.
            chunk_length: How much of the content to read in one chunk.
        """
        self._url = self.__normalize_url(url)
        self._chunk_length = chunk_length

    def __normalize_url(self, url):
        if url is None:
            return url

        pos = len(url) - 1
        while url[pos] == "/" and pos >= 0:
            pos -= 1

        return url[: pos + 1]

    def __encode_url(self, url: str) -> str:
        return quote(url.encode(), "/:&?=")

    def get_url_get_books(self) -> str:
        """REST-API `books` call returns a list of books in cradleAPI."""
        return self.__encode_url(f"{self._url}/books")

    def get_url_get_scopes(
        self,
        book_id: str,
        start_timestamp: int = None,
        end_timestamp: int = None,
        chunked_size: int = None,
    ) -> str:
        """REST-API `book/{bookID}/event/scopes/sse` call creates an sse channel of event scopes in book named bookID."""
        url = f"{self._url}/book/{book_id}/event/scopes/sse?"

        kwargs = {
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "chunkedSize": chunked_size,
        }

        url += "&".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
        return self.__encode_url(url)

    def get_url_get_message_aliases(
        self,
        book_id: str,
        start_timestamp: int = None,
        end_timestamp: int = None,
        chunked_size: int = None,
    ) -> str:
        """REST-API `book/{bookID}/message/aliases/sse` call creates an sse channel of message aliases in book named bookID."""
        url = f"{self._url}/book/{book_id}/message/aliases/sse?"

        kwargs = {
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "chunkedSize": chunked_size,
        }

        url += "&".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
        return self.__encode_url(url)

    def get_url_get_message_groups(
        self,
        book_id: str,
        start_timestamp: int = None,
        end_timestamp: int = None,
        chunked_size: int = None,
    ) -> str:
        """REST-API `book/{bookID}/message/groups/sse` call creates an sse channel of message groups in book named bookID."""
        url = f"{self._url}/book/{book_id}/message/groups/sse?"

        kwargs = {
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "chunkedSize": chunked_size,
        }

        url += "&".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
        return self.__encode_url(url)

    def get_url_find_event_by_id(self, event_id: str) -> str:
        """REST-API `event` call returns a single event with the specified id."""
        return self.__encode_url(f"{self._url}/event/{event_id}")

    def get_url_find_message_by_id(self, message_id: str, only_raw: bool = False) -> str:
        """REST-API `message` call returns a single      message with the specified id."""
        return self.__encode_url(f"{self._url}/message/{message_id}?onlyRaw={only_raw}")

    def get_url_get_pages_info_all(self, book_id: str):
        """REST-API `search/see/page-infos/{$BOOK_ID}/all` call returns page information with the specified timeframe."""
        url = f"{self._url}/search/sse/page-infos/{book_id}/all"
        return self.__encode_url(url)

    def get_url_get_pages_info(
        self, book_id: str, start_timestamp: int, end_timestamp: int, limit=None
    ):
        """REST-API `search/see/page-infos` call returns page information with the specified timeframe."""
        url = f"{self._url}/search/sse/page-infos?"
        params = {
            "bookId": book_id,
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
        }
        if limit:
            params["resultCountLimit"] = limit
        url += "&".join(f"{k}={v}" for k, v in params.items())
        return self.__encode_url(url)

    def get_url_search_sse_events(
        self,
        start_timestamp: int,
        book_id: str,
        scope: str,
        end_timestamp: Optional[int] = None,
        parent_event: Optional[str] = None,
        search_direction: Optional[str] = "next",
        result_count_limit: Union[int, float] = None,
        filters: Optional[str] = None,
    ) -> str:
        """REST-API `search/sse/events` call create a sse channel of event metadata that matches the filter.

        https://github.com/th2-net/th2-rpt-data-provider#sse-requests-api
        """
        # +TODO - add __split_requests here like in get_url_search_sse_messages
        kwargs = {
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "parentEvent": parent_event,
            "searchDirection": search_direction,
            "resultCountLimit": result_count_limit,
            "bookId": book_id,
            "scope": scope,
        }

        query = ""
        url = f"{self._url}/search/sse/events?"
        for k, v in kwargs.items():
            if v is None:
                continue
            else:
                query += f"&{k}={v}"
        url = f"{url}{query[1:]}"
        if filters is not None:
            url += filters
        return self.__encode_url(url)

    def get_url_search_sse_messages(
        self,
        start_timestamp: int,
        book_id: str,
        message_ids: List[str] = None,
        stream: List[str] = None,
        search_direction: Optional[str] = "next",
        result_count_limit: Union[int, float] = None,
        end_timestamp: Optional[int] = None,
        response_formats: List[str] = None,
        keep_open: bool = False,
        max_url_length=2048,
    ) -> List[str]:
        """REST-API `search/sse/messages` call create a sse channel of messages that matches the filter.

        https://github.com/th2-net/th2-rpt-data-provider#sse-requests-api
        """
        kwargs = {
            "startTimestamp": start_timestamp,
            "messageId": message_ids,
            "stream": stream,
            "searchDirection": search_direction,
            "resultCountLimit": result_count_limit,
            "endTimestamp": end_timestamp,
            "responseFormat": response_formats,
            "keepOpen": keep_open,
            "bookId": book_id,
        }
        if stream:
            kwargs["stream"] = None
            optional = [f"&stream={x}" for x in stream]
        else:
            kwargs["messageId"] = None
            optional = [f"&messageId={x}" for x in message_ids]

        query = ""
        url = f"{self._url}/search/sse/messages?"
        for k, v in kwargs.items():
            if v is None:
                continue
            if k in ["stream", "responseFormat", "messageId"]:
                for item in v:
                    query += f"&{k}={item}"
            else:
                query += f"&{k}={v}"
        url = f"{url}{query[1:]}"
        urls = self.__split_requests(url, optional, max_url_length)
        return [self.__encode_url(url) for url in urls]

    def get_url_search_messages_by_groups(
        self,
        start_timestamp: int,
        end_timestamp: int,
        book_id: str,
        groups: List[str],
        streams: List[str] = None,
        sort: bool = None,
        response_formats: List[str] = None,
        keep_open: bool = None,
        max_url_length=2048,
    ) -> List[str]:
        """REST-API `search/sse/messages/group` call creates a sse channel of messages groups in specified time range.

        Args:
            start_timestamp: Sets the search starting point. Expected in nanoseconds. One of the 'start_timestamp'
                or 'resume_from_id' must not absent.
            end_timestamp: Sets the timestamp to which the search will be performed, starting with 'start_timestamp'.
                Expected in nanoseconds.
            book_id: book ID for requested groups.
            groups: List of groups to search messages by
            streams: List of streams to search messages by.
            sort: Enables message sorting in the request
            response_formats: Response format
            keep_open: If true, keeps pulling for new message until don't have one outside the requested range
            max_url_length: API request url max length.

        Returns:
            Iterable object which return messages as parts of streaming response or message stream pointers.
        """
        kwargs = {
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "bookId": book_id,
            "sort": sort,
            "responseFormat": response_formats,
            "keepOpen": keep_open,
            "stream": streams,
        }
        groups = [f"&group={x}" for x in groups]  # "&group=".join(groups)  #
        options = []
        url = f"{self._url}/search/sse/messages/group?"

        for k, v in kwargs.items():
            if v is None:
                continue
            if k in ["responseFormat", "stream"]:
                for item in v:
                    options.append(self._option(k, item))
            else:
                options.append(self._option(k, v))

        options_url = "&".join(options)
        url = f"{url}{options_url}"
        urls = self.__split_requests(url, groups, max_url_length)
        return [self.__encode_url(url) for url in urls]

    def get_download_messages(
        self,
        start_timestamp: int,
        end_timestamp: int,
        book_id: str,
        groups: List[str],
        stream: List[str],
        sort: bool = None,
        response_formats: List[str] = None,
        keep_open: bool = None,
        max_url_length=2048,
    ) -> List[str]:
        """REST-API `download/messages` call downloads messages in specified time range in json format.

        Args:
            start_timestamp: Sets the search starting point. Expected in nanoseconds. One of the 'start_timestamp'
                or 'resume_from_id' must not absent.
            end_timestamp: Sets the timestamp to which the search will be performed, starting with 'start_timestamp'.
                Expected in nanoseconds.
            book_id: book ID for requested groups.
            groups: List of groups to search messages by
            stream: List of streams to search messages by.
            sort: Enables message sorting in the request
            response_formats: Response format
            keep_open: If true, keeps pulling for new message until don't have one outside the requested range
            max_url_length: API request url max length.

        Returns:
            URL for downloading messages.
        """
        kwargs = {
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "bookId": book_id,
            "sort": sort,
            "responseFormat": response_formats,
            "keepOpen": keep_open,
            "stream": stream,
        }
        groups = [f"&group={x}" for x in groups]  # "&group=".join(groups)  #
        options = []
        url = f"{self._url}/download/messages?"

        for k, v in kwargs.items():
            if v is None:
                continue
            if k in ["responseFormat", "stream"]:
                for item in v:
                    options.append(self._option(k, item))
            else:
                options.append(self._option(k, v))

        options_url = "&".join(options)
        url = f"{url}{options_url}"
        urls = self.__split_requests(url, groups, max_url_length)
        return [self.__encode_url(url) for url in urls]

    def execute_sse_request(self, url: str) -> Generator[bytes, None, None]:
        """Create stream connection.

        Args:
            url: Url.

        Yields:
             str: Response stream data.
        """
        headers = {"Accept": "text/event-stream"}
        http = PoolManager()
        response = http.request(method="GET", url=url, headers=headers, preload_content=False)

        if response.status != HTTPStatus.OK:
            for s in HTTPStatus:
                if s == response.status:
                    raise exceptions.HTTPError(
                        f"{s.value} {s.phrase} ({s.description}). {response.data}"
                    )
            raise exceptions.HTTPError(f"Http returned bad status: {response.status}")

        yield from response.stream(self._chunk_length)

        response.release_conn()

    def execute_request(self, url: str, headers: dict = None, stream=False) -> Response:
        """Sends a GET request to provider.

        Args:
            url: Url for a get request to rpt-data-provider.
            headers: Dictionary of headers for request.
            stream: Gets response as a stream if True.

        Returns:
            requests.Response: Response data.
        """
        return requests.get(url, headers=headers, stream=stream)

    def __split_requests(self, fixed_url: str, optional: List[str], max_url_len: int):
        if len(fixed_url + max(optional, key=len)) >= max_url_len:
            raise Exception(
                f"Fixed url part ({len(fixed_url)}) >= than max url len ({max_url_len})"
            )

        result_urls = []
        url = fixed_url

        for s in optional:
            if len(url) + len(s) >= max_url_len:
                result_urls.append(url)
                url = fixed_url + s
                continue
            url += s
        if url:
            result_urls.append(url)

        return result_urls

    def _option(self, opt_name, value):
        return f"{opt_name}={value}"

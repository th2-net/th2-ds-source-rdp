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
from abc import abstractmethod
from typing import List, Optional, Union, Generator, Any
from datetime import datetime
from functools import partial
from shutil import copyfileobj

import requests
from th2_data_services.data import Data
from th2_data_services.exceptions import EventNotFound, MessageNotFound
from th2_data_services.utils.converters import DatetimeConverter, ProtobufTimestampConverter

from th2_data_services.data_source.lwdp_v2_1 import Page
from th2_data_services.data_source.lwdp_v2_1.interfaces.command import IHTTPCommand
from th2_data_services.data_source.lwdp_v2_1.data_source.http import HTTPDataSource
from th2_data_services.data_source.lwdp_v2_1.source_api.http import HTTPAPI
from th2_data_services.data_source.lwdp_v2_1.streams import Streams, Stream
from th2_data_services.utils.sse_client import SSEClient
from th2_data_services.data_source.lwdp_v2_1.adapters.adapter_sse import (
    SSEAdapter,
    DEFAULT_BUFFER_LIMIT,
)
from th2_data_services.utils.decode_error_handler import UNICODE_REPLACE_HANDLER
from th2_data_services.data_source.lwdp_v2_1.filters.event_filters import LwDPEventFilter
from th2_data_services.data_source.lwdp_v2_1.utils import (
    _check_datetime,
    _check_list_or_tuple,
    _check_response_formats,
)
from th2_data_services.data_source.lwdp_v2_1.utils._misc import (
    get_utc_datetime_now,
    _get_response_format,
)
from th2_data_services.data_source.lwdp_v2_1.utils.json import BufferedJSONProcessor
from th2_data_services.data_source.lwdp_v2_1.page import PageNotFound

Event = dict


# LOG import logging

# LOG logger = logging.getLogger(__name__)


class SSEHandlerClassBase(IHTTPCommand):
    def __init__(
        self,
        cache: bool,
        buffer_limit: int,  # e.g. DEFAULT_BUFFER_LIMIT,
        char_enc: str,  # e.g. "utf-8",
        decode_error_handler: str,  # e.g. UNICODE_REPLACE_HANDLER,
    ):
        """SSEHandlerClassBase Constructor.

        Args:
            cache (bool): Cache Status
            buffer_limit (int): SSEAdapter BufferedJSONProcessor buffer limit.
            char_enc (Optional, str): Encoder, Defaults To 'UTF-8'
            decode_error_handler (Optional, str): Decode Error Handler, Defaults To 'UNICODE_REPLACE_HANDLER'
        """
        self._current_handle_function = self._data_object
        self._char_enc = char_enc
        self._decode_error_handler = decode_error_handler
        self._sse_handler = SSEAdapter(BufferedJSONProcessor(buffer_limit))
        self._cache = cache

    def return_sse_bytes_stream(self):
        """Returns SSEBytes Stream.

        Returns:
           Generator[bytes, None, None]
        """
        self._current_handle_function = self._sse_bytes_stream
        return self

    def return_sse_events_stream(self):
        """Returns SSEEvents Stream.

        Returns:
            Generator[Event, Any, None]
        """
        self._current_handle_function = self._sse_events_stream
        return self

    def return_data_object(self):
        """Returns Parsed 'Data' Object.

        Returns:
            Data
        """
        self._current_handle_function = self._data_object
        return self

    def _sse_bytes_stream(
        self, data_source: HTTPDataSource
    ) -> Generator[bytes, None, None]:  # noqa
        api: HTTPAPI = data_source.source_api
        urls: List[str] = self._get_urls(data_source)
        for url in urls:
            # LOG             logger.info(url)
            yield from api.execute_sse_request(url)

    def _sse_events_stream(self, data_source: HTTPDataSource) -> Generator[Event, Any, None]:
        """Turns SSEByte Stream Into SSEEvent Stream.

        Args:
            data_source: HTTPDataSource

        Returns:
             Generator[Event, Any, None]
        """
        sse_bytes_stream = partial(self._sse_bytes_stream, data_source)

        client = SSEClient(
            sse_bytes_stream(),
            char_enc=self._char_enc,
            decode_errors_handler=self._decode_error_handler,
        )
        yield from client.events()

    def _data_object(self, data_source: HTTPDataSource) -> Data:
        """Parses SSEEvents Into Data Object.

        Args:
            data_source: HTTPDataSource

        Returns:
             Data
        """
        sse_events_stream = partial(self._sse_events_stream, data_source)
        data = Data(sse_events_stream).map_stream(self._sse_handler.handle).use_cache(self._cache)
        data.metadata["urls"] = self._get_urls(data_source)
        return data

    @abstractmethod
    def _get_urls(self, data_source: HTTPDataSource) -> List[str]:
        pass

    def handle(
        self, data_source: HTTPDataSource
    ) -> Union[Generator[bytes, None, None], Generator[Event, None, None], Data]:
        """Handles Stream By Handle Function, Defaults To `Data`.

        Args:
            data_source: data_source

        Returns:
            Union[Generator[bytes, None, None], Generator[Event, None, None], Data]
        """
        return self._current_handle_function(data_source)


class GetEventScopes(SSEHandlerClassBase):
    """A Class-Command for request to lw-data-provider.

    It retrieves a list of event scopes in book.

    Returns:
        dict: List[str].
    """

    def __init__(
        self,
        book_id: str,
        start_timestamp: datetime = None,
        end_timestamp: datetime = None,
        cache: bool = False,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        buffer_limit: int = DEFAULT_BUFFER_LIMIT,
    ) -> None:
        """GetEventScopes Constructor.

        If start_timestamp and end_timestamp are not provided, it returns all aliases.

        Args:
            book_id (str): Book ID.
            start_timestamp (datetime): Start Timestamp.
            end_timestamp (datetime): End Timestamp.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        super().__init__(
            cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )
        if all(timestamp is None for timestamp in (start_timestamp, end_timestamp)):
            self._all_results = True
        else:
            _check_datetime(start_timestamp)
            _check_datetime(end_timestamp)
            self._start_timestamp = DatetimeConverter.to_nanoseconds(start_timestamp)
            self._end_timestamp = DatetimeConverter.to_nanoseconds(end_timestamp)
            self._all_results = False
        self._book_id = book_id

    def _get_urls(self, data_source: HTTPDataSource):
        api = data_source.source_api
        if self._all_results:
            return [api.get_url_get_scopes(book_id=self._book_id)]
        else:
            return [
                api.get_url_get_scopes(self._book_id, self._start_timestamp, self._end_timestamp)
            ]

    def _data_object(self, data_source: HTTPDataSource) -> Data[Page]:
        """Parses SSEEvents Into Data Object.

        Args:
            data_source: HTTPDataSource

        Returns:
             Data
        """
        sse_events_stream = partial(self._sse_events_stream, data_source)
        data = Data(sse_events_stream).map_stream(self._sse_handler).use_cache(self._cache)
        data.metadata["urls"] = self._get_urls(data_source)
        return data


class GetMessageAliases(SSEHandlerClassBase):
    """A Class-Command for request to lw-data-provider.

    It retrieves a list of message aliases in book.

    Returns:
        dict: List[str].
    """

    def __init__(
        self,
        book_id: str,
        start_timestamp: datetime = None,
        end_timestamp: datetime = None,
        cache: bool = False,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        buffer_limit: int = DEFAULT_BUFFER_LIMIT,
    ) -> None:
        """GetMessageAliases Constructor.

        If start_timestamp and end_timestamp are not provided, it returns all aliases.

        Args:
            book_id (str): Book ID.
            start_timestamp (datetime): Start Timestamp.
            end_timestamp (datetime): End Timestamp.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )
        if all(timestamp is None for timestamp in (start_timestamp, end_timestamp)):
            self._all_results = True
        else:
            _check_datetime(start_timestamp)
            _check_datetime(end_timestamp)
            self._start_timestamp = DatetimeConverter.to_nanoseconds(start_timestamp)
            self._end_timestamp = DatetimeConverter.to_nanoseconds(end_timestamp)
            self._all_results = False
        self._book_id = book_id

    def _get_urls(self, data_source: HTTPDataSource):
        api = data_source.source_api
        if self._all_results:
            return [api.get_url_get_message_aliases(book_id=self._book_id)]
        else:
            return [
                api.get_url_get_message_aliases(
                    self._book_id, self._start_timestamp, self._end_timestamp
                )
            ]

    def _data_object(self, data_source: HTTPDataSource) -> Data[Page]:
        """Parses SSEEvents Into Data Object.

        Args:
            data_source: HTTPDataSource

        Returns:
             Data
        """
        sse_events_stream = partial(self._sse_events_stream, data_source)
        data = Data(sse_events_stream).map_stream(self._sse_handler).use_cache(self._cache)
        data.metadata["urls"] = self._get_urls(data_source)
        return data


class GetMessageGroups(SSEHandlerClassBase):
    """A Class-Command for request to lw-data-provider.

    It retrieves a list of message groups in book.

    Returns:
        dict: List[str].
    """

    def __init__(
        self,
        book_id: str,
        start_timestamp: datetime = None,
        end_timestamp: datetime = None,
        cache: bool = False,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        buffer_limit: int = DEFAULT_BUFFER_LIMIT,
    ) -> None:
        """GetMessageGroups Constructor.

        If start_timestamp and end_timestamp are not provided, it returns all aliases.

        Args:
            book_id (str): Book ID.
            start_timestamp (datetime): Start Timestamp.
            end_timestamp (datetime): End Timestamp.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )
        if all(timestamp is None for timestamp in (start_timestamp, end_timestamp)):
            self._all_results = True
        else:
            _check_datetime(start_timestamp)
            _check_datetime(end_timestamp)
            self._start_timestamp = DatetimeConverter.to_nanoseconds(start_timestamp)
            self._end_timestamp = DatetimeConverter.to_nanoseconds(end_timestamp)
            self._all_results = False
        self._book_id = book_id

    def _get_urls(self, data_source: HTTPDataSource):
        api = data_source.source_api
        if self._all_results:
            return [api.get_url_get_message_groups(book_id=self._book_id)]
        else:
            return [
                api.get_url_get_message_groups(
                    self._book_id, self._start_timestamp, self._end_timestamp
                )
            ]

    def _data_object(self, data_source: HTTPDataSource) -> Data[Page]:
        """Parses SSEEvents Into Data Object.

        Args:
            data_source: HTTPDataSource

        Returns:
             Data
        """
        sse_events_stream = partial(self._sse_events_stream, data_source)
        data = Data(sse_events_stream).map_stream(self._sse_handler).use_cache(self._cache)
        data.metadata["urls"] = self._get_urls(data_source)
        return data


class GetBooks(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It retrieves a list of books from provider.

    Returns:
        dict: List[str].
    """

    def __init__(self):
        """GetBooks constructor."""
        super().__init__()

    def handle(self, data_source: HTTPDataSource) -> List[str]:  # noqa: D102
        api: HTTPAPI = data_source.source_api
        url = api.get_url_get_books()

        # LOG         logger.info(url)

        return api.execute_request(url).json()


class GetPageByName(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It retrieves the page by page name from the book.

    Returns:
        Page: page object.

    Raises:
        PageNotFound: If page wasn't found.
    """

    def __init__(self, book_id: str, page_name: str):
        """GetPageByName constructor.

        Args:
            book_id: Book to search inside.
            page_name: Page name to search for.
        """
        super().__init__()
        self._book_id = book_id
        self._page_name = page_name

    def handle(self, data_source: HTTPDataSource) -> Page:  # noqa: D102
        pages = data_source.command(GetPages(self._book_id)).filter(
            lambda page: page.name == self._page_name
        )
        for page in pages:
            return page
        else:
            raise PageNotFound(self._page_name, self._book_id)


class GetPages(SSEHandlerClassBase):
    def __init__(
        self,
        book_id: str,
        start_timestamp: datetime = None,
        end_timestamp: datetime = None,
        result_limit: int = None,
        cache: bool = False,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        buffer_limit: int = DEFAULT_BUFFER_LIMIT,
    ) -> None:
        """GetPages Constructor.

        If start_timestamp and end_timestamp are not provided, it returns all Pages.

        Args:
            book_id (str): Book ID.
            start_timestamp (datetime): Start Timestamp.
            end_timestamp (datetime): End Timestamp.
            result_limit (Optional, int): Return Result Limit.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        if all(timestamp is None for timestamp in (start_timestamp, end_timestamp)):
            self._all_results = True
        else:
            _check_datetime(start_timestamp)
            _check_datetime(end_timestamp)
            self._start_timestamp = DatetimeConverter.to_nanoseconds(start_timestamp)
            self._end_timestamp = DatetimeConverter.to_nanoseconds(end_timestamp)
            self._all_results = False
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )
        self._book_id = book_id
        self._result_limit = result_limit

    def _get_urls(self, data_source: HTTPDataSource):
        api = data_source.source_api
        if self._all_results:
            return [api.get_url_get_pages_info_all(self._book_id)]
        else:
            return [
                api.get_url_get_pages_info(
                    self._book_id, self._start_timestamp, self._end_timestamp, self._result_limit
                )
            ]

    def to_pages(self, stream):  # noqa
        for event_data in stream:
            yield Page(event_data)

    def _data_object(self, data_source: HTTPDataSource) -> Data[Page]:
        """Parses SSEEvents Into Data Object.

        Args:
            data_source: HTTPDataSource

        Returns:
             Data
        """
        sse_events_stream = partial(self._sse_events_stream, data_source)
        data = (
            Data(sse_events_stream)
            .map_stream(self._sse_handler)
            .map_stream(self.to_pages)
            .use_cache(self._cache)
        )
        data.metadata["urls"] = self._get_urls(data_source)
        return data


class GetEventById(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It retrieves the event by id with `attachedMessageIds` list.

    Returns:
        dict: Th2 event.

    Raises:
        EventNotFound: If event by Id wasn't found.
    """

    def __init__(self, id: str, use_stub=False):
        """GetEventById constructor.

        Args:
            id: Event id.
            use_stub: If True the command returns stub instead of exception.

        """
        super().__init__()
        self._id = id
        self._stub_status = use_stub

    def handle(self, data_source: HTTPDataSource) -> dict:  # noqa: D102
        api: HTTPAPI = data_source.source_api
        url = api.get_url_find_event_by_id(self._id)

        # LOG         logger.info(url)

        response = api.execute_request(url)
        # +TODO - perhaps we have to move it to api.execute_request
        if response.status_code == 404 and self._stub_status:
            stub = data_source.event_stub_builder.build(
                {data_source.event_struct.EVENT_ID: self._id}
            )
            return stub
        elif response.status_code == 404:
            # LOG             logger.error(f"Unable to find the message. Id: {self._id}")
            raise EventNotFound(self._id, "Unable to find the event")
        else:
            return response.json()


class GetEventsById(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It retrieves the events by ids with `attachedMessageIds` list.

    Returns:
        List[dict]: Th2 events.

    Raises:
        EventNotFound: If any event by Id wasn't found.
    """

    def __init__(self, ids: List[str], use_stub=False):
        """GetEventsById constructor.

        Args:
            ids: Event id list.
            use_stub: If True the command returns stub instead of exception.

        """
        super().__init__()
        self._ids: ids = ids
        self._stub_status = use_stub

    def handle(self, data_source: HTTPDataSource) -> List[dict]:  # noqa: D102
        result = []
        for event_id in self._ids:
            event = GetEventById(event_id, use_stub=self._stub_status).handle(data_source)
            result.append(event)

        return result


class GetEventsByPage(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It searches events stream by page.

    Returns:
        Iterable[dict]: Stream of Th2 messages.
    """

    def __init__(
        self,
        page: Union[Page, str],
        book_id: str = None,
        parent_event: str = None,
        search_direction: str = "next",
        result_count_limit: int = None,
        filters: Union[LwDPEventFilter, List[LwDPEventFilter]] = None,
        cache: bool = False,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        buffer_limit=DEFAULT_BUFFER_LIMIT,
    ):
        """GetEventsByPage Constructor.

        Args:
            page: Page to search with.
            book_id: Book to search page by name. If page is string, book_id should be passed.
            parent_event: Match events to the specified parent.
            search_direction: Search direction.
            result_count_limit: Result count limit.
            filters: Filters using in search for messages.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        self._char_enc = char_enc
        self._decode_error_handler = decode_error_handler
        self._buffer_limit = buffer_limit
        self._cache = cache
        self._page = page
        self._book_id = book_id
        self._parent_event = parent_event
        self._result_count_limit = result_count_limit
        self._search_direction = search_direction
        self._filters = filters
        self._cache = cache

    def handle(self, data_source: HTTPDataSource):
        page = _get_page_object(self._book_id, self._page, data_source)
        self._start_timestamp = ProtobufTimestampConverter.to_datetime(page.start_timestamp)
        self._end_timestamp = (
            get_utc_datetime_now()
            if page.end_timestamp is None
            else ProtobufTimestampConverter.to_datetime(page.end_timestamp)
        )
        self._scopes = list(
            data_source.command(
                GetEventScopes(
                    self._book_id,
                    self._start_timestamp,
                    self._end_timestamp,
                )
            )
        )
        self._book_id = page.book
        return data_source.command(
            GetEventsByPageByScopes(
                page=self._page,
                scopes=self._scopes,
                book_id=self._book_id,
                parent_event=self._parent_event,
                search_direction=self._search_direction,
                result_count_limit=self._result_count_limit,
                filters=self._filters,
                char_enc=self._char_enc,
                decode_error_handler=self._decode_error_handler,
                cache=self._cache,
                buffer_limit=self._buffer_limit,
            )
        )


class GetEventsByBookByScopes(SSEHandlerClassBase):
    """A Class-Command for request to lw-data-provider.

    It searches events stream by options.

    Returns:
        Iterable[dict]: Stream of Th2 events.
    """

    def __init__(
        self,
        start_timestamp: datetime,
        book_id: str,
        scopes: List[str],
        end_timestamp: Optional[datetime] = None,
        parent_event: str = None,
        search_direction: str = "next",
        result_count_limit: int = None,
        filters: Union[LwDPEventFilter, List[LwDPEventFilter]] = None,
        # Non-data source args.
        # +TODO - add `max_url_length: int = 2048,`
        #   It'll be required when you implement `__split_requests` in source_api/http.py
        cache: bool = False,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        buffer_limit: int = DEFAULT_BUFFER_LIMIT,
    ):
        """GetEventsByBookByScopes constructor.

        Args:
            start_timestamp: Start timestamp of search.
            book_id: Book ID for messages.
            scopes: Scope names for events.
            end_timestamp: End timestamp of search.
            parent_event: Match events to the specified parent.
            search_direction: Search direction.
            result_count_limit: Result count limit.
            filters: Filters using in search for messages.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        _check_datetime(start_timestamp)
        if end_timestamp:
            _check_datetime(end_timestamp)
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )

        self._cache = cache
        # +TODO - we can make timestamps optional datetime or int. We have to check that it's in ms.

        self._start_timestamp = DatetimeConverter.to_nanoseconds(start_timestamp)
        self._end_timestamp = (
            DatetimeConverter.to_nanoseconds(end_timestamp) if end_timestamp else None
        )
        self._parent_event = parent_event
        self._search_direction = search_direction
        self._result_count_limit = result_count_limit
        self._filters = filters
        self._book_id = book_id
        self._scopes = scopes
        if isinstance(filters, LwDPEventFilter):
            self._filters = filters.url()
        elif isinstance(filters, (tuple, list)):
            self._filters = "".join([filter_.url() for filter_ in filters])

        _check_list_or_tuple(self._scopes, var_name="scopes")

    def _get_urls(self, data_source: HTTPDataSource):
        api = data_source.source_api
        return [
            api.get_url_search_sse_events(
                start_timestamp=self._start_timestamp,
                end_timestamp=self._end_timestamp,
                parent_event=self._parent_event,
                search_direction=self._search_direction,
                result_count_limit=self._result_count_limit,
                filters=self._filters,
                book_id=self._book_id,
                scope=scope,
            )
            for scope in self._scopes
        ]


class GetEventsByPageByScopes(SSEHandlerClassBase):
    """A Class-Command for request to lw-data-provider.

    It searches events stream by options.

    Returns:
        Iterable[dict]: Stream of Th2 events.
    """

    def __init__(
        self,
        page: Union[Page, str],
        scopes: List[str],
        book_id: str = None,
        parent_event: str = None,
        search_direction: str = "next",
        result_count_limit: int = None,
        filters: Union[LwDPEventFilter, List[LwDPEventFilter]] = None,
        # Non-data source args.
        # +TODO - add `max_url_length: int = 2048,`
        #   It'll be required when you implement `__split_requests` in source_api/http.py
        cache: bool = False,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        buffer_limit=DEFAULT_BUFFER_LIMIT,
    ):
        """GetEventsByPageByScopes constructor.

        Args:
            page: Page to search with.
            scopes: Scope names for events.
            book_id: Book to search page by name. If page is string, book_id should be passed.
            parent_event: Match events to the specified parent.
            search_direction: Search direction.
            result_count_limit: Result count limit.
            filters: Filters using in search for messages.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )

        self._cache = cache
        # +TODO - we can make timestamps optional datetime or int. We have to check that it's in ms.

        self._page = page
        self._book_id = book_id
        self._parent_event = parent_event
        self._search_direction = search_direction
        self._result_count_limit = result_count_limit
        self._filters = filters
        self._scopes = scopes
        if isinstance(filters, LwDPEventFilter):
            self._filters = filters.url()
        elif isinstance(filters, (tuple, list)):
            self._filters = "".join([filter_.url() for filter_ in filters])

        _check_list_or_tuple(self._scopes, var_name="scopes")

    def _get_urls(self, data_source: HTTPDataSource):
        page = _get_page_object(self._book_id, self._page, data_source)
        self._start_timestamp = ProtobufTimestampConverter.to_nanoseconds(page.start_timestamp)
        self._end_timestamp = (
            get_utc_datetime_now()
            if page.end_timestamp is None
            else ProtobufTimestampConverter.to_nanoseconds(page.end_timestamp)
        )
        self._book_id = page.book
        api = data_source.source_api
        return [
            api.get_url_search_sse_events(
                start_timestamp=self._start_timestamp,
                end_timestamp=self._end_timestamp,
                parent_event=self._parent_event,
                search_direction=self._search_direction,
                result_count_limit=self._result_count_limit,
                filters=self._filters,
                book_id=self._book_id,
                scope=scope,
            )
            for scope in self._scopes
        ]


class GetMessageById(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It retrieves the message by id.

    Returns:
        dict: Th2 message.

    Raises:
        MessageNotFound: If message by id wasn't found.
    """

    def __init__(self, id: str, use_stub=False, response_formats: Union[List[str], str] = None):
        """GetMessageById constructor.

        Args:
            id: Message id.
            use_stub: If True the command returns stub instead of exception.
            response_formats: Allowed values: ["BASE_64","JSON_PARSED"] and ["BASE_64"]

        """
        super().__init__()
        self._id = id
        self._stub_status = use_stub
        self._response_formats = response_formats

    def handle(self, data_source: HTTPDataSource) -> dict:  # noqa: D102
        api: HTTPAPI = data_source.source_api
        if self._response_formats in [["JSON_PARSED", "BASE_64"], ["BASE_64", "JSON_PARSED"], None]:
            only_raw = False
        elif self._response_formats == ["BASE_64"]:
            only_raw = True
        else:
            raise Exception(
                "response_formats should be either ['BASE_64'] or ['JSON_PARSED','BASE_64']"
            )

        url = api.get_url_find_message_by_id(self._id, only_raw)
        # LOG         logger.info(url)
        response = api.execute_request(url)
        if response.status_code in (404, 408) and self._stub_status:
            stub = data_source.message_stub_builder.build(
                {data_source.message_struct.MESSAGE_ID: self._id}
            )
            return stub
        elif response.status_code in (404, 408):
            # LOG             logger.error(f"Unable to find the message. Id: {self._id}")
            raise MessageNotFound(self._id, "Unable to find the message")
        else:
            return response.json()


class GetMessagesById(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It retrieves the messages by ids.

    Returns:
        List[dict]: Th2 messages.

    Raises:
        MessageNotFound: If any message by id wasn't found.
    """

    def __init__(
        self, ids: List[str], use_stub=False, response_formats: Union[List[str], str] = None
    ):
        """GetMessagesById constructor.

        Args:
            ids: Message id list.
            use_stub: If True the command returns stub instead of exception.
            response_formats: Allowed values: ["BASE_64","JSON_PARSED"] and ["BASE_64"]

        """
        super().__init__()
        self._ids: ids = ids
        self._stub_status = use_stub
        self._response_formats = response_formats

    def handle(self, data_source: HTTPDataSource) -> List[dict]:  # noqa: D102
        result = []
        for message_id in self._ids:
            message = GetMessageById(
                message_id,
                use_stub=self._stub_status,
                response_formats=self._response_formats,
            ).handle(data_source)
            result.append(message)

        return result


class GetMessagesByBookByStreams(SSEHandlerClassBase):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream by options.

    Returns:
        Iterable[dict]: Stream of Th2 messages.
    """

    def __init__(
        self,
        start_timestamp: datetime,
        book_id: str,
        streams: Union[List[Union[str, Streams, Stream]], Streams],
        message_ids: List[str] = None,
        search_direction: str = "next",
        result_count_limit: int = None,
        end_timestamp: datetime = None,
        response_formats: Union[List[str], str] = None,
        keep_open: bool = False,
        # Non-data source args.
        # +TODO - we often repeat these args. Perhaps it's better to move them to some class.
        max_url_length: int = 2048,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        cache: bool = False,
        buffer_limit: int = DEFAULT_BUFFER_LIMIT,
    ):
        """GetMessagesByBookByStreams constructor.

        Args:
            start_timestamp: Start timestamp of search.
            book_id: Book ID for messages
            streams: List of aliases to request. If direction is not specified all directions will be requested for stream.
            message_ids: List of message IDs to restore search. If given, it has
                the highest priority and ignores streams (uses streams from ids), startTimestamp and resumeFromId.
            search_direction: Search direction.
            result_count_limit: Result count limit.
            end_timestamp: End timestamp of search.
            response_formats: The format of the response
            keep_open: If the search has reached the current moment.
                It needs to wait further for the appearance of new data.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        response_formats = _get_response_format(response_formats)
        _check_response_formats(response_formats)
        _check_datetime(start_timestamp)
        if end_timestamp:
            _check_datetime(end_timestamp)
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )

        self._streams = streams
        self._search_direction = search_direction
        self._result_count_limit = result_count_limit
        self._response_formats = response_formats
        self._keep_open = keep_open
        self._message_ids = message_ids
        self._book_id = book_id
        self._max_url_length = max_url_length
        self._char_enc = char_enc
        self._decode_error_handler = decode_error_handler
        self._cache = cache

        # + TODO - we can make timestamps optional datetime or int
        self._start_timestamp = DatetimeConverter.to_nanoseconds(start_timestamp)
        self._end_timestamp = (
            DatetimeConverter.to_nanoseconds(end_timestamp) if end_timestamp else None
        )

        if self._start_timestamp is None and not self._message_ids:
            raise TypeError("One of start_timestamp or message_id arguments must not be empty")

        if isinstance(streams, Streams):
            self._streams = streams.as_list()
        elif isinstance(streams, (tuple, list, Streams)):
            self._streams = []
            for stream in streams:
                if isinstance(stream, Stream):
                    self._streams.append(stream.url()[8:])
                elif isinstance(stream, Streams):
                    self._streams += stream.as_list()
                else:
                    self._streams.append(stream)
        else:
            raise TypeError(
                f"streams argument has to be list, tuple or Streams type. "
                f"Got {type(self._streams)}"
            )

    def _get_urls(self, data_source: HTTPDataSource):
        api = data_source.source_api
        return api.get_url_search_sse_messages(
            start_timestamp=self._start_timestamp,
            message_ids=self._message_ids,
            stream=self._streams,
            search_direction=self._search_direction,
            result_count_limit=self._result_count_limit,
            end_timestamp=self._end_timestamp,
            response_formats=self._response_formats,
            keep_open=self._keep_open,
            book_id=self._book_id,
            max_url_length=self._max_url_length,
        )


class DownloadMessagesByPageGzip(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream by page and downloads them.
    Beware that if you request this command with long list of groups,
      you will get multiple files: ‘{filename}.1.gz’, ‘{filename}.2.gz’,
      etc., since the request might exceed url limit.

    Returns:
        Nothing.
    """

    def __init__(
        self,
        filename: str,
        page: Union[Page, str],
        book_id: str = None,
        sort: bool = None,
        response_formats: Union[List[str], str] = None,
        keep_open: bool = None,
        streams: List[str] = None,
        # Non-data source args.
        max_url_length: int = 2048,
    ):
        """DownloadMessagesByPageGzip Constructor.

        Args:
            filename: Filename of downloaded files.
            page: Page to search with.
            book_id: Book to search page by name. If page is string, book_id should be passed.
            sort: Enables message sorting within a group. It is not sorted between groups.
            response_formats: The format of the response
            keep_open: If true, keeps pulling for new message until don't have one outside the requested range.
            streams: List of streams to search messages from.
            max_url_length: API request url max length.
        """
        response_formats = _get_response_format(response_formats)
        _check_response_formats(response_formats)
        # TODO - check if filename is valid
        # check_if_filename_valid
        self._filename = filename
        self._page = page
        self._book_id = book_id
        self._sort = sort
        self._response_formats = response_formats
        self._keep_open = keep_open
        self._streams = streams
        self._max_url_length = max_url_length

        if streams is not None:
            _check_list_or_tuple(self._streams, var_name="streams")

    def handle(self, data_source: HTTPDataSource):
        page = _get_page_object(self._book_id, self._page, data_source)
        start_timestamp = ProtobufTimestampConverter.to_datetime(page.start_timestamp)
        end_timestamp = (
            get_utc_datetime_now()
            if page.end_timestamp is None
            else ProtobufTimestampConverter.to_datetime(page.end_timestamp)
        )
        groups = list(
            data_source.command(
                GetMessageGroups(
                    self._book_id,
                    start_timestamp,
                    end_timestamp,
                )
            )
        )
        self._book_id = page.book
        return DownloadMessagesByPageByGroupsGzip(
            filename=self._filename,
            page=page,
            groups=groups,
            streams=self._streams,
            book_id=self._book_id,
            sort=self._sort,
            response_formats=self._response_formats,
            keep_open=self._keep_open,
            max_url_length=self._max_url_length,
        )


def _download_messages(api, urls, headers, filename):
    """Downloads messages from LwDP and store to jsons.gz files.

    Args:
        api:
        urls:
        headers:
        filename:

    Returns:
        None
    """

    def do_req_and_store(fn, headers, url):
        with open(fn, "wb") as file:
            try:
                response = api.execute_request(url, headers=headers, stream=True)
                response.raise_for_status()

                copyfileobj(response.raw, file)
            except requests.exceptions.HTTPError as e:
                print(e)
                print()

    if filename.endswith(".gz"):
        filename = filename[:-3]

    if len(urls) == 1:
        do_req_and_store(f"{filename}.gz", headers, urls[0])

    else:
        for num, url in enumerate(urls):
            do_req_and_store(f"{filename}.{num + 1}.gz", headers, url)


class DownloadMessagesByPageByGroupsGzip(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream by page & groups and downloads them.
    Beware that if you request this command with long list of groups,
      you will get multiple files: ‘{filename}.1.gz’, ‘{filename}.2.gz’,
      etc., since the request might exceed url limit.


    Returns:
        Nothing.
    """

    def __init__(
        self,
        filename: str,
        page: Union[Page, str],
        groups: List[str],
        book_id: str = None,
        sort: bool = None,
        response_formats: Union[List[str], str] = None,
        keep_open: bool = None,
        streams: List[str] = None,
        # Non-data source args.
        max_url_length: int = 2048,
    ):
        """DownloadMessagesByPageByGroupsGzip Constructor.

        Args:
            filename: Filename of downloaded files.
            page: Page to search with.
            book_id: Book to search page by name. If page is string, book_id should be passed.
            groups: List of groups to search messages from.
            sort: Enables message sorting within a group. It is not sorted between groups.
            response_formats: The format of the response
            keep_open: If true, keeps pulling for new message until don't have one outside the requested range.
            streams: List of streams to search messages from.
            max_url_length: API request url max length.
        """
        response_formats = _get_response_format(response_formats)
        _check_response_formats(response_formats)
        self._filename = filename
        self._page = page
        self._book_id = book_id
        self._groups = groups
        self._streams = streams
        self._sort = sort
        self._response_formats = response_formats
        self._keep_open = keep_open
        self._max_url_length = max_url_length

        _check_list_or_tuple(self._groups, var_name="groups")
        if streams is not None:
            _check_list_or_tuple(self._streams, var_name="streams")

    def handle(self, data_source: HTTPDataSource):
        page = _get_page_object(self._book_id, self._page, data_source)
        self._start_timestamp = ProtobufTimestampConverter.to_nanoseconds(page.start_timestamp)
        self._end_timestamp = (
            get_utc_datetime_now()
            if page.end_timestamp is None
            else ProtobufTimestampConverter.to_nanoseconds(page.end_timestamp)
        )
        self._book_id = page.book
        api = data_source.source_api
        urls = api.get_download_messages(
            start_timestamp=self._start_timestamp,
            end_timestamp=self._end_timestamp,
            book_id=self._book_id,
            groups=self._groups,
            stream=self._streams,
            sort=self._sort,
            response_formats=self._response_formats,
            keep_open=self._keep_open,
            max_url_length=self._max_url_length,
        )

        headers = {"Accept": "application/stream+json", "Accept-Encoding": "gzip, deflate"}

        _download_messages(api, urls, headers, self._filename)


class DownloadMessagesByBookByGroupsGzip(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream by page & groups and downloads them.
    Beware that if you request this command with long list of groups,
      you will get multiple files: ‘{filename}.1.gz’, ‘{filename}.2.gz’,
      etc., since the request might exceed url limit.


    Returns:
        Nothing.
    """

    def __init__(
        self,
        filename: str,
        start_timestamp: datetime,
        end_timestamp: datetime,
        book_id: str,
        groups: List[str],
        sort: bool = None,
        response_formats: Union[List[str], str] = None,
        keep_open: bool = None,
        streams: List[str] = None,
        # Non-data source args.
        max_url_length: int = 2048,
    ):
        """DownloadMessagesByBookByGroupsGzip Constructor.

        Args:
            filename: Filename of downloaded files.
            start_timestamp: Sets the search starting point.
            end_timestamp: Sets the timestamp to which the search will be performed, starting with 'start_timestamp'.

            book_id: book ID for requested groups.
            groups: List of groups to search messages from.
            sort: Enables message sorting within a group. It is not sorted between groups.
                  (You cannot specify a direction in groups unlike streams.
                  It's possible to add it to the CradleAPI by request to dev team.)
            response_formats: The format of the response
            keep_open: If true, keeps pulling for new message until don't have one outside the requested range.
            streams: List of streams to search messages from.
            max_url_length: API request url max length.
        """
        response_formats = _get_response_format(response_formats)
        _check_response_formats(response_formats)
        _check_datetime(start_timestamp)
        _check_datetime(end_timestamp)
        self._filename = filename
        self._start_timestamp = DatetimeConverter.to_nanoseconds(start_timestamp)
        self._end_timestamp = DatetimeConverter.to_nanoseconds(end_timestamp)
        self._groups = groups
        self._streams = streams
        self._sort = sort
        self._response_formats = response_formats
        self._keep_open = keep_open
        self._book_id = book_id
        self._max_url_length = max_url_length

        _check_list_or_tuple(self._groups, var_name="groups")
        if streams is not None:
            _check_list_or_tuple(self._streams, var_name="streams")

    def handle(self, data_source: HTTPDataSource):
        api = data_source.source_api
        urls = api.get_download_messages(
            start_timestamp=self._start_timestamp,
            end_timestamp=self._end_timestamp,
            book_id=self._book_id,
            groups=self._groups,
            stream=self._streams,
            sort=self._sort,
            response_formats=self._response_formats,
            keep_open=self._keep_open,
            max_url_length=self._max_url_length,
        )
        headers = {"Accept": "application/stream+json", "Accept-Encoding": "gzip, deflate"}

        _download_messages(api, urls, headers, self._filename)


class GetMessagesByBookByGroups(SSEHandlerClassBase):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream by groups.

    Returns:
        Iterable[dict]: Stream of Th2 messages.
    """

    def __init__(
        self,
        start_timestamp: datetime,
        end_timestamp: datetime,
        book_id: str,
        groups: List[str],
        sort: bool = None,
        response_formats: Union[List[str], str] = None,
        keep_open: bool = None,
        streams: List[str] = None,
        # Non-data source args.
        max_url_length: int = 2048,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        cache: bool = False,
        buffer_limit=DEFAULT_BUFFER_LIMIT,
    ):
        """GetMessagesByBookByGroups Constructor.

        Args:
            start_timestamp: Sets the search starting point.
            end_timestamp: Sets the timestamp to which the search will be performed, starting with
                'start_timestamp'.
            book_id: book ID for requested groups.
            groups: List of groups to search messages from.
            sort: Enables message sorting within a group. It is not sorted between groups.
                  (You cannot specify a direction in groups unlike streams.
                  It's possible to add it to the CradleAPI by request to dev team.)
            response_formats: The format of the response
            keep_open: If true, keeps pulling for new message until don't have one outside the
                requested range.
            streams: List of streams to search messages from.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        response_formats = _get_response_format(response_formats)
        _check_response_formats(response_formats)
        _check_datetime(start_timestamp)
        _check_datetime(end_timestamp)
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )

        self._char_enc = char_enc
        self._decode_error_handler = decode_error_handler
        self._cache = cache
        self._start_timestamp = DatetimeConverter.to_nanoseconds(start_timestamp)
        self._end_timestamp = DatetimeConverter.to_nanoseconds(end_timestamp)
        self._groups = groups
        self._streams = streams
        self._sort = sort
        self._response_formats = response_formats
        self._keep_open = keep_open
        self._book_id = book_id
        self._max_url_length = max_url_length

        _check_list_or_tuple(self._groups, var_name="groups")
        if streams is not None:
            _check_list_or_tuple(self._streams, var_name="streams")

    def _get_urls(self, data_source: HTTPDataSource):
        api = data_source.source_api
        return api.get_url_search_messages_by_groups(
            start_timestamp=self._start_timestamp,
            end_timestamp=self._end_timestamp,
            groups=self._groups,
            streams=self._streams,
            response_formats=self._response_formats,
            keep_open=self._keep_open,
            sort=self._sort,
            book_id=self._book_id,
            max_url_length=self._max_url_length,
        )


class GetMessagesByPage(IHTTPCommand):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream by page.

    Returns:
        Iterable[dict]: Stream of Th2 messages.
    """

    def __init__(
        self,
        page: Union[Page, str],
        book_id: str = None,
        sort: bool = None,
        response_formats: Union[List[str], str] = None,
        keep_open: bool = None,
        max_url_length: int = 2048,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        cache: bool = False,
        buffer_limit: int = DEFAULT_BUFFER_LIMIT,
    ):
        """GetMessagesByPage Constructor.

        Args:
            page: Page to search with.
            book_id: Book to search page by name.
            sort: Enables message sorting within a group. It is not sorted between groups.
            response_formats: The format of the response
            keep_open: If true, keeps pulling for new message until don't have one outside the requested range.
            max_url_length: API request url max length.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        response_formats = _get_response_format(response_formats)
        _check_response_formats(response_formats)
        self._char_enc = char_enc
        self._decode_error_handler = decode_error_handler
        self._buffer_limit = buffer_limit
        self._cache = cache
        self._page = page
        self._book_id = book_id
        self._sort = sort
        self._response_formats = response_formats
        self._keep_open = keep_open
        self._max_url_length = max_url_length
        self._cache = cache

    def handle(self, data_source: HTTPDataSource):
        page = _get_page_object(self._book_id, self._page, data_source)
        start_timestamp = ProtobufTimestampConverter.to_datetime(page.start_timestamp)
        end_timestamp = (
            get_utc_datetime_now()
            if page.end_timestamp is None
            else ProtobufTimestampConverter.to_datetime(page.end_timestamp)
        )
        groups = list(
            data_source.command(
                GetMessageGroups(
                    self._book_id,
                    start_timestamp,
                    end_timestamp,
                    char_enc=self._char_enc,
                    decode_error_handler=self._decode_error_handler,
                )
            )
        )
        self._book_id = page.book
        return data_source.command(
            GetMessagesByPageByGroups(
                page=self._page,
                groups=groups,
                book_id=self._book_id,
                sort=self._sort,
                response_formats=self._response_formats,
                keep_open=self._keep_open,
                max_url_length=self._max_url_length,
                char_enc=self._char_enc,
                decode_error_handler=self._decode_error_handler,
                cache=self._cache,
                buffer_limit=self._buffer_limit,
            )
        )


class GetMessagesByPageByStreams(SSEHandlerClassBase):
    def __init__(
        self,
        page: Union[Page, str],
        stream: List[str],
        book_id: str = None,
        message_ids: List[None] = None,
        search_direction: Optional[str] = "next",
        result_count_limit: int = None,
        response_formats: Union[List[str], str] = None,
        keep_open: bool = None,
        max_url_length: int = 2048,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        cache: bool = False,
        buffer_limit: int = DEFAULT_BUFFER_LIMIT,
    ):
        """GetMessagesByPageByStreams Constructor.

        Args:
            page: Page to search with.
            stream: In which streams to search.
            book_id: Book to search page by name. If page is string, book_id should be passed.
            message_ids: Search for message ids.
            result_count_limit: Max results to get.
            search_direction: Search direction.
            response_formats: The format of the response
            keep_open: If true, keeps pulling for new message until don't have one outside the requested range.
            max_url_length: API request url max length.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )
        response_formats = _get_response_format(response_formats)
        _check_response_formats(response_formats)
        self._char_enc = char_enc
        self._decode_error_handler = decode_error_handler
        self._cache = cache
        self._page = page
        self._book_id = book_id
        self._result_count_limit = result_count_limit
        self._search_direction = search_direction
        self._response_formats = response_formats
        self._message_ids = message_ids
        self._keep_open = keep_open
        self._max_url_length = max_url_length
        self._stream = stream

    def _get_urls(self, data_source: HTTPDataSource):
        page = _get_page_object(self._book_id, self._page, data_source)
        self._start_timestamp = ProtobufTimestampConverter.to_nanoseconds(page.start_timestamp)
        self._end_timestamp = (
            get_utc_datetime_now()
            if page.end_timestamp is None
            else ProtobufTimestampConverter.to_nanoseconds(page.end_timestamp)
        )
        self._book_id = page.book
        api = data_source.source_api
        return api.get_url_search_sse_messages(
            start_timestamp=self._start_timestamp,
            book_id=self._book_id,
            message_ids=self._message_ids,
            stream=self._stream,
            search_direction=self._search_direction,
            result_count_limit=self._result_count_limit,
            end_timestamp=self._end_timestamp,
            response_formats=self._response_formats,
            keep_open=self._keep_open,
            max_url_length=self._max_url_length,
        )


class GetMessagesByPageByGroups(SSEHandlerClassBase):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream by page & groups.

    Returns:
        Iterable[dict]: Stream of Th2 messages.
    """

    def __init__(
        self,
        page: Union[Page, str],
        groups: List[str],
        book_id: str = None,
        sort: bool = None,
        response_formats: Union[List[str], str] = None,
        keep_open: bool = None,
        streams: List[str] = None,
        # Non-data source args.
        max_url_length: int = 2048,
        char_enc: str = "utf-8",
        decode_error_handler: str = UNICODE_REPLACE_HANDLER,
        cache: bool = False,
        buffer_limit=DEFAULT_BUFFER_LIMIT,
    ):
        """GetMessagesByPageByGroups Constructor.

        Args:
            page: Page to search with.
            book_id: Book to search page by name. If page is string, book_id should be passed.
            groups: List of groups to search messages from.
            sort: Enables message sorting within a group. It is not sorted between groups.
            response_formats: The format of the response
            keep_open: If true, keeps pulling for new message until don't have one outside the
                requested range.
            streams: List of streams to search messages from.
            char_enc: Encoding for the byte stream.
            decode_error_handler: Registered decode error handler.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            max_url_length: API request url max length.
            buffer_limit: SSEAdapter BufferedJSONProcessor buffer limit.
        """
        super().__init__(
            cache=cache,
            buffer_limit=buffer_limit,
            char_enc=char_enc,
            decode_error_handler=decode_error_handler,
        )
        response_formats = _get_response_format(response_formats)
        _check_response_formats(response_formats)

        self._char_enc = char_enc
        self._decode_error_handler = decode_error_handler
        self._cache = cache
        self._page = page
        self._book_id = book_id
        self._groups = groups
        self._streams = streams
        self._sort = sort
        self._response_formats = response_formats
        self._keep_open = keep_open
        self._max_url_length = max_url_length

        _check_list_or_tuple(self._groups, var_name="groups")
        if streams is not None:
            _check_list_or_tuple(self._streams, var_name="streams")

    def _get_urls(self, data_source: HTTPDataSource):
        page = _get_page_object(self._book_id, self._page, data_source)
        self._start_timestamp = ProtobufTimestampConverter.to_nanoseconds(page.start_timestamp)
        self._end_timestamp = (
            get_utc_datetime_now()
            if page.end_timestamp is None
            else ProtobufTimestampConverter.to_nanoseconds(page.end_timestamp)
        )
        self._book_id = page.book
        api = data_source.source_api
        return api.get_url_search_messages_by_groups(
            start_timestamp=self._start_timestamp,
            end_timestamp=self._end_timestamp,
            groups=self._groups,
            streams=self._streams,
            response_formats=self._response_formats,
            keep_open=self._keep_open,
            sort=self._sort,
            book_id=self._book_id,
            max_url_length=self._max_url_length,
        )


def _get_page_object(book_id, page: Union[Page, str], data_source) -> Page:  # noqa
    if isinstance(page, str):
        if book_id is None:
            raise Exception("If page name is passed then book_id should be passed too!")
        else:
            return data_source.command(GetPageByName(book_id, page))
    elif isinstance(page, Page):
        return page
    else:
        raise Exception("Wrong type. page should be Page object or string (page name)!")

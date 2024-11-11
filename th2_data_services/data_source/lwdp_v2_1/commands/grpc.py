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

from datetime import datetime, timezone
from functools import partial
from typing import List, Iterable, Generator, Union

from grpc._channel import _InactiveRpcError
from th2_grpc_lw_data_provider.lw_data_provider_pb2 import (
    EventResponse,
    MessageGroupResponse,
    MessageStreamPointer,
)

from th2_data_services.data import Data
from th2_data_services.interfaces.command import IAdaptableCommand
from th2_data_services.exceptions import EventNotFound, MessageNotFound
from th2_data_services.data_source.lwdp_v2_1.adapters.basic_adapters import GRPCObjectToDictAdapter
from th2_data_services.data_source.lwdp_v2_1.adapters.event_adapters import DeleteEventWrappersAdapter
from th2_data_services.data_source.lwdp_v2_1.adapters.message_adapters import DeleteMessageWrappersAdapter
from th2_data_services.data_source.lwdp_v2_1.filters.filter import LwDPEventFilter
from th2_data_services.data_source.lwdp_v2_1.interfaces.command import IGRPCCommand

from th2_data_services.data_source.lwdp_v2_1.data_source.grpc import GRPCDataSource
from th2_data_services.data_source.lwdp_v2_1.source_api import GRPCAPI

import logging

from th2_data_services.data_source.lwdp_v2_1.streams import Streams

logger = logging.getLogger(__name__)


class GetEventByIdGRPCObject(IGRPCCommand, IAdaptableCommand):
    """A Class-Command for request to lw-data-provider.

    It retrieves the event by id as GRPC object.

    Returns:
        EventResponse: Th2 event.
    """

    def __init__(self, id: str):
        """GetEventByIdGRPCObject constructor.

        Args:
            id: Event id.

        """
        super().__init__()
        self._id = id

    def handle(self, data_source: GRPCDataSource) -> EventResponse:  # noqa: D102
        api: GRPCAPI = data_source.source_api
        event = api.get_event(self._id)

        event = self._handle_adapters(event)
        return event


class GetEventById(IGRPCCommand, IAdaptableCommand):
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
        self._grpc_decoder = GRPCObjectToDictAdapter()
        self._wrapper_deleter = DeleteEventWrappersAdapter()
        self._stub_status = use_stub

    def handle(self, data_source: GRPCDataSource) -> dict:  # noqa: D102
        try:
            event = GetEventByIdGRPCObject(self._id).handle(data_source)
            event = self._grpc_decoder.handle(event)
            event = self._wrapper_deleter.handle(event)
        except _InactiveRpcError:
            if self._stub_status:
                event = data_source.event_stub_builder.build(
                    {data_source.event_struct.EVENT_ID: self._id}
                )
            else:
                logger.error(f"Unable to find the event. Id: {self._id}")
                raise EventNotFound(self._id)

        event = self._handle_adapters(event)
        return event


class GetEventsById(IGRPCCommand, IAdaptableCommand):
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
            ids: Events ids.
            use_stub: If True the command returns stub instead of exception.

        """
        super().__init__()
        self.ids = ids
        self._stub_status = use_stub

    def handle(self, data_source: GRPCDataSource) -> List[dict]:  # noqa: D102
        response = []
        for event_id in self.ids:
            event = GetEventById(event_id, use_stub=self._stub_status).handle(
                data_source=data_source
            )
            event = self._handle_adapters(event)
            response.append(event)

        return response


class GetEventsGRPCObjects(IGRPCCommand, IAdaptableCommand):
    """A Class-Command for request to lw-data-provider.

    It searches events stream as GRPC object by options.

    Returns:
        Iterable[EventResponse]: Stream of Th2 events.
    """

    def __init__(
        self,
        start_timestamp: int,
        end_timestamp: int,
        parent_event: str = None,
        search_direction: str = "NEXT",
        result_count_limit: int = None,
        filters: List[LwDPEventFilter] = None,
        book_id: str = None,
        scope: str = None,
    ):
        """GetEventsGRPCObjects constructor.

        Args:
            start_timestamp: Start timestamp of search.
            end_timestamp: End timestamp of search.
            parent_event: Match events to the specified parent.
            search_direction: Sets the lookup direction. Can be 'NEXT' or 'PREVIOUS'.
            result_count_limit: Sets the maximum amount of messages to return.
            filters: Filters using in search for messages.
            book_id: book ID for messages
            scope: scope for events
        """
        super().__init__()
        self._start_timestamp = start_timestamp
        self._end_timestamp = end_timestamp
        self._parent_event = parent_event
        self._search_direction = search_direction
        self._result_count_limit = result_count_limit
        self._filters = filters
        self._book_id = book_id
        self._scope = scope

    def handle(self, data_source: GRPCDataSource) -> Iterable[EventResponse]:  # noqa: D102
        api: GRPCAPI = data_source.source_api

        start_timestamp = int(
            self._start_timestamp.replace(tzinfo=timezone.utc).timestamp() * 10**9
        )
        end_timestamp = int(self._end_timestamp.replace(tzinfo=timezone.utc).timestamp() * 10**9)

        stream_response = api.search_events(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            parent_event=self._parent_event,
            search_direction=self._search_direction,
            result_count_limit=self._result_count_limit,
            filter=self._filters,
            book_id=self._book_id,
            scope=self._scope,
        )
        for response in stream_response:
            if response.WhichOneof("data") == "event":
                response = self._handle_adapters(response)
                yield response.event


class GetEvents(IGRPCCommand, IAdaptableCommand):
    """A Class-Command for request to lw-data-provider.

    It searches events stream by options.

    Returns:
        Iterable[dict]: Stream of Th2 events.
    """

    def __init__(
        self,
        start_timestamp: int,
        end_timestamp: int,
        parent_event: str = None,
        search_direction: str = "NEXT",
        result_count_limit: int = None,
        filters: List[LwDPEventFilter] = None,
        book_id: str = None,
        scope: str = None,
        cache: bool = False,
    ):
        """GetEvents constructor.

        Args:
            start_timestamp: Start timestamp of search.
            end_timestamp: End timestamp of search.
            parent_event: Match events to the specified parent.
            cache: If True, all requested data from lw-data-provider will be saved to cache.
            search_direction: Sets the lookup direction. Can be 'NEXT' or 'PREVIOUS'.
            result_count_limit: Sets the maximum amount of messages to return.
            filters: Filters using in search for messages.
            book_id: book ID for messages
            scope: scope for events
        """
        super().__init__()
        self._start_timestamp = start_timestamp
        self._end_timestamp = end_timestamp
        self._parent_event = parent_event
        self._search_direction = search_direction
        self._result_count_limit = result_count_limit
        self._filters = filters
        self._book_id = book_id
        self._scope = scope
        self._cache = cache

        self._grpc_decoder = GRPCObjectToDictAdapter()
        self._wrapper_deleter = DeleteEventWrappersAdapter()

    def handle(self, data_source: GRPCDataSource) -> Data:  # noqa: D102
        source = partial(self.__handle_stream, data_source)
        return Data(source, cache=self._cache)

    def __handle_stream(self, data_source: GRPCDataSource) -> Generator[dict, None, None]:
        stream = GetEventsGRPCObjects(
            start_timestamp=self._start_timestamp,
            end_timestamp=self._end_timestamp,
            parent_event=self._parent_event,
            search_direction=self._search_direction,
            result_count_limit=self._result_count_limit,
            filter=self._filters,
            book_id=self._book_id,
            scope=self._scope,
        ).handle(data_source)
        for event in stream:
            event = self._grpc_decoder.handle(event)
            event = self._wrapper_deleter.handle(event)
            event = self._handle_adapters(event)
            yield event


class GetMessageByIdGRPCObject(IGRPCCommand, IAdaptableCommand):  # noqa: D102
    """A Class-Command for request to lw-data-provider.

    It retrieves the message by id as GRPC Object.

    Returns:
        MessageGroupResponse: Th2 message.
    """

    def __init__(self, id: str):
        """GetMessageByIdGRPCObject constructor.

        Args:
            id: Message id.

        """
        super().__init__()
        self._id = id

    def handle(self, data_source: GRPCDataSource) -> MessageGroupResponse:
        api: GRPCAPI = data_source.source_api
        response = api.get_message(self._id)
        response = self._handle_adapters(response)
        return response


class GetMessageById(IGRPCCommand, IAdaptableCommand):  # noqa: D102
    """A Class-Command for request to lw-data-provider.

    It retrieves the message by id.

    Please note,  doesn't return `attachedEventIds`. It will be == [].
    It's expected that Provider7 will be support it.

    Returns:
        dict: Th2 message.

    Raises:
        MessageNotFound: If message by id wasn't found.
    """

    def __init__(self, id: str, use_stub=False):
        """GetMessageById constructor.

        Args:
            id: Message id.
            use_stub: If True the command returns stub instead of exception.

        """
        super().__init__()
        self._id = id
        self._decoder = GRPCObjectToDictAdapter()
        self._wrapper_deleter = DeleteMessageWrappersAdapter()
        self._stub_status = use_stub

    def handle(self, data_source: GRPCDataSource) -> dict:  # noqa: D102
        try:
            message = GetMessageByIdGRPCObject(self._id).handle(data_source)
            message = self._decoder.handle(message)
            message = self._wrapper_deleter.handle(message)
        except _InactiveRpcError:
            if self._stub_status:
                message = data_source.message_stub_builder.build(
                    {data_source.message_struct.MESSAGE_ID: self._id}
                )
            else:
                logger.error(f"Unable to find the message. Id: {self._id}")
                raise MessageNotFound(self._id)
        message = self._handle_adapters(message)
        return message


class GetMessagesById(IGRPCCommand, IAdaptableCommand):
    """A Class-Command for request to lw-data-provider.

    It retrieves the messages by id.

    Please note,  doesn't return `attachedEventIds`. It will be == [].
    It's expected that Provider7 will be support it.

    Returns:
        List[dict]: Th2 messages.

    Raises:
        MessageNotFound: If any message by id wasn't found.
    """

    def __init__(self, ids: List[str], use_stub=False):
        """GetMessagesById constructor.

        Args:
            ids: Messages id.
            use_stub: If True the command returns stub instead of exception.

        """
        super().__init__()
        self._ids = ids
        self._stub_status = use_stub

    def handle(self, data_source: GRPCDataSource) -> List[dict]:  # noqa: D102
        response = []
        for id_ in self._ids:
            message = GetMessageById(id_, use_stub=self._stub_status).handle(data_source)
            message = self._handle_adapters(message)
            response.append(message)

        return response


class GetMessagesGRPCObject(IGRPCCommand, IAdaptableCommand):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream as GRPC object by options.

    Returns:
        Iterable[MessageGroupResponse]: Stream of Th2 messages.
    """

    def __init__(
        self,
        start_timestamp: datetime,
        stream: List[Union[str, Streams]],
        end_timestamp: datetime = None,
        search_direction: str = "NEXT",
        result_count_limit: int = None,
        stream_pointers: List[MessageStreamPointer] = None,
    ):
        """GetMessagesGRPCObject constructor.

        Args:
            start_timestamp: Start timestamp of search.
            end_timestamp: End timestamp of search.
            stream: Alias of messages.
            search_direction: Search direction.
            result_count_limit: Result count limit.
            stream_pointers: List of stream pointers to restore the search from.
                start_timestamp will be ignored if this parameter is specified. This parameter is only received
                from the provider.
        """
        super().__init__()
        self._start_timestamp = start_timestamp
        self._end_timestamp = end_timestamp
        self._stream = stream
        self._search_direction = search_direction
        self._result_count_limit = result_count_limit
        self._stream_pointers = stream_pointers

    def handle(self, data_source: GRPCDataSource) -> List[MessageGroupResponse]:
        api = data_source.source_api

        start_timestamp = int(
            self._start_timestamp.replace(tzinfo=timezone.utc).timestamp() * 10**9
        )
        end_timestamp = int(self._end_timestamp.replace(tzinfo=timezone.utc).timestamp() * 10**9)

        stream_response = api.search_messages(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            stream=self._stream,
            search_direction=self._search_direction,
            result_count_limit=self._result_count_limit,
            stream_pointer=self._stream_pointers,
        )
        for response in stream_response:
            if response.WhichOneof("data") == "message":
                response = self._handle_adapters(response)
                yield response.message


class GetMessages(IGRPCCommand, IAdaptableCommand):
    """A Class-Command for request to lw-data-provider.

    It searches messages stream by options.

    Returns:
        Iterable[dict]: Stream of Th2 messages.
    """

    def __init__(
        self,
        start_timestamp: datetime,
        stream: List[Union[str, Streams]],
        end_timestamp: datetime = None,
        search_direction: str = "NEXT",
        result_count_limit: int = None,
        stream_pointers: List[MessageStreamPointer] = None,
        cache: bool = False,
    ):
        """GetMessages constructor.

        Args:
            start_timestamp: Start timestamp of search.
            end_timestamp: End timestamp of search.
            stream: Alias of messages.
            search_direction: Search direction.
            result_count_limit: Result count limit.
            stream_pointers: List of stream pointers to restore the search from.
                start_timestamp will be ignored if this parameter is specified. This parameter is only received
                from the provider.
            cache: If True, all requested data from rpt-data-provider will be saved to cache.
        """
        super().__init__()
        self._start_timestamp = start_timestamp
        self._end_timestamp = end_timestamp
        self._stream = stream
        self._search_direction = search_direction
        self._result_count_limit = result_count_limit
        self._stream_pointers = stream_pointers
        self._cache = cache

        self._decoder = GRPCObjectToDictAdapter()
        self._wrapper_deleter = DeleteMessageWrappersAdapter()

    def handle(self, data_source: GRPCDataSource) -> Data:
        source = partial(self.__handle_stream, data_source)
        return Data(source, cache=self._cache)

    def __handle_stream(self, data_source: GRPCDataSource) -> Iterable[dict]:
        stream = GetMessagesGRPCObject(
            start_timestamp=self._start_timestamp,
            end_timestamp=self._end_timestamp,
            stream=self._stream,
            search_direction=self._search_direction,
            result_count_limit=self._result_count_limit,
            stream_pointers=self._stream_pointers,
        ).handle(data_source)
        for message in stream:
            message = self._decoder.handle(message)
            message = self._wrapper_deleter.handle(message)
            message = self._handle_adapters(message)
            yield message

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
from __future__ import annotations
from typing import Any

from grpc._channel import _InactiveRpcError

from typing import TYPE_CHECKING

from th2_data_services.exceptions import CommandError
from th2_data_services.interfaces import IEventStruct, IMessageStruct

if TYPE_CHECKING:
    from th2_data_services.data_source.lwdp_v2_1.interfaces.command import IGRPCCommand

from th2_data_services.data_source.lwdp_v2_1.interfaces.data_source import IGRPCDataSource

import logging

from th2_data_services.data_source.lwdp_v2_1.stub_builder import IEventStub, IMessageStub
from th2_data_services.data_source.lwdp_v2_1.source_api import GRPCAPI
from th2_data_services.data_source.lwdp_v2_1.struct import (
    grpc_message_struct,
    grpc_event_struct,
)
from th2_data_services.data_source.lwdp_v2_1.stub_builder import (
    grpc_event_stub_builder,
    grpc_message_stub_builder,
)

logger = logging.getLogger(__name__)


class GRPCDataSource(IGRPCDataSource):
    """DataSource class which provide work with lw-data-provider.

    Protocol: GRPC
    """

    def __init__(
        self,
        url: str,
        event_struct: IEventStruct = grpc_event_struct,
        message_struct: IMessageStruct = grpc_message_struct,
        event_stub_builder: IEventStub = grpc_event_stub_builder,
        message_stub_builder: IMessageStub = grpc_message_stub_builder,
    ):
        """GRPCDataSource constructor.

        Args:
            url: Url of lw-data-provider.
            event_struct: Event structure that is supplied by lw-data-provider.
            message_struct: Message structure that is supplied by lw-data-provider.
            event_stub_builder: Stub builder for broken events.
            message_stub_builder: Stub builder for broken messages.
        """
        super().__init__(
            url=url,
            event_struct=event_struct,
            message_struct=message_struct,
            event_stub_builder=event_stub_builder,
            message_stub_builder=message_stub_builder,
        )

        self.__provider_api = GRPCAPI(url)

        logger.info(url)

    def command(self, cmd: IGRPCCommand) -> Any:
        """Execute the transmitted GRPC command.

        Args:
            cmd: GRPC Command.

        Returns:
            Any: Command response.

        Raises:
            CommandError: If the command was broken.
        """
        try:
            return cmd.handle(data_source=self)
        except _InactiveRpcError as info:
            raise CommandError(
                f"The command '{cmd.__class__.__name__}' was broken. Details of error:\n{info.details()}"
            )

    @property
    def source_api(self) -> GRPCAPI:
        """Returns Provider API."""
        return self.__provider_api

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
from th2_data_services.data_source.lwdp_v2_1.interfaces.data_source import (
    ILwDPDataSource,
    IGRPCDataSource,
    IHTTPDataSource,
)
from th2_data_services.interfaces import ICommand


class ILwDPCommand(ICommand):
    """Interface of command for lwdp-data-provider."""

    @abstractmethod
    def handle(self, data_source: ILwDPDataSource):
        pass


class IHTTPCommand(ILwDPCommand):
    """Interface of command for rpt-data-provider which works via HTTP."""

    @abstractmethod
    def handle(self, data_source: IHTTPDataSource):
        pass


class IGRPCCommand(ILwDPCommand):
    """Interface of command for lwdp-data-provider.

    Lwdp-data-provider version: 1.1.x
    Protocol: GRPC
    """

    @abstractmethod
    def handle(self, data_source: IGRPCDataSource):
        pass

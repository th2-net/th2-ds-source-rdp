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

"""
This package includes a copy of the code from the repository
at https://github.com/th2-net/th2-ds-source-lwdp, branch "release-2.1".
"""

from .stub_builder import BrokenEvent, BrokenMessage
from .message_response_format import ResponseFormat
from .streams import Stream, Streams
from .page import Page

from th2_data_services.config import options as _o

from th2_data_services.data_source.lwdp_v2_1.resolver import (
    LwdpEventFieldsResolver,
    LwdpMessageFieldsResolver,
    LwdpSubMessageFieldResolver,
    ExpandedMessageFieldResolver,
)

_o.setup_resolvers(
    LwdpEventFieldsResolver(),
    LwdpMessageFieldsResolver(),
    LwdpSubMessageFieldResolver(),
    ExpandedMessageFieldResolver(),
)

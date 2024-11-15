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
from typing import List, Union
from th2_data_services.data_source.lwdp_v2_1.message_response_format import ResponseFormat as RF


class ResponseFormatsChecker:
    def __init__(self):  # noqa
        """ResponseFormats Constructor."""
        self.correct_formats = [RF.JSON_PARSED, RF.BASE64, RF.PROTO_PARSED]

    def is_valid_response_format(self, formats: Union[str, List[str]]):
        if formats is None:
            return True
        if isinstance(formats, str):
            formats = [formats]
        if not isinstance(formats, list):
            raise Exception("Wrong type. formats should be list or string")
        if RF.PROTO_PARSED in formats and RF.JSON_PARSED in formats:
            raise Exception(
                f"{RF.PROTO_PARSED} and {RF.JSON_PARSED} can't be used together for format"
            )
        return all(format in self.correct_formats for format in formats)

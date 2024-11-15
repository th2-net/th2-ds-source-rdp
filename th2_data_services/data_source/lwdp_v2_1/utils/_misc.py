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
from datetime import datetime, timezone
from typing import List

from th2_data_services.data_source.lwdp_v2_1 import ResponseFormat
from th2_data_services.data_source.lwdp_v2_1.utils._response_formats import ResponseFormatsChecker


def _check_list_or_tuple(variable, var_name):  # noqa
    if not (isinstance(variable, tuple) or isinstance(variable, list)):
        raise TypeError(f"{var_name} argument has to be list or tuple type. Got {type(variable)}")


def _check_datetime(dt: datetime):
    if not isinstance(dt, datetime):
        raise TypeError("Provided timestamp should be `datetime` object in UTC time")


def _check_response_formats(formats: List[str]):
    rf = ResponseFormatsChecker()
    if not rf.is_valid_response_format(formats):
        raise Exception("Invalid response format")


def _get_response_format(formats: List[str]):
    if formats is None:
        return [ResponseFormat.JSON_PARSED]
    elif isinstance(formats, str):
        return [formats]
    else:
        return formats


def get_utc_datetime_now():  # noqa
    return datetime.now(timezone.utc).replace(microsecond=0)

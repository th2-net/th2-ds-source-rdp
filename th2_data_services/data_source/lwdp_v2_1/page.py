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
from datetime import datetime
from typing import Dict, Optional

from th2_data_services.utils.converters import ProtobufTimestampConverter


class Page:
    def __init__(self, data: Dict):  # noqa
        """Page Constructor.

        Args:
            data (Dict): Page Data
        """
        self.data: dict = data  # Original data dict.
        self.book: str = data["id"]["book"]
        self.name: str = data["id"]["name"]
        self.comment: str = data["comment"]
        self.start_timestamp: Dict[str, int] = data["started"]  # eg. {'epochSeconds': 0, 'nano': 0}
        self.end_timestamp: Optional[Dict[str, int]] = data["ended"]
        self.updated = data["updated"]
        self.removed = data["removed"]

    @property
    def start_timestamp_datetime(self) -> datetime:
        return ProtobufTimestampConverter.to_datetime(self.start_timestamp)

    @property
    def end_timestamp_datetime(self) -> Optional[datetime]:
        if self.end_timestamp is None:
            return None
        else:
            return ProtobufTimestampConverter.to_datetime(self.end_timestamp)

    def repr_without_book(self):
        return (
            f"Page<'{self.name}', "
            f"{self.start_timestamp_datetime} - {self.end_timestamp_datetime}, "
            f"comment: '{self.comment}', updated: {self.updated}, removed: {self.removed}>"
        )

    def __str__(self):  # noqa
        return (
            f"Page<'{self.name}', book: '{self.book}', "
            f"{self.start_timestamp_datetime} - {self.end_timestamp_datetime}, "
            f"comment: '{self.comment}', updated: {self.updated}, removed: {self.removed}>"
        )

    def __repr__(self):  # noqa
        return self.__str__()


class PageNotFound(Exception):
    def __init__(self, name: str, book: str):
        """Exception for the case when the page was not found in data source.

        Args:
            name: Page Name
            book: Book ID
        """
        self._name = name
        self._book = book

    def __str__(self):
        return f"Unable to find the page with name '{self._name}' in book '{self._book}'."


if __name__ == "__main__":
    print(
        Page(
            {
                "id": {"book": "poc202306", "name": "auto-page-1686582003737"},
                "comment": None,
                "started": {"epochSecond": 1686582003, "nano": 737594000},
                "ended": {"epochSecond": 1686614400, "nano": 0},
                "updated": None,
                "removed": None,
            }
        ).repr_without_book()
    )
    print(
        Page(
            {
                "id": {"book": "poc202306", "name": "auto-page-1686589203737"},
                "comment": None,
                "started": {"epochSecond": 1686614400, "nano": 0},
                "ended": {"epochSecond": 1686700800, "nano": 0},
                "updated": None,
                "removed": None,
            }
        )
    )
    print(
        Page(
            {
                "id": {"book": "poc202306", "name": "auto-page-1686618003736"},
                "comment": None,
                "started": {"epochSecond": 1686700800, "nano": 0},
                "ended": None,
                "updated": None,
                "removed": None,
            }
        )
    )

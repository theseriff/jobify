"""Minimal example of Jobify with manually configured fast components.

Demonstrates:
- Using PydanticTypeAdapter as dumper/loader.
- OrjsonSerializer for fast JSON serialization.
- UUID7 generator for time-sortable IDs.
- Pushing a job and awaiting its result.

Requires the ``fast`` extra to be installed. Install it with::

dependencies = [
    "jobify[fast]>=0.13.0",
    "uuid7-rs>=0.0.8",
]
"""

import asyncio
from datetime import datetime, timezone
from typing import NamedTuple
from uuid import UUID

from uuid7_rs.compat import uuid7

from jobify import Jobify
from jobify.serializers.orjson import OrjsonSerializer
from jobify.typeadapter import PydanticConverter

adapter = PydanticConverter()  # or use adaptix: `uv add adaptix`
# from adaptix import Retort
# adapter = Retort()

# Manually configure fast components
app = Jobify(
    serializer=OrjsonSerializer(),
    dumper=adapter,
    loader=adapter,
    uuid_generator=uuid7,
)


class User(NamedTuple):
    id: UUID
    name: str
    created_at: datetime


db: dict[UUID, User] = {}


@app.task(name="Create new user")
async def add_user(user: User) -> UUID:
    db[user.id] = user
    return user.id


async def main() -> None:
    async with app:
        now = datetime.now(timezone.utc)
        # Creating a user with uuid7
        user = User(uuid7(), "Ivan Zolo", now)
        # Scheduling the task
        job = await add_user.push(user)
        # Awaiting job completion and getting the result
        user_id = await job
        print(f"User with id: {user_id} has been added")


if __name__ == "__main__":
    asyncio.run(main())

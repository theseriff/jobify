import asyncio
from unittest.mock import AsyncMock, patch

from examples import fast_setup


def test_fast_setup() -> None:
    with patch.object(fast_setup.app.configs, "storage", new=AsyncMock()):
        asyncio.run(fast_setup.main())

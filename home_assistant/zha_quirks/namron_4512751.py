"""ZHA quirk for Namron 4512751 dimmers that omit command responses."""

from __future__ import annotations

from typing import Any

from zigpy.zcl import foundation
from zigpy.zcl.clusters.general import LevelControl, OnOff
from zhaquirks.builder import QuirkBuilder
from zhaquirks.clusters import CustomCluster


class _NoApplicationReplyCluster(CustomCluster):
    """Send commands without waiting for the device's missing ZCL response."""

    async def command(
        self,
        command_id: int,
        *args: Any,
        manufacturer: int | None = None,
        expect_reply: bool = True,
        **kwargs: Any,
    ) -> tuple[int, foundation.Status]:
        del expect_reply
        kwargs.pop("disable_default_response", None)
        await super().command(
            command_id,
            *args,
            manufacturer=manufacturer,
            expect_reply=False,
            disable_default_response=True,
            **kwargs,
        )
        return command_id, foundation.Status.SUCCESS


class Namron4512751OnOff(_NoApplicationReplyCluster, OnOff):
    """On/off cluster for the affected Namron dimmer."""


class Namron4512751LevelControl(_NoApplicationReplyCluster, LevelControl):
    """Level-control cluster for the affected Namron dimmer."""


(
    QuirkBuilder("NamronAS", "4512751")
    .replaces(Namron4512751OnOff)
    .replaces(Namron4512751LevelControl)
    .add_to_registry()
)

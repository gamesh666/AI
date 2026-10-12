"""Which models are running where, as reported by the edges themselves (heartbeat `models`)."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.edge_device import EdgeDevice
from app.schemas.model_usage import ModelUsage, ModelUsageCamera, ModelUsageDevice, ModelUsageOverview, SilentDevice


class ModelUsageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(self) -> ModelUsageOverview:
        stmt = select(EdgeDevice).options(
            selectinload(EdgeDevice.site), selectinload(EdgeDevice.cameras)
        ).order_by(EdgeDevice.name)
        devices = list((await self.session.execute(stmt)).scalars().all())

        groups: dict[tuple[str, str | None], ModelUsage] = {}
        silent: list[SilentDevice] = []
        for device in devices:
            if device.reported_models is None:
                silent.append(SilentDevice(device_id=device.id, device_uuid=device.device_uuid,
                                           device_name=device.name, status=device.status.value))
                continue
            cameras = {c.code: c for c in device.cameras}
            for m in device.reported_models:
                key = (str(m.get("name")), m.get("version"))
                usage = groups.get(key)
                if usage is None:
                    usage = groups[key] = ModelUsage(
                        name=key[0], version=key[1], type=m.get("type"), task=m.get("task"),
                        labels=m.get("labels") or [], devices=[], camera_count=0,
                    )
                codes = m.get("cameras") or []
                usage.devices.append(ModelUsageDevice(
                    device_id=device.id,
                    device_uuid=device.device_uuid,
                    device_name=device.name,
                    site_name=device.site.name if device.site else None,
                    status=device.status.value,
                    reported_at=device.reported_models_at,
                    cameras=[
                        ModelUsageCamera(code=code, camera_id=cameras[code].id if code in cameras else None,
                                         name=cameras[code].name if code in cameras else None)
                        for code in codes
                    ],
                ))
                usage.camera_count += len(codes)

        versions: dict[str, set[str]] = defaultdict(set)
        for name, version in groups:
            versions[name].add(version or "—")
        for (name, version), usage in groups.items():
            usage.other_versions = sorted(versions[name] - {version or "—"})
        models = sorted(groups.values(), key=lambda u: (u.name.lower(), u.version or ""))
        return ModelUsageOverview(models=models, not_reporting=silent)

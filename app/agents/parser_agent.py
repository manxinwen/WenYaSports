"""ParserAgent: turns a FIT file path into a ParsedActivity."""

import logging

from app.agents.base_agent import BaseAgent
from app.models.activity import ActivityMetadata, ActivityRecord, ParsedActivity
from app.services.fit_parser import FitParseError, parse_fit_file

logger = logging.getLogger(__name__)


class ParserAgent(BaseAgent):
    """Parses a FIT file into a ParsedActivity model."""

    def run(self, file_path: str) -> ParsedActivity:
        try:
            data = parse_fit_file(file_path)
        except FitParseError:
            raise
        except Exception as exc:
            logger.exception("解析FIT文件失败: %s", file_path)
            raise FitParseError(f"解析FIT文件失败: {exc}") from exc

        meta = data["metadata"]
        metadata = ActivityMetadata(
            sport=meta.get("sport") or "unknown",
            start_time=meta["start_time"],
            total_duration_s=float(meta.get("total_timer_time") or 0.0),
            total_distance_m=float(meta.get("total_distance") or 0.0),
            total_ascent_m=float(meta.get("total_ascent") or 0.0),
            total_descent_m=float(meta.get("total_descent") or 0.0),
            avg_hr=(
                float(meta["avg_heart_rate"])
                if meta.get("avg_heart_rate") is not None
                else None
            ),
            max_hr=(
                int(meta["max_heart_rate"])
                if meta.get("max_heart_rate") is not None
                else None
            ),
            avg_speed=(
                float(meta["avg_speed"]) if meta.get("avg_speed") is not None else None
            ),
            max_speed=(
                float(meta["max_speed"]) if meta.get("max_speed") is not None else None
            ),
        )

        records = []
        for rec in data["records"]:
            records.append(
                ActivityRecord(
                    timestamp=rec["timestamp"],
                    lat=rec.get("lat"),
                    lon=rec.get("lon"),
                    hr=int(rec["hr"]) if rec.get("hr") is not None else None,
                    speed=rec.get("speed"),
                    alt=rec.get("alt"),
                    distance=rec.get("distance"),
                    power=rec.get("power"),
                )
            )

        return ParsedActivity(metadata=metadata, records=records)

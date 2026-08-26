"""ParserAgent: turns a FIT file path into a ParsedActivity."""

import logging

from app.agents.base_agent import BaseAgent
from app.models.activity import ActivityMetadata, ActivityRecord, ParsedActivity
from app.services.fit_parser import FitParseError, parse_fit_file

logger = logging.getLogger(__name__)


class ParserAgent(BaseAgent):
    """Parses a FIT file into a ParsedActivity model.

    Supports Harness integration for:
    - Trace recording for observability
    - Message-based communication with other agents
    - Blackboard data sharing
    """

    agent_id = "parser"
    agent_name = "FIT Parser"
    capabilities = ["fit_parsing", "data_extraction", "metadata_parsing"]

    def run(self, file_path: str) -> ParsedActivity:
        self._execution_count += 1
        self._last_input = file_path

        self._trace_step(
            step_type="thought",
            thought=f"开始解析 FIT 文件: {file_path}",
            detail={"file_path": file_path},
        )

        try:
            data = parse_fit_file(file_path)
        except FitParseError:
            self._last_error = str(FitParseError)
            self._trace_step(
                step_type="final",
                thought=f"FIT 解析失败",
                detail={"error": str(FitParseError)},
            )
            raise
        except Exception as exc:
            logger.exception("解析FIT文件失败: %s", file_path)
            self._last_error = str(exc)
            self._trace_step(
                step_type="final",
                thought=f"解析失败: {exc}",
                detail={"error": str(exc)},
            )
            raise FitParseError(f"解析FIT文件失败: {exc}") from exc

        self._trace_step(
            step_type="action",
            thought=f"解析完成，提取 {len(data.get('records', []))} 条记录",
            detail={
                "metadata_keys": list(data.get("metadata", {}).keys()),
                "record_count": len(data.get("records", [])),
            },
        )

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

        result = ParsedActivity(metadata=metadata, records=records)
        self._last_output = result

        if self.blackboard:
            self.write_to_blackboard(
                namespace="parser_results",
                key=file_path.split("/")[-1] if "/" in file_path else file_path,
                value={
                    "sport": metadata.sport,
                    "distance": metadata.total_distance_m,
                    "duration": metadata.total_duration_s,
                    "records_count": len(records),
                },
            )

        self._trace_step(
            step_type="final",
            thought=f"FIT 解析成功: {metadata.total_distance_m:.1f}m, {metadata.total_duration_s:.0f}s",
            detail={
                "sport": metadata.sport,
                "distance_m": metadata.total_distance_m,
                "duration_s": metadata.total_duration_s,
                "records": len(records),
            },
        )

        if self.message_bus:
            self.broadcast_message(
                message_type="agent_completed",
                payload={
                    "agent_id": self.agent_id,
                    "status": "success",
                    "output_summary": f"{metadata.total_distance_m:.1f}m parsed",
                },
            )

        return result

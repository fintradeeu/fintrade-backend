"""Video optimization helpers for S3-backed uploads."""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote, urlparse

import boto3
from botocore.config import Config

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class S3ObjectRef:
    bucket: str
    key: str


def is_video_content(content_type: str | None, filename: str | None = None) -> bool:
    if content_type and content_type.lower().startswith("video/"):
        return True
    ext = os.path.splitext(filename or "")[1].lower()
    return ext in {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


def s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )


def public_s3_url(bucket: str, key: str) -> str:
    return f"https://{bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


def parse_s3_url(file_url: str) -> S3ObjectRef:
    parsed = urlparse(file_url)
    host_parts = parsed.netloc.split(".")

    if len(host_parts) >= 4 and host_parts[1] == "s3":
        bucket = host_parts[0]
        key = unquote(parsed.path.lstrip("/"))
    elif parsed.netloc.startswith("s3.") or parsed.netloc == "s3.amazonaws.com":
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) != 2:
            raise ValueError("Invalid S3 URL path")
        bucket, key = path_parts[0], unquote(path_parts[1])
    else:
        raise ValueError("Unsupported S3 URL")

    if bucket != settings.AWS_S3_BUCKET:
        raise ValueError("S3 URL bucket does not match configured bucket")
    return S3ObjectRef(bucket=bucket, key=key)


def ffmpeg_available() -> bool:
    return _resolve_ffmpeg_path() is not None


def _resolve_ffmpeg_path() -> Optional[str]:
    configured_path = shutil.which(settings.VIDEO_FFMPEG_PATH)
    if configured_path:
        return configured_path

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def optimize_s3_video(source_url: str, final_url: str, delete_source: Optional[bool] = None) -> None:
    """Download a raw S3 video, optimize it with FFmpeg, upload the final MP4."""
    if not settings.VIDEO_OPTIMIZATION_ENABLED:
        logger.info("video_optimization_skipped_disabled", source_url=source_url)
        return

    ffmpeg_path = _resolve_ffmpeg_path()
    if not ffmpeg_path:
        logger.error("video_optimization_ffmpeg_missing", ffmpeg_path=settings.VIDEO_FFMPEG_PATH)
        return

    source = parse_s3_url(source_url)
    final = parse_s3_url(final_url)
    client = s3_client()
    should_delete_source = settings.VIDEO_DELETE_RAW_AFTER_OPTIMIZE if delete_source is None else delete_source

    with tempfile.TemporaryDirectory(prefix="fintrade-video-") as workdir:
        source_ext = os.path.splitext(source.key)[1] or ".mp4"
        raw_path = os.path.join(workdir, f"raw{source_ext}")
        output_path = os.path.join(workdir, "optimized.mp4")

        logger.info("video_optimization_downloading", source_key=source.key)
        client.download_file(source.bucket, source.key, raw_path)

        scale_filter = (
            f"scale=min({settings.VIDEO_MAX_WIDTH}\\,iw):-2"
            if settings.VIDEO_MAX_WIDTH > 0
            else "scale=iw:-2"
        )
        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            raw_path,
            "-vf",
            scale_filter,
            "-c:v",
            "libx264",
            "-preset",
            settings.VIDEO_FFMPEG_PRESET,
            "-crf",
            str(settings.VIDEO_CRF),
            "-c:a",
            "aac",
            "-b:a",
            settings.VIDEO_AUDIO_BITRATE,
            "-movflags",
            "+faststart",
            output_path,
        ]

        logger.info("video_optimization_started", source_key=source.key, final_key=final.key)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        client.upload_file(
            output_path,
            final.bucket,
            final.key,
            ExtraArgs={"ContentType": "video/mp4"},
        )

        if should_delete_source and source.key != final.key:
            client.delete_object(Bucket=source.bucket, Key=source.key)

        logger.info(
            "video_optimization_finished",
            source_key=source.key,
            final_key=final.key,
            deleted_source=should_delete_source,
        )

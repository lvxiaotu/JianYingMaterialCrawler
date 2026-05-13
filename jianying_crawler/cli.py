from __future__ import annotations

import argparse
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import ensure_storage_dirs, load_config
from .crawlers import CRAWLER_MAP
from .db import connect_postgres, init_db
from .downloader import DownloadService
from .repository import Repository
from .service import build_context
from .structure_report import build_structure_report


def cmd_init_db() -> None:
    config = load_config()
    ensure_storage_dirs(config)
    init_db(config)
    print(f"Initialized database: {config.database_target}")


def cmd_migrate_sqlite(sqlite_path: str | None = None) -> None:
    config = load_config()
    ensure_storage_dirs(config)
    if not config.use_postgres:
        raise RuntimeError("Set config.database_url or JY_DATABASE_URL to a PostgreSQL URL before migration.")

    source_path = sqlite_path or str(config.database_path)
    init_db(config)

    sqlite_conn = sqlite3.connect(source_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = connect_postgres(config.database_url)
    try:
        table_order = ["categories", "items", "downloads", "dependencies", "crawl_state"]
        for table in table_order:
            rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                print(f"{table}: 0")
                continue

            columns = [column for column in rows[0].keys() if column != "id"]
            placeholders = ", ".join(["%s"] * len(columns))
            column_sql = ", ".join(columns)
            update_sql = ", ".join(f"{column}=EXCLUDED.{column}" for column in columns if column not in {"created_at"})

            conflict_map = {
                "categories": "(crawler_name, category_id, category_key, collection_id)",
                "items": "(crawler_name, resource_id)",
                "downloads": "(resource_id, url, url_kind)",
                "dependencies": "(parent_resource_id, child_resource_id, dependency_type)",
                "crawl_state": "(crawler_name, state_key)",
            }
            sql = f"""
                INSERT INTO {table} ({column_sql})
                VALUES ({placeholders})
                ON CONFLICT {conflict_map[table]} DO UPDATE SET
                {update_sql}
            """
            values = [tuple(row[column] for column in columns) for row in rows]
            with pg_conn.cursor() as cur:
                cur.executemany(sql, values)
            pg_conn.commit()
            print(f"{table}: {len(rows)}")
    finally:
        sqlite_conn.close()
        pg_conn.close()


def run_single_crawl(crawler_name: str) -> None:
    context = build_context()
    crawler_cls = CRAWLER_MAP[crawler_name]
    crawler = crawler_cls(context)
    print(f"crawl-start\tcrawler={crawler_name}")
    crawler.run()
    print(f"crawl-finished\tcrawler={crawler_name}")


def cmd_crawl(crawler_names: list[str], parallel: int = 1) -> None:
    normalized_names: list[str] = []
    for crawler_name in crawler_names:
        if crawler_name not in normalized_names:
            normalized_names.append(crawler_name)

    if not normalized_names:
        raise ValueError("At least one crawler is required.")

    if len(normalized_names) == 1 and parallel <= 1:
        run_single_crawl(normalized_names[0])
        return

    worker_count = max(1, min(int(parallel or 1), len(normalized_names)))
    print(
        "crawl-batch-start\t"
        f"count={len(normalized_names)}\t"
        f"parallel={worker_count}\t"
        f"crawlers={','.join(normalized_names)}"
    )

    failures: list[tuple[str, str]] = []

    if worker_count == 1:
        for crawler_name in normalized_names:
            try:
                run_single_crawl(crawler_name)
            except Exception as exc:
                failures.append((crawler_name, str(exc)))
                print(f"crawl-failed\tcrawler={crawler_name}\terror={exc}")
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(run_single_crawl, crawler_name): crawler_name
                for crawler_name in normalized_names
            }
            for future in as_completed(future_map):
                crawler_name = future_map[future]
                try:
                    future.result()
                except Exception as exc:
                    failures.append((crawler_name, str(exc)))
                    print(f"crawl-failed\tcrawler={crawler_name}\terror={exc}")

    print(
        "crawl-batch-summary\t"
        f"count={len(normalized_names)}\t"
        f"parallel={worker_count}\t"
        f"failed={len(failures)}"
    )
    if failures:
        raise SystemExit(1)


def cmd_download(
    crawler_name: str,
    limit: int,
    resource_id: str | None,
    url_kind: str | None,
    interval_seconds: float | None,
    include_auxiliary: bool,
    until_empty: bool,
) -> None:
    context = build_context()
    service = DownloadService(context)
    if until_empty:
        summary = service.run_until_empty(
            crawler_name=crawler_name,
            batch_limit=limit,
            resource_id=resource_id,
            url_kind=url_kind,
            interval_seconds=interval_seconds,
            include_auxiliary=include_auxiliary,
        )
        results = summary.results
    else:
        results = service.run_pending(
            crawler_name=crawler_name,
            limit=limit,
            resource_id=resource_id,
            url_kind=url_kind,
            interval_seconds=interval_seconds,
            include_auxiliary=include_auxiliary,
        )
    if not results:
        if until_empty:
            print(
                "download-summary\t"
                f"crawler={crawler_name}\t"
                "batches=0\t"
                "processed=0\t"
                "status=queue_already_empty"
            )
            return
        print("No pending downloads.")
        return

    for result in results:
        if result.status == "done":
            print(f"done\t{result.resource_id}\t{result.target_path}")
        else:
            print(f"failed\t{result.resource_id}\t{result.error}")

    if until_empty:
        summary_status = "queue_drained"
        if summary.stalled:
            summary_status = "stalled"
        print(
            "download-summary\t"
            f"crawler={crawler_name}\t"
            f"batches={summary.batches}\t"
            f"processed={len(summary.results)}\t"
            f"status={summary_status}"
        )


def cmd_build_structure() -> None:
    config = load_config()
    ensure_storage_dirs(config)
    output_dir = build_structure_report(config)
    print(f"Structure report generated: {output_dir}")


def cmd_cleanup_downloads() -> None:
    config = load_config()
    ensure_storage_dirs(config)
    repo = Repository(config)
    result = repo.cleanup_duplicate_downloads()
    print(
        "cleanup-downloads\t"
        f"before={result['before_count']}\t"
        f"after={result['after_count']}\t"
        f"deleted={result['deleted_count']}\t"
        f"groups={result['duplicate_groups']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="JianYing crawler CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")

    migrate_parser = subparsers.add_parser("migrate-sqlite")
    migrate_parser.add_argument("--sqlite-path", dest="sqlite_path")

    crawl_parser = subparsers.add_parser("crawl")
    crawl_parser.add_argument("crawler_names", nargs="+", choices=sorted(CRAWLER_MAP.keys()))
    crawl_parser.add_argument("--parallel", dest="parallel", type=int, default=1)

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("crawler_name", choices=sorted(CRAWLER_MAP.keys()))
    download_parser.add_argument("--limit", type=int, default=10)
    download_parser.add_argument("--resource-id", dest="resource_id")
    download_parser.add_argument("--url-kind", dest="url_kind")
    download_parser.add_argument("--interval-seconds", dest="interval_seconds", type=float)
    download_parser.add_argument("--include-auxiliary", dest="include_auxiliary", action="store_true")
    download_parser.add_argument("--until-empty", dest="until_empty", action="store_true")

    subparsers.add_parser("build-structure")
    subparsers.add_parser("cleanup-downloads")

    args = parser.parse_args()

    if args.command == "init-db":
        cmd_init_db()
        return

    if args.command == "migrate-sqlite":
        cmd_migrate_sqlite(args.sqlite_path)
        return

    if args.command == "crawl":
        cmd_crawl(args.crawler_names, args.parallel)
        return

    if args.command == "download":
        cmd_download(
            args.crawler_name,
            args.limit,
            args.resource_id,
            args.url_kind,
            args.interval_seconds,
            args.include_auxiliary,
            args.until_empty,
        )
        return

    if args.command == "build-structure":
        cmd_build_structure()
        return

    if args.command == "cleanup-downloads":
        cmd_cleanup_downloads()
        return


if __name__ == "__main__":
    main()

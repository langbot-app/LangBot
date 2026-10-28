"""CLI for running offline LangRAG retrieval benchmarks."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.metrics import dedupe_in_order, evaluate_query, mean_metrics
from benchmarks.sdk_stubs import install_stubs

install_stubs()

from components.knowledge_engine.langrag import LangRAG  # noqa: E402
from langbot_plugin.api.entities.builtin.rag import (  # noqa: E402
    DocumentStatus,
    FileMetadata,
    FileObject,
    IngestionContext,
    ParseContext,
    ParseResult,
    RetrievalContext,
    TextSection,
)

from benchmarks.local_runtime import LocalBenchmarkPlugin  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPO_ROOT / "benchmarks/datasets/mini_zh.json"
DEFAULT_CONFIG = REPO_ROOT / "benchmarks/configs/local_retrieval.json"
DEFAULT_OUT_DIR = REPO_ROOT / "benchmarks/runs"
DEFAULT_PARSER_REPO = REPO_ROOT.parents[1] / "misc/GeneralParsers"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.stdout.strip()
    except Exception:
        return None


def _git_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return bool(result.stdout.strip())
    except Exception:
        return None


def _merge_settings(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    result.update(deepcopy(override))
    return result


def _raw_bytes(document: dict[str, Any]) -> bytes:
    raw = document.get("raw_content", document.get("content", ""))
    return raw.encode(document.get("encoding", "utf-8"))


def _filename(document: dict[str, Any]) -> str:
    return document.get("filename", f"{document.get('title', document['id'])}.txt")


def _mime_type(document: dict[str, Any]) -> str:
    return document.get("mime_type", "text/plain")


def _make_sections(section_rows: list[dict[str, Any]]) -> list[TextSection]:
    return [
        TextSection(
            content=row["content"],
            heading=row.get("heading"),
            level=row.get("level", 0),
            page=row.get("page"),
            metadata=row.get("metadata", {}),
        )
        for row in section_rows
    ]


def _load_general_parsers_class(parser_repo: Path):
    components_dir = parser_repo / "components"
    package_dir = components_dir / "general_parsers"
    init_path = package_dir / "__init__.py"
    if not init_path.exists():
        raise FileNotFoundError(f"GeneralParsers package not found: {package_dir}")

    root_name = "_langbot_parser_components"
    if root_name not in sys.modules:
        spec = importlib.util.spec_from_loader(root_name, loader=None)
        module = importlib.util.module_from_spec(spec)
        module.__path__ = [str(components_dir)]
        sys.modules[root_name] = module

    package_name = f"{root_name}.general_parsers"
    if package_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            package_name,
            init_path,
            submodule_search_locations=[str(package_dir)],
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load parser package from {init_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module
        spec.loader.exec_module(module)

    module = importlib.import_module(f"{package_name}.general_parsers")
    return module.GeneralParsers


async def _general_parse(
    document: dict[str, Any],
    parser_repo: Path,
    plugin: LocalBenchmarkPlugin,
) -> ParseResult:
    parser_class = _load_general_parsers_class(parser_repo)
    parser = parser_class()
    parser.plugin = plugin
    return await parser.parse(
        ParseContext(
            file_content=_raw_bytes(document),
            filename=_filename(document),
            mime_type=_mime_type(document),
            metadata={"dataset_document_id": document["id"]},
        )
    )


async def _parsed_content_for_document(
    document: dict[str, Any],
    parser_mode: str,
    parser_repo: Path,
    plugin: LocalBenchmarkPlugin,
) -> ParseResult | None:
    if parser_mode == "internal":
        return None

    if parser_mode == "general_parsers":
        return await _general_parse(document, parser_repo, plugin)

    if parser_mode != "preparsed":
        raise ValueError(f"Unknown parser_mode: {parser_mode}")

    content = document.get("content", document.get("raw_content", ""))
    return ParseResult(
        text=content,
        sections=_make_sections(document.get("sections", [])),
        metadata={
            "dataset_document_id": document["id"],
            "dataset_title": document.get("title", document["id"]),
            "parser_mode": parser_mode,
        },
    )


def _make_ingestion_context(
    document: dict[str, Any],
    knowledge_base_id: str,
    creation_settings: dict[str, Any],
    parsed_content: ParseResult | None,
) -> IngestionContext:
    return IngestionContext(
        file_object=FileObject(
            metadata=FileMetadata(
                filename=_filename(document),
                file_size=len(_raw_bytes(document)),
                mime_type=_mime_type(document),
                document_id=document["id"],
                knowledge_base_id=knowledge_base_id,
            ),
            storage_path=f"dataset://{document['id']}",
        ),
        knowledge_base_id=knowledge_base_id,
        creation_settings=creation_settings,
        parsed_content=parsed_content,
    )


def _make_retrieval_context(
    query: dict[str, Any],
    knowledge_base_id: str,
    creation_settings: dict[str, Any],
    retrieval_settings: dict[str, Any],
) -> RetrievalContext:
    return RetrievalContext(
        query=query["query"],
        knowledge_base_id=knowledge_base_id,
        creation_settings=creation_settings,
        retrieval_settings=retrieval_settings,
        filters=query.get("filters", {}),
    )


async def _run_experiment(
    dataset: dict[str, Any],
    experiment: dict[str, Any],
    k_values: list[int],
    parser_repo: Path,
) -> dict[str, Any]:
    name = experiment["name"]
    knowledge_base_id = f"bench_{name}"
    engine = LangRAG()
    plugin = LocalBenchmarkPlugin()
    from benchmarks.state_fixture import attach_installation_state
    await attach_installation_state(plugin)
    engine.plugin = plugin
    parser_mode = experiment.get("parser_mode", "preparsed")

    creation_settings = _merge_settings(
        {
            "embedding_model_uuid": "local-hash-256",
            "index_type": "chunk",
            "chunk_size": 512,
            "overlap": 50,
        },
        experiment.get("creation_settings", {}),
    )
    retrieval_settings = _merge_settings(
        {
            "top_k": max(k_values),
            "search_type": "vector",
            "query_rewrite": "off",
            "rerank": "off",
        },
        experiment.get("retrieval_settings", {}),
    )
    retrieval_settings["top_k"] = max(
        int(retrieval_settings.get("top_k", 0)),
        max(k_values),
    )

    started = time.perf_counter()
    parser_seconds = 0.0
    parsed_sections = 0
    ingestion_results = []
    for document in dataset["documents"]:
        storage_path = f"dataset://{document['id']}"
        plugin.storage[storage_path] = _raw_bytes(document)

        parser_started = time.perf_counter()
        parsed_content = await _parsed_content_for_document(
            document=document,
            parser_mode=parser_mode,
            parser_repo=parser_repo,
            plugin=plugin,
        )
        parser_seconds += time.perf_counter() - parser_started
        if parsed_content is not None:
            parsed_sections += len(parsed_content.sections or [])

        context = _make_ingestion_context(
            document=document,
            knowledge_base_id=knowledge_base_id,
            creation_settings=creation_settings,
            parsed_content=parsed_content,
        )
        result = await engine.ingest(context)
        ingestion_results.append(
            {
                "document_id": result.document_id,
                "status": getattr(result.status, "value", result.status),
                "chunks_created": result.chunks_created,
                "error_message": result.error_message,
            }
        )

    ingest_seconds = time.perf_counter() - started
    failed = [
        row
        for row in ingestion_results
        if row["status"] != getattr(DocumentStatus.COMPLETED, "value", "completed")
    ]
    if failed:
        raise RuntimeError(f"Experiment {name} ingestion failed: {failed}")

    query_rows = []
    metric_rows = []
    retrieval_started = time.perf_counter()
    for query in dataset["queries"]:
        context = _make_retrieval_context(
            query=query,
            knowledge_base_id=knowledge_base_id,
            creation_settings=creation_settings,
            retrieval_settings=retrieval_settings,
        )
        response = await engine.retrieve(context)
        retrieved = []
        for entry in response.results:
            metadata = entry.metadata
            retrieved.append(
                {
                    "id": entry.id,
                    "document_id": metadata.get("document_id"),
                    "document_name": metadata.get("document_name"),
                    "distance": entry.distance,
                    "score": entry.score,
                    "heading_path": metadata.get("heading_path", ""),
                }
            )

        retrieved_document_ids = [
            item["document_id"] for item in retrieved if item.get("document_id")
        ]
        ranked_document_ids = dedupe_in_order(retrieved_document_ids)
        metrics = evaluate_query(
            relevant_document_ids=query["relevant_document_ids"],
            retrieved_document_ids=ranked_document_ids,
            k_values=k_values,
        )
        metrics.update(
            _heading_metrics(
                expected_headings=query.get("relevant_headings", []),
                retrieved=retrieved,
                k_values=k_values,
            )
        )
        metric_rows.append(metrics)
        query_rows.append(
            {
                "id": query["id"],
                "query": query["query"],
                "relevant_document_ids": query["relevant_document_ids"],
                "ranked_document_ids": ranked_document_ids,
                "retrieved": retrieved,
                "metrics": metrics,
            }
        )

    retrieve_seconds = time.perf_counter() - retrieval_started
    summary = mean_metrics(metric_rows)
    summary.update(
        {
            "parser_mode": parser_mode,
            "documents": len(dataset["documents"]),
            "queries": len(dataset["queries"]),
            "chunks_created": sum(row["chunks_created"] for row in ingestion_results),
            "vectors_stored": plugin.vector_count(knowledge_base_id),
            "vectors_with_heading_path": _count_heading_vectors(
                plugin,
                knowledge_base_id,
            ),
            "parsed_sections": parsed_sections,
            "embedding_calls": plugin.embedding_calls,
            "llm_calls": plugin.llm_calls,
            "parser_seconds": parser_seconds,
            "ingest_seconds": ingest_seconds,
            "retrieve_seconds": retrieve_seconds,
        }
    )

    return {
        "name": name,
        "description": experiment.get("description", ""),
        "parser_mode": parser_mode,
        "creation_settings": creation_settings,
        "retrieval_settings": retrieval_settings,
        "summary": summary,
        "ingestion": ingestion_results,
        "queries": query_rows,
    }


def _count_heading_vectors(plugin: LocalBenchmarkPlugin, collection_id: str) -> int:
    return sum(
        1
        for record in plugin.collections.get(collection_id, {}).values()
        if record.metadata.get("heading_path")
    )


def _heading_metrics(
    expected_headings: list[str],
    retrieved: list[dict[str, Any]],
    k_values: list[int],
) -> dict[str, float]:
    if not expected_headings:
        return {}

    lowered = [heading.lower() for heading in expected_headings]
    result = {}
    for k in k_values:
        top_items = retrieved[:k]
        hit = any(
            expected in (item.get("heading_path") or "").lower()
            for item in top_items
            for expected in lowered
        )
        result[f"heading_hit@{k}"] = 1.0 if hit else 0.0
    return result


async def run_benchmark(
    dataset_path: Path,
    config_path: Path,
    out_dir: Path,
    run_id: str | None = None,
    parser_repo: Path = DEFAULT_PARSER_REPO,
) -> dict[str, Any]:
    dataset = _read_json(dataset_path)
    config = _read_json(config_path)
    k_values = [
        int(k)
        for k in config.get("metrics", {}).get("k_values", [1, 3, 5])
    ]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if run_id is None:
        run_id = f"{timestamp}_{_sha256(config_path)[:8]}_{_sha256(dataset_path)[:8]}"

    experiments = []
    for experiment in config["experiments"]:
        experiments.append(
            await _run_experiment(
                dataset=dataset,
                experiment=experiment,
                k_values=k_values,
                parser_repo=parser_repo,
            )
        )

    result = {
        "run": {
            "run_id": run_id,
            "timestamp_utc": timestamp,
            "git_commit": _git_commit(),
            "git_dirty": _git_dirty(),
            "python": sys.version,
            "platform": platform.platform(),
            "dataset_path": str(dataset_path),
            "dataset_sha256": _sha256(dataset_path),
            "config_path": str(config_path),
            "config_sha256": _sha256(config_path),
            "parser_repo": str(parser_repo),
        },
        "dataset": {
            "id": dataset.get("id", dataset_path.stem),
            "description": dataset.get("description", ""),
            "documents": len(dataset["documents"]),
            "queries": len(dataset["queries"]),
        },
        "config": {
            "id": config.get("id", config_path.stem),
            "description": config.get("description", ""),
            "k_values": k_values,
        },
        "experiments": experiments,
    }

    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "results.json"
    result["run"]["output_path"] = str(output_path)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    return result


def _print_summary(result: dict[str, Any]) -> None:
    k_values = result["config"]["k_values"]
    primary_k = 3 if 3 in k_values else k_values[-1]
    metric_names = [
        f"hit@{primary_k}",
        f"all_relevant@{primary_k}",
        f"recall@{primary_k}",
        f"mrr@{primary_k}",
        f"ndcg@{primary_k}",
    ]
    if any(
        f"heading_hit@{primary_k}" in experiment["summary"]
        for experiment in result["experiments"]
    ):
        metric_names.append(f"heading_hit@{primary_k}")
    header = [
        "experiment",
        "parser",
        "vectors",
        "headings",
        "chunks",
        "parser_s",
        "ingest_s",
        "retrieve_s",
        *metric_names,
    ]
    print("\t".join(header))
    for experiment in result["experiments"]:
        summary = experiment["summary"]
        row = [
            experiment["name"],
            experiment["parser_mode"],
            str(summary["vectors_stored"]),
            str(summary["vectors_with_heading_path"]),
            str(summary["chunks_created"]),
            f"{summary['parser_seconds']:.4f}",
            f"{summary['ingest_seconds']:.4f}",
            f"{summary['retrieve_seconds']:.4f}",
            *(f"{summary[name]:.4f}" for name in metric_names),
        ]
        print("\t".join(row))

    print(f"\nWrote benchmark results to {result['run']['output_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--parser-repo",
        type=Path,
        default=Path(os.environ.get("LANGBOT_PARSER_REPO", DEFAULT_PARSER_REPO)),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(
        run_benchmark(
            dataset_path=args.dataset,
            config_path=args.config,
            out_dir=args.out,
            run_id=args.run_id,
            parser_repo=args.parser_repo,
        )
    )
    _print_summary(result)


if __name__ == "__main__":
    main()

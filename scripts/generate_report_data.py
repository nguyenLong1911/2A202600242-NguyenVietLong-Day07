from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import load_documents_from_files
from src import (
    ChunkingStrategyComparator,
    EmbeddingStore,
    FixedSizeChunker,
    KnowledgeBaseAgent,
    OpenAIChatLLM,
    OpenAIEmbedder,
    RecursiveChunker,
    SentenceChunker,
    Document,
    compute_similarity,
)


def infer_doc_metadata(doc_id: str) -> dict:
    doc_id_lc = doc_id.lower()
    metadata = {
        "model": "unknown",
        "doc_type": "other",
        "language": "en",
        "region": "global",
    }

    if "vf3" in doc_id_lc:
        metadata["model"] = "VF3"
    elif "vf6" in doc_id_lc:
        metadata["model"] = "VF6"
    elif "vf8" in doc_id_lc:
        metadata["model"] = "VF8"
    elif "vf9" in doc_id_lc:
        metadata["model"] = "VF9"

    if "warranty" in doc_id_lc:
        metadata["doc_type"] = "warranty"
    elif "spec" in doc_id_lc:
        metadata["doc_type"] = "spec"
    elif "first_responder" in doc_id_lc:
        metadata["doc_type"] = "first_responder"

    if "_vn_" in doc_id_lc or "vn" in doc_id_lc:
        metadata["region"] = "VN"
        metadata["language"] = "vi"
    elif "us" in doc_id_lc:
        metadata["region"] = "US"

    if "warranty" in doc_id_lc and "vn" in doc_id_lc:
        metadata["language"] = "vi"

    return metadata


def keyword_hit_count(text: str, keywords: list[str]) -> int:
    text_lc = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in text_lc)


def chunk_documents_by_strategy(
    docs: list[Document],
    strategy: str,
    chunk_size: int = 1200,
) -> list[Document]:
    strategy_name = (strategy or "recursive").strip().lower()
    if strategy_name == "fixed_size":
        chunker = FixedSizeChunker(chunk_size=chunk_size, overlap=min(120, max(0, chunk_size // 10)))
    elif strategy_name == "by_sentences":
        chunker = SentenceChunker(max_sentences_per_chunk=4)
    else:
        chunker = RecursiveChunker(chunk_size=chunk_size)

    chunked_docs: list[Document] = []
    for doc in docs:
        chunks = chunker.chunk(doc.content)
        if not chunks:
            continue

        if len(chunks) == 1 and chunks[0] == doc.content:
            metadata = dict(doc.metadata)
            metadata.update({"chunking_strategy": strategy_name})
            chunked_docs.append(Document(id=doc.id, content=doc.content, metadata=metadata))
            continue

        for index, chunk in enumerate(chunks, start=1):
            metadata = dict(doc.metadata)
            metadata.update(
                {
                    "doc_id": doc.id,
                    "chunk_index": index,
                    "chunking_strategy": strategy_name,
                }
            )
            chunked_docs.append(
                Document(
                    id=f"{doc.id}__chunk{index:03d}",
                    content=chunk,
                    metadata=metadata,
                )
            )
    return chunked_docs


def summarize_text(text: str, max_len: int = 180) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


def answer_from_retrieved(query: str, retrieved: list[dict], llm: OpenAIChatLLM) -> str:
    if not retrieved:
        return "No relevant chunk found for this filtered query."

    context_lines: list[str] = []
    for index, item in enumerate(retrieved, start=1):
        source = (item.get("metadata") or {}).get("source", "unknown")
        content = item.get("content", "")
        context_lines.append(f"[{index}] source={source}\n{content}")

    prompt = (
        "You are a helpful assistant. Use only the provided context. "
        "If context is insufficient, say so clearly.\n\n"
        f"Question:\n{query}\n\n"
        f"Context:\n{chr(10).join(context_lines)}\n\n"
        "Answer:"
    )
    return llm(prompt)


def run(strategy: str = "recursive", store_chunk_size: int = 1200) -> dict:
    load_dotenv()

    selected_files = [
        "data/vinfast_markdown_clean/VF3_spec.md",
        "data/vinfast_markdown_clean/vf3_vn_warranty.md",
        "data/vinfast_markdown_clean/20230927_VF6_VN_VN_1_1706781000_Warranty.md",
        "data/vinfast_markdown_clean/VF9 US Vehicle Warranty Booklet.md",
        "data/vinfast_markdown_clean/VINFAST_VF8_First_Responder_Guide.md",
    ]

    docs = load_documents_from_files(selected_files)
    for doc in docs:
        doc.metadata.update(infer_doc_metadata(doc.id))

    data_inventory = [
        {
            "id": doc.id,
            "source": doc.metadata.get("source", ""),
            "char_count": len(doc.content),
            "extension": doc.metadata.get("extension", ""),
            "model": doc.metadata.get("model", ""),
            "doc_type": doc.metadata.get("doc_type", ""),
            "language": doc.metadata.get("language", ""),
            "region": doc.metadata.get("region", ""),
        }
        for doc in docs
    ]
    source_by_id = {doc.id: doc.metadata.get("source", "") for doc in docs}

    comparator = ChunkingStrategyComparator()
    chunking_stats = {}
    for doc in docs[:3]:
        compared = comparator.compare(doc.content, chunk_size=500)
        chunking_stats[doc.id] = {
            name: {
                "count": stats["count"],
                "avg_length": round(stats["avg_length"], 2),
            }
            for name, stats in compared.items()
        }

    embedder = OpenAIEmbedder(model_name="text-embedding-3-small")
    llm = OpenAIChatLLM(model_name="gpt-4o-mini")

    similarity_pairs = [
        {
            "pair": 1,
            "sentence_a": "VF3 warranty covers repair for manufacturing defects.",
            "sentence_b": "Vehicle warranty includes repairs for manufacturer defects.",
            "prediction": "high",
        },
        {
            "pair": 2,
            "sentence_a": "Code of conduct requires ethical behavior.",
            "sentence_b": "Employees must follow integrity and ethics guidelines.",
            "prediction": "high",
        },
        {
            "pair": 3,
            "sentence_a": "The first responder guide explains emergency handling.",
            "sentence_b": "Sustainability report discusses carbon emissions.",
            "prediction": "low",
        },
        {
            "pair": 4,
            "sentence_a": "Bảo hành pin có điều kiện áp dụng riêng.",
            "sentence_b": "Chính sách bảo hành xe điện có phạm vi cụ thể.",
            "prediction": "high",
        },
        {
            "pair": 5,
            "sentence_a": "Audit committee oversees compliance and governance.",
            "sentence_b": "How to charge the VF3 battery at home safely.",
            "prediction": "low",
        },
    ]

    for pair in similarity_pairs:
        vec_a = embedder(pair["sentence_a"])
        vec_b = embedder(pair["sentence_b"])
        score = compute_similarity(vec_a, vec_b)
        pair["actual_score"] = round(score, 4)
        if score >= 0.65:
            level = "high"
        elif score <= 0.45:
            level = "low"
        else:
            level = "medium"
        pair["actual_label"] = level
        pair["is_correct"] = (pair["prediction"] == level) or (
            pair["prediction"] == "high" and level == "medium"
        )

    docs_for_store = chunk_documents_by_strategy(docs, strategy=strategy, chunk_size=store_chunk_size)
    store = EmbeddingStore(collection_name="vinfast_report_store", embedding_fn=embedder)
    store.add_documents(docs_for_store)
    agent = KnowledgeBaseAgent(store=store, llm_fn=llm)

    benchmark_queries = [
        {
            "id": 1,
            "query": "What is the battery capacity and range of the VinFast VF3?",
            "gold_answer": "Battery type LFP, capacity 18.64 kWh, and range around 210 km (NEDC).",
            "metadata_filter": None,
            "relevant_keywords": ["battery", "capacity", "18.64", "range", "210"],
            "min_keyword_hits": 3,
        },
        {
            "id": 2,
            "query": "Thời hạn bảo hành chung của xe VinFast VF3 là bao lâu?",
            "gold_answer": "7 năm hoặc 160.000 km (thường), 3 năm hoặc 100.000 km (thương mại), tính từ ngày kích hoạt bảo hành.",
            "metadata_filter": None,
            "relevant_keywords": ["7 năm", "160.000", "3 năm", "100.000", "kích hoạt bảo hành"],
            "min_keyword_hits": 2,
        },
        {
            "id": 3,
            "query": "Những hư hỏng nào không được VinFast bảo hành?",
            "gold_answer": "Các hư hỏng do sửa chữa trái phép, lạm dụng, thiên tai/tai nạn, hao mòn tự nhiên hoặc phụ tùng không chính hãng không thuộc phạm vi bảo hành.",
            "metadata_filter": None,
            "relevant_keywords": [
                "không thuộc phạm vi bảo hành",
                "hao mòn",
                "không chính hãng",
                "thiên tai",
                "tai nạn",
            ],
            "min_keyword_hits": 2,
        },
        {
            "id": 4,
            "query": "How should first responders handle a VinFast VF8 high-voltage battery fire?",
            "gold_answer": "Assume HV components are live, wear PPE, use large amounts of water, and account for re-ignition risk.",
            "metadata_filter": None,
            "relevant_keywords": ["hv", "battery", "fire", "water", "ppe", "reignite"],
            "min_keyword_hits": 2,
        },
        {
            "id": 5,
            "query": "What is the battery warranty period for VinFast vehicles?",
            "gold_answer": "VF3 VN battery warranty is 8 years or 160,000 km for non-commercial usage; cross-doc answers should be constrained by model/doc_type filter.",
            "metadata_filter": {"model": "VF3", "doc_type": "warranty"},
            "relevant_keywords": ["pin", "8 năm", "160.000"],
            "min_keyword_hits": 2,
        },
    ]

    benchmark_results = []
    top3_relevant = 0

    for item in benchmark_queries:
        unfiltered_top1_source = ""
        unfiltered_top1_score = 0.0

        if item["id"] == 5:
            unfiltered = store.search(item["query"], top_k=3)
            if unfiltered:
                unfiltered_top1_source = (unfiltered[0].get("metadata") or {}).get("source", "")
                unfiltered_top1_score = round(float(unfiltered[0].get("score", 0.0)), 4)

        if item["metadata_filter"]:
            retrieved = store.search_with_filter(
                item["query"],
                top_k=3,
                metadata_filter=item["metadata_filter"],
            )
            answer = answer_from_retrieved(item["query"], retrieved, llm)
        else:
            retrieved = store.search(item["query"], top_k=3)
            answer = agent.answer(item["query"], top_k=3)

        top1 = retrieved[0] if retrieved else {"content": "", "score": 0.0, "metadata": {}}
        source = (top1.get("metadata") or {}).get("source", "")
        top1_summary = summarize_text(top1.get("content", ""))

        answer_summary = summarize_text(answer, max_len=260)

        relevant = False
        for candidate in retrieved[:3]:
            content = candidate.get("content", "")
            hit_count = keyword_hit_count(content, item.get("relevant_keywords", []))
            if hit_count >= item.get("min_keyword_hits", 1):
                relevant = True
                break
        if relevant:
            top3_relevant += 1

        benchmark_results.append(
            {
                "id": item["id"],
                "query": item["query"],
                "gold_answer": item["gold_answer"],
                "top1_source": source,
                "top1_score": round(float(top1.get("score", 0.0)), 4),
                "top1_summary": top1_summary,
                "relevant": relevant,
                "agent_answer_summary": answer_summary,
                "relevant_keywords": item.get("relevant_keywords", []),
                "min_keyword_hits": item.get("min_keyword_hits", 1),
                "metadata_filter": item["metadata_filter"],
                "unfiltered_top1_source": unfiltered_top1_source,
                "unfiltered_top1_score": unfiltered_top1_score,
            }
        )

    return {
        "chunking_strategy": strategy,
        "store_chunk_size": store_chunk_size,
        "selected_files": selected_files,
        "data_inventory": data_inventory,
        "chunking_stats": chunking_stats,
        "similarity_pairs": similarity_pairs,
        "store_document_count": store.get_collection_size(),
        "benchmark_results": benchmark_results,
        "top3_relevant_count": top3_relevant,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate benchmark data for report")
    parser.add_argument(
        "--strategy",
        choices=["recursive", "fixed_size", "by_sentences"],
        default="recursive",
        help="Chunking strategy used for store ingestion",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1200,
        help="Chunk size for fixed_size/recursive strategies",
    )
    parser.add_argument(
        "--output",
        default="report/report_data.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    report_data = run(strategy=args.strategy, store_chunk_size=args.chunk_size)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved report data to {output_path}")
    print(f"Chunking strategy: {report_data['chunking_strategy']}")
    print(f"Store size: {report_data['store_document_count']}")
    print(f"Top-3 relevant: {report_data['top3_relevant_count']}/5")

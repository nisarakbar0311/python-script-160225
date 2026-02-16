from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Document:
    doc_url: str
    doc_type: str
    title: str
    subtitle: Optional[str]
    file_size_kb: Optional[int]
    active_substances: List[str]
    product_label: str
    product_url: str
    collected_at_utc: str = field(default_factory=utc_now_iso)

    def to_pdf_link_entry(self) -> Dict[str, object]:
        return {
            "pdf_url": self.doc_url,
            "doc_type": self.doc_type,
            "title": self.title,
            "subtitle": self.subtitle,
            "file_size_kb": self.file_size_kb,
            "active_substances": self.active_substances,
            "product_label": self.product_label,
            "product_url": self.product_url,
            "full_url": self.doc_url,
            "collected_at_utc": self.collected_at_utc,
        }

    def to_ultra_entry(self) -> Dict[str, object]:
        return {
            "doc_url": self.doc_url,
            "doc_type": self.doc_type,
            "title": self.title,
            "subtitle": self.subtitle,
            "file_size_kb": self.file_size_kb,
            "active_substances": self.active_substances,
            "product_label": self.product_label,
            "product_url": self.product_url,
        }


@dataclass
class Product:
    label: str
    product_url: str
    documents: List[Document] = field(default_factory=list)

    def to_ultra_entry(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "product_url": self.product_url,
            "documents": [doc.to_ultra_entry() for doc in self.documents],
        }

    def to_structure_mapping(self) -> List[str]:
        results: List[str] = []
        for doc in self.documents:
            if doc.subtitle:
                results.append(doc.subtitle)
            elif doc.title:
                results.append(doc.title)
        return results


@dataclass
class Substance:
    name: str
    substance_url: str
    products: List[Product] = field(default_factory=list)

    def to_ultra_entry(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "substance_url": self.substance_url,
            "sub_drugs": [product.to_ultra_entry() for product in self.products],
        }

    def to_structure_mapping(self) -> Dict[str, List[str]]:
        return {product.label: product.to_structure_mapping() for product in self.products}


@dataclass
class LetterBucket:
    letter: str
    substances: List[Substance] = field(default_factory=list)

    def to_ultra_entry(self) -> Dict[str, object]:
        return {
            "letter": self.letter,
            "substances": [substance.to_ultra_entry() for substance in self.substances],
        }

    def to_structure_mapping(self) -> Dict[str, Dict[str, List[str]]]:
        return {substance.name: substance.to_structure_mapping() for substance in self.substances}


@dataclass
class ExtractionResults:
    letters: List[LetterBucket]
    generated_at_utc: str
    source: str

    def to_mhra_ultra(self) -> Dict[str, object]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "source": self.source,
            "crawler_info": {
                "strategy": "Ultra 3.0 - Full Extraction with Structure",
                "total_letters": len(self.letters),
                "concurrency": {
                    "letters": 1,
                    "substances": 1,
                    "products": 1,
                    "documents": 1,
                },
                "features": [
                    "PDF Link Collection",
                    "Hierarchical Structure",
                    "Detailed CLI Output",
                    "Version Tracking",
                ],
            },
            "letters": [letter.to_ultra_entry() for letter in self.letters],
        }

    def to_structure_mapping(self, base_path: str) -> Dict[str, object]:
        return {
            "metadata": {
                "created": self.generated_at_utc,
                "basePath": base_path,
                "totalTopLevelDirectories": len(self.letters),
                "structure": "Level 1: Letters/Numbers -> Level 2: Drug Names -> Level 3: Formulations -> Level 4: PDF Files",
            },
            "structure": {letter.letter: letter.to_structure_mapping() for letter in self.letters},
        }


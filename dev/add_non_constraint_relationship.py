"""Augment a mermerd-generated Mermaid ER diagram with fuzzy relationships.

mermerd only draws edges backed by real foreign-key constraints. Plenty of our
links live only in application code (a plain ``*_id`` column with no DB-level
FK). This pass parses the ``.mmd`` file, matches ``*_id`` columns against table
names by a few name variations, and appends the missing edges (prefixed ``F__``
and flagged as non-constraint) so the diagram reflects the real data model.
"""

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class Relationship:
    from_entity: str
    to_entity: str
    key: str
    cardinality: str = "}o--||"


class MermaidParser:
    def __init__(self, content: str):
        self.content = content

    def parse_tables_and_keys(self) -> Dict[str, List[str]]:
        """Parse .mmd file and extract tables with their key (``*id``) fields."""
        table_pattern = r"(\w+)\s*{([^}]+)}"
        tables = re.finditer(table_pattern, self.content)
        result = {}

        for table_match in tables:
            table_name = table_match.group(1)
            table_content = table_match.group(2)
            key_fields = [
                parts[1]
                for parts in (line.split() for line in table_content.split("\n"))
                if len(parts) > 1 and "id" in parts[1]
            ]
            if key_fields:
                result[table_name] = key_fields

        return result

    def parse_existing_relationships(self) -> List[Relationship]:
        """Parse Mermaid ER diagram relationships already present in the file."""
        relationship_pattern = r'(\w+)\s+([}|o\-|]+)\s+(\w+)\s*:\s*"([^"]+)"'
        relationships = []

        for line in self.content.split("\n"):
            if "--" not in line:
                continue

            match = re.match(relationship_pattern, line.strip())
            if match:
                relationships.append(
                    Relationship(
                        from_entity=match.group(1),
                        to_entity=match.group(3),
                        key=match.group(4),
                        cardinality=match.group(2),
                    )
                )

        return relationships


class RelationshipFinder:
    @staticmethod
    def _get_key_variations(key: str) -> List[str]:
        """Generate table-name variations a ``*_id`` column might point at."""
        base_keys = [
            key,
            key.replace("_id", ""),
            key.replace("_ids", ""),
            key.replace("_entity_id", ""),
            key.replace("_entity_ids", ""),
        ]
        return base_keys + [k + "s" for k in base_keys]

    @staticmethod
    def find_missing_relationships(
        tables_and_keys: Dict[str, List[str]], existing_relationships: List[Relationship]
    ) -> List[Relationship]:
        tables = list(tables_and_keys.keys())
        found_relationships: List[Relationship] = []

        for from_table, keys in tables_and_keys.items():
            for key in keys:
                for table in tables:
                    if any(variation == table for variation in RelationshipFinder._get_key_variations(key)):
                        found_relationships.append(Relationship(from_entity=from_table, to_entity=table, key=key))

        existing_set = {(r.from_entity, r.to_entity, r.key) for r in existing_relationships}

        return [r for r in found_relationships if (r.from_entity, r.to_entity, r.key) not in existing_set]


def process_mermaid_file(mmd_file: Path) -> None:
    """Process the Mermaid file and append missing (non-constraint) relationships."""
    if not mmd_file.exists():
        raise FileNotFoundError(f"Mermaid file not found: {mmd_file}")

    content = mmd_file.read_text()
    parser = MermaidParser(content)

    tables_and_keys = parser.parse_tables_and_keys()
    existing_relationships = parser.parse_existing_relationships()

    missing_relationships = RelationshipFinder.find_missing_relationships(tables_and_keys, existing_relationships)

    if missing_relationships:
        with mmd_file.open("a") as f:
            f.write("\n    %% Following relations don't have constraints and come from fuzzy preprocessing\n")
            for rel in missing_relationships:
                f.write(f'    {rel.from_entity} {rel.cardinality} {rel.to_entity} : "F__{rel.key}"\n')


def main():
    print("Adding non-constraint relationships to Mermaid ER diagram")
    parser = argparse.ArgumentParser(description="Add non-constraint relationships to Mermaid ER diagram")
    parser.add_argument("mmd_file", type=Path, help="Path to the Mermaid ER diagram file")
    args = parser.parse_args()

    try:
        process_mermaid_file(args.mmd_file)
    except Exception as e:
        print(f"Error processing file: {e}")
        exit(1)


if __name__ == "__main__":
    main()

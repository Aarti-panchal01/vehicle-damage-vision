import json
import re
import statistics
from pathlib import Path

import tiktoken

from src.rag.document_loader import load_policy_documents


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

ENCODING = tiktoken.get_encoding("cl100k_base")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

MAX_TOKENS = 500
TARGET_TOKENS = 350
MIN_TOKENS = 100
OVERLAP_TOKENS = 50


# ---------------------------------------------------------
# TOKEN UTILITIES
# ---------------------------------------------------------

def tokenize(text):
    return ENCODING.encode(text, disallowed_special=())


def count_tokens(text):
    return len(tokenize(text))


def decode_tokens(tokens):
    return ENCODING.decode(tokens)


# ---------------------------------------------------------
# TEXT CLEANING
# ---------------------------------------------------------

def clean_text(text):
    """Normalize extracted PDF text without destroying structure."""

    text = text.replace("\u00a0", " ")
    text = text.replace("\ufb01", "fi")
    text = text.replace("\ufb02", "fl")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------
# HEADING DETECTION
# ---------------------------------------------------------

def _parse_no_claim_bonus_heading(line):
    """Return a genuine No Claim Bonus heading and any inline body text."""
    match = re.match(
        r"^\s*(?P<number>\d+(?:\.\d+)*[.)]?\s*)?"
        r"No\s+Claim\s+Bonus(?:\s*\(NCB\))?(?P<tail>.*)$",
        line,
        re.IGNORECASE,
    )
    if not match:
        return None

    tail = match.group("tail").strip()
    number = (match.group("number") or "").strip()

    # A bare label, a numbered label followed by a colon and inline text,
    # or the malformed number/label split produced by some PDF extractors.
    if not tail:
        return (f"{number} No Claim Bonus".strip(), "")
    if tail.startswith(":"):
        return (
            f"{number} No Claim Bonus".strip(),
            tail[1:].strip(),
        )
    if ":" in tail:
        descriptor, inline_text = tail.split(":", 1)
        descriptor = descriptor.strip()
        if (
            descriptor
            and len(descriptor.split()) <= 8
            and not re.search(r"\b(is|are|means|shall|will|was|were)\b", descriptor, re.I)
        ):
            return (
                f"{number} No Claim Bonus {descriptor}".strip(),
                inline_text.strip(),
            )
    elif re.match(r"(?:during|for|at|on|in|under|after)\b", tail, re.I):
        descriptor = tail.strip()
        if (
            len(descriptor.split()) <= 8
            and not re.search(r"\b(is|are|means|shall|will|was|were)\b", descriptor, re.I)
        ):
            return (
                f"{number} No Claim Bonus {descriptor}".strip(),
                "",
            )
    if not number and re.fullmatch(r"\d+[.)]?", tail):
        return ("No Claim Bonus", tail)

    return None


def is_heading(line):
    """
    Detect structural insurance-policy headings.

    Deliberately avoids treating ordinary uppercase sentences
    or short PDF header/footer lines as clause headings.
    """

    line = line.strip()

    if _parse_no_claim_bonus_heading(line):
        return True

    # Recognise insurance endorsement headings (IMT and TA).
    if re.match(r"^(?:IMT|TA)\s*\.?\s*\d+\b", line, re.IGNORECASE):
        return len(line) <= 180

    if not line or len(line) > 110:
        return False

    words = line.split()

    if len(words) > 15:
        return False

    # Explicit structural headings.
    structural_patterns = [
        r"^(PART|SECTION|CHAPTER)\s+(?:[IVXLCDM]+|\d+)\b",
        r"^(CLAUSE|ANNEXURE|ANNEX|SCHEDULE)\s+[A-Z0-9IVX.-]+\b",
    ]

    for pattern in structural_patterns:
        if re.match(pattern, line, re.IGNORECASE):
            return True

    # Numbered clauses: 1., 1.1, 2.3.1, etc.
    numbered = re.match(
        r"^(\d+(?:\.\d+){0,3})[.)]?\s+(.+)$",
        line,
    )

    if numbered:
        remainder = numbered.group(2)

        if (
            len(remainder.split()) <= 13
            and not re.search(r"[;:]$", remainder)
            and not re.search(r"\b(is|are|means|shall|will)\b", remainder, re.I)
        ):
            return True

    # Roman numeral and lettered headings.
    if re.match(r"^(?:[IVXLCDM]+|[A-Z])[.)]\s+\S", line):
        return len(words) <= 12

    # Common insurance-policy headings.
    known_headings = {
        "definitions",
        "exclusions",
        "scope of cover",
        "geographical area",
        "conditions",
        "general conditions",
        "special conditions",
        "own damage section",
        "third party liability",
        "liability to third parties",
        "indemnity",
        "claims procedure",
        "claim procedure",
        "cancellation",
        "deductible",
        "deductibles",
        "limitations as to use",
        "no claim bonus",
        "optional covers",
        "add-on covers",
        "add on covers",
        "claims intimation",
        "claim intimation",
        "claim notification",
        "claims procedure",
        "claim procedure",
        "insured's declared value",
        "personal accident cover",
        "depreciation",
    }

    if line.lower().rstrip(":") in known_headings:
        return True

    if re.search(r"\b(?:add-on|add on)\s+covers?\s*:?$", line, re.IGNORECASE):
        return True

    if re.search(r"\bliability to third parties\b", line, re.IGNORECASE):
        return True

    # Strict uppercase heading detection.
    # Do not apply IGNORECASE to this condition.
    if (
        line == line.upper()
        and any(c.isalpha() for c in line)
        and 2 <= len(words) <= 12
        and not re.search(r"[.;]", line)
    ):
        return True

    return False


# ---------------------------------------------------------
# PARAGRAPH AND SECTION EXTRACTION
# ---------------------------------------------------------

def extract_sections(text):
    """
    Identify headings and group following paragraphs
    into policy sections.
    """

    lines = clean_text(text).splitlines()

    sections = []
    current_heading = "General Policy Text"
    current_content = []

    def save_section():
        content = "\n".join(current_content).strip()

        if content or current_heading != "General Policy Text":
            sections.append({
                "heading": current_heading,
                "text": content,
            })

    for line in lines:
        line = line.strip()

        if not line:
            if current_content and current_content[-1] != "":
                current_content.append("")
            continue

        ncb_heading = _parse_no_claim_bonus_heading(line)
        if ncb_heading:
            save_section()
            current_heading, inline_text = ncb_heading
            current_content = [inline_text] if inline_text else []
        elif is_heading(line):
            save_section()

            current_heading = line
            current_content = []
        else:
            current_content.append(line)

    save_section()

    return sections


# ---------------------------------------------------------
# SAFE TEXT SPLITTING
# ---------------------------------------------------------

def split_long_paragraph(text, max_tokens):
    """Split oversized paragraphs at sentence boundaries."""

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    pieces = []
    current = []

    for sentence in sentences:
        if count_tokens(sentence) > max_tokens:
            if current:
                pieces.append(" ".join(current))
                current = []

            tokens = tokenize(sentence)

            for start in range(0, len(tokens), max_tokens):
                part = decode_tokens(tokens[start:start + max_tokens])
                if part.strip():
                    pieces.append(part.strip())

            continue

        candidate = " ".join(current + [sentence])

        if count_tokens(candidate) <= max_tokens:
            current.append(sentence)
        else:
            if current:
                pieces.append(" ".join(current))
            current = [sentence]

    if current:
        pieces.append(" ".join(current))

    return pieces


def split_section(section, max_tokens=MAX_TOKENS):
    """
    Split an oversized section while preserving its heading
    and paragraph boundaries wherever possible.
    """

    heading = section["heading"]
    text = section["text"]

    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", text)
        if p.strip()
    ]

    heading_tokens = count_tokens(heading)
    content_limit = max_tokens - heading_tokens - 5

    if content_limit < 50:
        content_limit = max_tokens - 5

    pieces = []
    current = []

    for paragraph in paragraphs:
        paragraph_parts = (
            [paragraph]
            if count_tokens(paragraph) <= content_limit
            else split_long_paragraph(paragraph, content_limit)
        )

        for part in paragraph_parts:
            candidate = "\n\n".join(current + [part])

            if count_tokens(candidate) <= content_limit:
                current.append(part)
            else:
                if current:
                    pieces.append("\n\n".join(current))

                current = [part]

    if current:
        pieces.append("\n\n".join(current))

    return [
        {
            "heading": heading,
            "text": piece,
        }
        for piece in pieces
    ]


# ---------------------------------------------------------
# SECTION PACKING
# ---------------------------------------------------------


def pack_sections(sections):
    """Pack sections while isolating General Exceptions boundaries."""
    prepared = []
    for section in sections:
        if section["text"].strip():
            prepared.extend(split_section(section))
        else:
            prepared.append(section)

    chunks = []
    current = []
    current_tokens = 0
    current_group = None

    for section in prepared:
        rendered = "{}\n{}".format(
            section["heading"], section["text"]
        )
        size = count_tokens(rendered)

        if size > MAX_TOKENS:
            raise ValueError("Section exceeds maximum chunk size.")

        heading = section["heading"].strip().casefold().rstrip(":")
        is_boundary = re.match(r"^general exceptions?\b", heading) is not None
        ncb_boundary = _parse_no_claim_bonus_heading(section["heading"]) is not None
        group = _heading_pack_group(section["heading"])

        if not section["text"].strip():
            if current:
                chunks.append(current)
                current = []
                current_tokens = 0
            current_group = None
            chunks.append([rendered])
            continue

        if is_boundary or ncb_boundary:
            if current:
                chunks.append(current)
                current = []
                current_tokens = 0
            current_group = None
            chunks.append([rendered])
            continue

        if current and group != current_group and (
            group is not None or current_group is not None
        ):
            chunks.append(current)
            current = []
            current_tokens = 0
            current_group = None

        if current and current_tokens + size > TARGET_TOKENS:
            chunks.append(current)
            current = []
            current_tokens = 0

        if not current:
            current_group = group

        current.append(rendered)
        current_tokens += size

    if current:
        chunks.append(current)

    return ["\n\n".join(chunk) for chunk in chunks]



# ---------------------------------------------------------
# METADATA AND CHUNK CREATION
# ---------------------------------------------------------

def create_chunk(text, metadata, strategy, index, headings=None):
    text = text.strip()

    chunk_metadata = metadata.copy()

    page = metadata.get("page", "unknown")

    chunk_metadata.update({
        "chunk_id": (
            f"{metadata['file_name']}"
            f"::page-{page}"
            f"::{strategy}"
            f"::{index}"
        ),
        "chunk_index": index,
        "chunking_strategy": strategy,
        "token_count": count_tokens(text),
        "headings": headings or [],
    })

    return {
        "text": text,
        "metadata": chunk_metadata,
    }


# ---------------------------------------------------------
# STRATEGY 1: FIXED SIZE
# ---------------------------------------------------------

def fixed_size_chunks(
    documents,
    chunk_size=MAX_TOKENS,
    overlap=OVERLAP_TOKENS,
):
    results = []
    active_scope_by_file = {}

    if overlap >= chunk_size:
        raise ValueError("Overlap must be smaller than chunk size.")

    for document in documents:
        text = clean_text(document["text"])

        if not text:
            continue

        metadata = document["metadata"]
        file_name = metadata["file_name"]
        scope, title = active_scope_by_file.get(
            file_name, ("general", "General Policy Text")
        )
        regulatory = metadata.get("document_category") == "regulation"

        tokens = tokenize(text)
        start = 0
        index = 0

        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            piece = decode_tokens(tokens[start:end]).strip()

            # Decoding and re-encoding a token slice can change token
            # boundaries. Keep the stored text within the requested limit.
            while end > start and count_tokens(piece) > chunk_size:
                end -= 1
                piece = decode_tokens(tokens[start:end]).strip()

            sections = extract_sections(piece)
            headings = [section["heading"] for section in sections]
            for heading in headings:
                if regulatory:
                    label = _heading_label(heading)
                    if label and label.casefold() != "general policy text":
                        title = label
                    scope = "regulatory"
                else:
                    scope, title = classify_policy_scope(heading, scope, title)

            chunk = create_chunk(
                piece,
                metadata,
                "fixed_size",
                index,
                headings,
            )
            chunk["metadata"]["policy_scope"] = scope
            chunk["metadata"]["policy_section"] = title
            results.append(chunk)

            if end >= len(tokens):
                break

            next_start = max(start + 1, end - overlap)
            start = next_start
            index += 1

        active_scope_by_file[file_name] = (scope, title)

    return results


# ---------------------------------------------------------
# STRATEGY 2: HEADING-AWARE CHUNKING
# ---------------------------------------------------------

def _heading_label(line):
    """Normalize the label portion of a heading, without reading its body."""
    label = re.sub(r"\s+", " ", line.strip())
    label = label.replace("–", "-").replace("—", "-")
    label = re.sub(
        r"^(?:\d+(?:\.\d+)*[.)]?|[a-z][.)])\s*",
        "",
        label,
        flags=re.IGNORECASE,
    )
    return label.strip().lstrip("-: ").rstrip(":").strip()


def _heading_pack_group(heading):
    """Return a packing boundary for headings that need their own scope."""
    normalized = _heading_label(heading).casefold()
    if re.match(r"^general exceptions?\b", normalized):
        return ("general", "General Exceptions")
    if _parse_no_claim_bonus_heading(heading):
        return ("general", "No Claim Bonus")

    scope, title = classify_policy_scope(heading)
    if scope != "general" or title != "General Policy Text":
        return (scope, title)
    return None


def classify_policy_scope(
    text,
    current_scope="general",
    current_title="General Policy Text",
):
    """Classify from the leading section heading, never from body mentions."""
    heading = next(
        (line.strip() for line in text.splitlines() if line.strip()),
        "",
    )
    label = _heading_label(heading)
    normalized = label.casefold()

    if re.match(r"^general exceptions?\b", normalized):
        return "general", "General Exceptions"

    if _parse_no_claim_bonus_heading(heading):
        return "general", "No Claim Bonus"

    if re.match(r"^section\s+i\b", normalized) or normalized == "own damage section":
        return "own_damage", "Section I - Loss of or Damage to the Vehicle Insured"
    if re.match(r"^section\s+ii\b", normalized) or normalized in (
        "third party liability",
        "liability to third parties",
    ) or re.search(r"\bliability to third parties\b", normalized):
        return "third_party", "Section II - Liability to Third Parties"
    if re.match(r"^section\s+iii\b", normalized):
        return "personal_accident", "Section III - Personal Accident"

    endorsement = re.match(r"^imt\s*\.?\s*(\d+)\b", normalized)
    if endorsement:
        number = int(endorsement.group(1))
        if number in (15, 16, 17):
            return "personal_accident", f"Personal Accident Endorsement IMT{number}"
        if number in (11, 19, 22, 26):
            return "own_damage", f"Vehicle Damage Endorsement IMT{number}"
        if number == 24:
            return "add_on", "Electrical/Electronic Fittings Add-on IMT24"
        if number == 25:
            return "add_on", "CNG/LPG Kit Add-on IMT25"
        if number in (20, 28, 29):
            return "third_party", f"Third-Party Liability Endorsement IMT{number}"
        return "general", f"Policy Endorsement IMT{number}"

    if re.match(r"^ta\s*\.?\s*\d+\b", normalized):
        return "add_on", "Policy Add-on"

    if re.search(r"\b(?:optional|add[- ]on)\s+covers?\b", normalized):
        return "add_on", "Policy Add-on"
    if "ncb protect" in normalized:
        return "add_on", "Policy Add-on"

    if (
        normalized.startswith("personal accident")
        or "named person other than paid driver" in normalized
        or "than insured and the paid driver or cleaner" in normalized
        or normalized.endswith("and conductors")
    ):
        return "personal_accident", "Personal Accident"

    if "imported without customs duty" in normalized or "compulsory deductible" in normalized:
        return "own_damage", "Own Damage Endorsement"
    if normalized == "deductible" or normalized == "deductibles":
        return "own_damage", "Deductibles"
    if "reduction in the limit of liability for property damage" in normalized:
        return "third_party", "Third-Party Liability Endorsement"
    if "electrical" in normalized and "electronic fittings" in normalized:
        return "add_on", "Policy Add-on"
    if "cng" in normalized and "lpg kit" in normalized:
        return "add_on", "Policy Add-on"

    if (
        normalized in ("conditions", "general conditions")
        or re.match(r"^[a-z][.)]?\s*conditions\b", normalized)
        or normalized.startswith("general terms and conditions")
        or normalized.startswith("part iv general terms and conditions")
    ):
        return "general", "General Policy Conditions"

    if normalized in (
        "claims intimation",
        "claim intimation",
        "claims procedure",
        "claim procedure",
        "claim notification",
        "survey of loss",
    ):
        return "general", "Claims Procedure"

    if normalized == "definitions":
        return "general", "Definitions"
    if normalized.startswith("grievance redressal") or normalized.startswith(
        "names of ombudsman"
    ):
        return "general", "Grievance Redressal"
    if (
        normalized.startswith("policy wording")
        or normalized.startswith("now this policy witnesseth")
    ):
        return "general", "General Policy Text"

    if normalized.startswith("uin:") or normalized.startswith("(uin:"):
        if current_title == "Policy Add-on":
            return current_scope, current_title
        return "general", "General Policy Text"

    if normalized == "general policy text":
        # No Claim Bonus labels must not leak into an unrelated or unheaded
        # page; General Exceptions may continue across a page break.
        if current_title == "No Claim Bonus":
            return "general", "General Policy Text"
        return current_scope, current_title

    if current_title == "General Exceptions":
        # Numbered or lettered exclusion clauses are part of the same section.
        return "general", "General Exceptions"

    if current_title == "No Claim Bonus":
        return "general", label or "General Policy Text"

    return current_scope, current_title


def _sections_in_piece(piece, sections):
    return [
        section
        for section in sections
        if re.search(
            r"(?:\A|\n\n)" + re.escape(section["heading"]) + r"\n",
            piece,
        )
    ]


def _can_merge_short_chunks(left, right, sections):
    left_sections = _sections_in_piece(left, sections)
    right_sections = _sections_in_piece(right, sections)
    if (
        not any(section["text"].strip() for section in left_sections)
        or not any(section["text"].strip() for section in right_sections)
    ):
        return False

    left_headings = [section["heading"] for section in left_sections]
    right_headings = [section["heading"] for section in right_sections]

    for heading in left_headings + right_headings:
        if re.match(r"^general exceptions?\b", _heading_label(heading).casefold()):
            return False
        if _parse_no_claim_bonus_heading(heading):
            return False

    left_groups = {
        group for group in (_heading_pack_group(h) for h in left_headings)
        if group is not None
    }
    right_groups = {
        group for group in (_heading_pack_group(h) for h in right_headings)
        if group is not None
    }
    return left_groups == right_groups and len(left_groups) <= 1


def clause_aware_chunks(
    documents,
    target_tokens=TARGET_TOKENS,
    max_tokens=MAX_TOKENS,
    min_tokens=MIN_TOKENS,
):
    results = []
    active_scope_by_file = {}

    for document in documents:
        text = clean_text(document["text"])
        if not text:
            continue

        file_name = document["metadata"]["file_name"]
        scope, title = active_scope_by_file.get(
            file_name, ("general", "General Policy Text")
        )

        sections = extract_sections(text)
        if not sections:
            sections = [{
                "heading": "General Policy Text",
                "text": text,
            }]

        packed = pack_sections(sections)

        if len(packed) >= 2:
            if (
                count_tokens(packed[-1]) < min_tokens
                and count_tokens(packed[-2] + "\n\n" + packed[-1]) <= max_tokens
                and _can_merge_short_chunks(packed[-2], packed[-1], sections)
            ):
                packed[-2] += "\n\n" + packed[-1]
                packed.pop()

        chunk_index = 0
        for piece in packed:
            if count_tokens(piece) > max_tokens:
                raise ValueError(
                    "Chunk exceeds maximum size: {}".format(file_name)
                )

            included_sections = _sections_in_piece(piece, sections)
            headings = [section["heading"] for section in included_sections]
            regulatory = document["metadata"].get("document_category") == "regulation"
            for heading in headings:
                if regulatory:
                    label = _heading_label(heading)
                    if label and label.casefold() != "general policy text":
                        title = label
                    scope = "regulatory"
                else:
                    scope, title = classify_policy_scope(heading, scope, title)

            if not any(section["text"].strip() for section in included_sections):
                continue

            chunk = create_chunk(
                piece,
                document["metadata"],
                "clause_aware",
                chunk_index,
                headings,
            )
            chunk["metadata"]["policy_scope"] = scope
            chunk["metadata"]["policy_section"] = title
            results.append(chunk)
            chunk_index += 1

        # A heading printed at the bottom of a PDF page has no body on that
        # page. Carry it into the next page's section state instead of losing
        # it and inheriting the preceding section indefinitely.
        trailing_empty_sections = []
        for section in reversed(sections):
            if section["text"].strip():
                break
            trailing_empty_sections.append(section)
        for section in reversed(trailing_empty_sections):
            if document["metadata"].get("document_category") == "regulation":
                scope = "regulatory"
                label = _heading_label(section["heading"])
                if label and label.casefold() != "general policy text":
                    title = label
            else:
                scope, title = classify_policy_scope(section["heading"], scope, title)

        active_scope_by_file[file_name] = (scope, title)

    return results

def save_jsonl(chunks, filename):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / filename

    with open(output_path, "w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(
                json.dumps(chunk, ensure_ascii=False) + "\n"
            )

    return output_path


# ---------------------------------------------------------
# REPORTING
# ---------------------------------------------------------

def print_report(name, chunks):
    print(f"\n{name}")
    print("-" * 45)

    if not chunks:
        print("No chunks generated.")
        return

    sizes = [
        chunk["metadata"]["token_count"]
        for chunk in chunks
    ]

    print("Total chunks:", len(chunks))
    print("Minimum tokens:", min(sizes))
    print("Maximum tokens:", max(sizes))
    print("Average tokens:", round(statistics.mean(sizes), 2))
    print("Median tokens:", statistics.median(sizes))

    print(
        "Chunks below 100 tokens:",
        sum(size < MIN_TOKENS for size in sizes),
    )

    print(
        "Chunks between 100 and 500 tokens:",
        sum(MIN_TOKENS <= size <= MAX_TOKENS for size in sizes),
    )

    print(
        "Chunks above 500 tokens:",
        sum(size > MAX_TOKENS for size in sizes),
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    print("Loading policy documents...", flush=True)

    documents = load_policy_documents()

    print(f"Loaded {len(documents)} PDF pages.", flush=True)

    print("\nGenerating fixed-size chunks...", flush=True)
    fixed = fixed_size_chunks(documents)

    print("Generating heading-aware chunks...", flush=True)
    clause = clause_aware_chunks(documents)

    print_report("FIXED-SIZE CHUNKING", fixed)
    print_report("HEADING-AWARE CHUNKING", clause)

    fixed_path = save_jsonl(
        fixed,
        "fixed_size_chunks.jsonl",
    )

    clause_path = save_jsonl(
        clause,
        "clause_aware_chunks.jsonl",
    )

    print("\nSAVED OUTPUTS")
    print("-" * 45)
    print(fixed_path)
    print(clause_path)

    if clause:
        print("\nSAMPLE HEADING-AWARE CHUNK")
        print("-" * 45)
        print(clause[0]["text"][:1000])
        print("\nMETADATA")
        print(clause[0]["metadata"])

    print("\nChunking completed successfully.")


if __name__ == "__main__":
    main()

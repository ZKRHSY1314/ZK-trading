"""Independently compare extracted XML with immutable DLL PE byte slices.

No target assembly execution, application configuration, network or database.
The resource offsets come from retained ECMA-335 metadata inspection; this
verifier separately maps the PE RVA to file bytes and checks resource lengths.
"""
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ASSEMBLY = Path(r"D:\同花顺软件\同花顺远航版\bin\Hevo.Core.DataModel.dll")
ASSEMBLY_SHA = "5c64b1444f379c54067d0dc37c36cf019ed389b958e75665ae802b657ba17167"
RESOURCE_RVA = 25564


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run():
    raw = ASSEMBLY.read_bytes()
    assert sha(raw) == ASSEMBLY_SHA
    pe = struct.unpack_from("<I", raw, 60)[0]
    assert raw[pe:pe + 4] == b"PE\0\0"
    _, section_count, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", raw, pe + 4)
    sections = [struct.unpack_from("<8sIIIIIIHHI", raw, pe + 24 + optional_size + 40 * index)
                for index in range(section_count)]
    containing = [section for section in sections
                  if section[2] <= RESOURCE_RVA < section[2] + section[3]]
    assert len(containing) == 1
    section = containing[0]
    file_offset = section[4] + RESOURCE_RVA - section[2]
    resources = []
    elements = {}
    for name, offset, expected_length in (("MarketData", 0, 39299),
                                           ("QuoteFieldData", 39303, 351647)):
        length = struct.unpack_from("<I", raw, file_offset + offset)[0]
        assert length == expected_length
        original = raw[file_offset + offset + 4:file_offset + offset + 4 + length]
        target = HERE / f"unit_semantics_static_resource_Hevo.Core.DataModel.Data.{name}.xml"
        assert original == target.read_bytes()
        elements[name] = ET.fromstring(original)
        resources.append({"resource": name, "resource_offset": offset,
                          "length": length, "sha256": sha(original),
                          "extracted_bytes_match_original_dll": True})
    markets = []
    for market in ("USHA", "USZA", "USTM", "USHI", "USZI"):
        entry = elements["MarketData"].find(f"Market[@id='{market}']")
        assert entry is not None and entry.attrib["ShareCountPerUnit"] == "100"
        markets.append({"id": market, "share_count_per_unit": 100,
                        "name": entry.find("Name").attrib["zh-cn"]})
    fields = []
    for field_id in ("13", "19"):
        entry = elements["QuoteFieldData"].find(f"QuoteField[@id='{field_id}']")
        assert entry is not None
        fields.append({"id": int(field_id), "data_type": entry.attrib["data_type"],
                       "name": entry.find("Name").attrib["zh-cn"],
                       "english_name": entry.find("Name").attrib["en-us"],
                       "attributes": dict(entry.attrib)})
    artifact_pins = {path.name: sha(path.read_bytes()) for path in sorted(HERE.glob("unit_semantics_static_*"))
                     if path.is_file() and path.suffix in (".txt", ".xml", ".ps1")}
    return {"assembly": str(ASSEMBLY), "assembly_sha256": ASSEMBLY_SHA,
            "resource_rva": RESOURCE_RVA, "resource_file_offset": file_offset,
            "resources": resources, "markets": markets, "fields": fields,
            "verification_script_sha256": sha(Path(__file__).read_bytes()),
            "artifact_sha256": artifact_pins,
            "static_resource_verification_passed": True,
            "currency_yuan_proved_by_static_evidence_alone": False,
            "dataset_qualification_granted": False, "target_dll_invocations": 0,
            "network_requests": 0, "database_opens": 0}


if __name__ == "__main__":
    result = run()
    with (HERE / "unit_semantics_static_verification.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"static_resource_verification_passed": True, "markets": result["markets"]}, ensure_ascii=True))

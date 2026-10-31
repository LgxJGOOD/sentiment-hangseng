#!/usr/bin/env python3
"""
检测图片是否包含 AI 生成元数据（C2PA / EXIF / XMP）
支持 OpenAI (DALL-E)、Midjourney、Stable Diffusion 等常见签名
"""

import sys
import json
import struct
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any, BinaryIO


@dataclass
class SignatureInfo:
    source: str
    field: str
    value: Any
    confidence: str = "high"


class ImageMetadataExtractor:
    # 常见 AI 生成工具的标识符
    AI_SIGNATURES = {
        "openai": ["openai", "dall-e", "dalle", "gpt-image"],
        "midjourney": ["midjourney", "mj"],
        "stability": ["stability.ai", "stable-diffusion", "sdxl"],
        "adobe": ["adobe", "firefly", "generative-ai"],
        "google": ["google", "imagen"],
        "microsoft": ["microsoft", "designer", "bing-image-creator"],
    }

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.raw_bytes = self.file_path.read_bytes()
        self.results: Dict[str, Any] = {
            "file": str(self.file_path),
            "size": len(self.raw_bytes),
            "format": None,
            "exif": {},
            "xmp": {},
            "c2pa": {},
            "iptc": {},
            "signatures": [],
            "ai_generated": False,
            "ai_confidence": "none",
        }

    # ==================== 格式检测 ====================

    def detect_format(self) -> str:
        header = self.raw_bytes[:16]
        if header[:8] == b"\x89PNG\r\n\x1a\n":
            self.results["format"] = "PNG"
        elif header[:3] == b"\xff\xd8\xff":
            self.results["format"] = "JPEG"
        elif header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            self.results["format"] = "WEBP"
        elif header[:4] == b"GIF8":
            self.results["format"] = "GIF"
        else:
            self.results["format"] = "UNKNOWN"
        return self.results["format"]

    # ==================== PNG 块解析 ====================

    def _read_png_chunks(self) -> List[Dict]:
        """读取 PNG 所有 chunk"""
        chunks = []
        offset = 8  # 跳过 PNG signature
        while offset < len(self.raw_bytes):
            if offset + 8 > len(self.raw_bytes):
                break
            length = struct.unpack(">I", self.raw_bytes[offset:offset+4])[0]
            chunk_type = self.raw_bytes[offset+4:offset+8].decode("ascii", errors="ignore")
            data_start = offset + 8
            data_end = data_start + length
            if data_end + 4 > len(self.raw_bytes):
                break
            data = self.raw_bytes[data_start:data_end]
            crc = struct.unpack(">I", self.raw_bytes[data_end:data_end+4])[0]
            chunks.append({
                "type": chunk_type,
                "length": length,
                "data": data,
                "offset": offset,
            })
            offset = data_end + 4
        return chunks

    def extract_png_metadata(self):
        """提取 PNG 的 tEXt、zTXt、iTXt 块"""
        chunks = self._read_png_chunks()
        for chunk in chunks:
            if chunk["type"] in ("tEXt", "zTXt", "iTXt"):
                try:
                    data = chunk["data"]
                    # tEXt: keyword\0text
                    null_idx = data.find(b"\x00")
                    if null_idx > 0:
                        keyword = data[:null_idx].decode("utf-8", errors="ignore")
                        text = data[null_idx+1:].decode("utf-8", errors="ignore")
                        self.results["exif"][keyword] = text
                        self._check_ai_signature(keyword, text, "PNG tEXt")
                except Exception:
                    pass

    # ==================== JPEG EXIF / XMP ====================

    def extract_jpeg_metadata(self):
        """提取 JPEG 的 APP1 (EXIF/XMP) 和 APP13 (IPTC) 段"""
        offset = 2  # 跳过 SOI
        while offset < len(self.raw_bytes):
            if self.raw_bytes[offset] != 0xFF:
                break
            marker = self.raw_bytes[offset + 1]
            if marker == 0xD9:  # EOI
                break
            if marker in (0xD8, 0x00, 0x01):
                offset += 2
                continue
            if marker in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9):
                offset += 2
                continue

            length = struct.unpack(">H", self.raw_bytes[offset+2:offset+4])[0]
            segment_data = self.raw_bytes[offset+4:offset+2+length]

            # APP1: EXIF 或 XMP
            if marker == 0xE1:
                if segment_data[:6] == b"Exif\x00\x00":
                    self._parse_exif(segment_data[6:])
                elif b"http://ns.adobe.com/xap/" in segment_data[:100]:
                    self._parse_xmp(segment_data)

            # APP13: IPTC / Photoshop
            elif marker == 0xED:
                self._parse_iptc(segment_data)

            offset += 2 + length

    def _parse_exif(self, data: bytes):
        """解析 TIFF 格式的 EXIF 数据"""
        try:
            endian = "<" if data[:2] == b"II" else ">"
            ifd_offset = struct.unpack(endian + "I", data[4:8])[0]
            self._parse_ifd(data, ifd_offset, endian, "EXIF")
        except Exception:
            pass

    def _parse_ifd(self, data: bytes, offset: int, endian: str, prefix: str):
        """解析 IFD 目录"""
        try:
            count = struct.unpack(endian + "H", data[offset:offset+2])[0]
            entry_offset = offset + 2
            for i in range(count):
                entry = entry_offset + i * 12
                if entry + 12 > len(data):
                    break
                tag = struct.unpack(endian + "H", data[entry:entry+2])[0]
                type_id = struct.unpack(endian + "H", data[entry+2:entry+4])[0]
                count_val = struct.unpack(endian + "I", data[entry+4:entry+8])[0]
                value_offset = struct.unpack(endian + "I", data[entry+8:entry+12])[0]

                tag_name = self._exif_tag_name(tag)
                value = self._read_exif_value(data, type_id, count_val, value_offset, endian)
                if value:
                    key = f"{prefix}:{tag_name}"
                    self.results["exif"][key] = str(value)
                    self._check_ai_signature(key, str(value), "EXIF")
        except Exception:
            pass

    def _exif_tag_name(self, tag: int) -> str:
        names = {
            0x010F: "Make", 0x0110: "Model", 0x0131: "Software",
            0x0132: "DateTime", 0x8298: "Copyright", 0x8769: "ExifIFD",
            0x8825: "GPSInfo", 0x9286: "UserComment",
        }
        return names.get(tag, f"Tag0x{tag:04X}")

    def _read_exif_value(self, data: bytes, type_id: int, count: int, offset: int, endian: str) -> Optional[str]:
        try:
            if type_id == 2:  # ASCII
                if count <= 4:
                    val = data[offset:offset+count-1].decode("ascii", errors="ignore")
                else:
                    val = data[offset:offset+count-1].decode("ascii", errors="ignore")
                return val
            elif type_id == 1:  # BYTE
                return str(data[offset]) if count == 1 else None
        except Exception:
            return None
        return None

    def _parse_xmp(self, data: bytes):
        """解析 XMP 元数据"""
        try:
            xmp_str = data.decode("utf-8", errors="ignore")
            self.results["xmp"]["raw_length"] = len(xmp_str)

            # 提取关键字段
            keywords = [
                "dc:creator", "dc:title", "xmp:CreatorTool",
                "xmpMM:DocumentID", "photoshop:Credit",
                "Iptc4xmpExt:DigitalSourceType",
                "plus:ImageCreator", "xmp:MetadataDate",
            ]
            for kw in keywords:
                if kw in xmp_str:
                    start = xmp_str.find(kw)
                    end = min(start + 500, len(xmp_str))
                    snippet = xmp_str[start:end].replace("\n", " ")[:200]
                    self.results["xmp"][kw] = snippet
                    self._check_ai_signature(kw, snippet, "XMP")

            # 检测 C2PA / Content Credentials
            if "c2pa" in xmp_str.lower() or "contentcredentials" in xmp_str.lower():
                self.results["c2pa"]["detected"] = True
                self.results["c2pa"]["in_xmp"] = True
                self._add_signature("C2PA", "XMP嵌入", "Content Credentials 签名", "high")

            # 检测 OpenAI 特定标记
            if "openai" in xmp_str.lower():
                self._add_signature("OpenAI", "XMP", "发现 OpenAI 标记", "high")

        except Exception:
            pass

    def _parse_iptc(self, data: bytes):
        """解析 IPTC / Photoshop 资源块"""
        try:
            # Photoshop Image Resources
            if data[:4] == b"Phot":
                offset = 4 + 2 + 4  # "Photoshop 3.0" + null + 4 bytes
                while offset + 4 < len(data):
                    sig = data[offset:offset+4]
                    if sig != b"8BIM":
                        break
                    resource_id = struct.unpack(">H", data[offset+4:offset+6])[0]
                    name_len = data[offset+6]
                    name_pad = (name_len + 1) & ~1
                    data_len = struct.unpack(">I", data[offset+7+name_pad:offset+11+name_pad])[0]
                    data_pad = (data_len + 1) & ~1
                    resource_data = data[offset+11+name_pad:offset+11+name_pad+data_len]

                    if resource_id == 0x0404:  # IPTC-NAA
                        self._parse_iptc_records(resource_data)
                    elif resource_id == 0x0425:  # XMP
                        self._parse_xmp(resource_data)

                    offset += 11 + name_pad + data_pad
        except Exception:
            pass

    def _parse_iptc_records(self, data: bytes):
        """解析 IPTC 记录"""
        try:
            offset = 0
            while offset + 5 < len(data):
                if data[offset] != 0x1C:
                    offset += 1
                    continue
                record_num = data[offset+1]
                dataset_num = data[offset+2]
                data_len = struct.unpack(">H", data[offset+3:offset+5])[0]
                record_data = data[offset+5:offset+5+data_len].decode("utf-8", errors="ignore")
                key = f"IPTC:{record_num}:{dataset_num}"
                self.results["iptc"][key] = record_data
                self._check_ai_signature(key, record_data, "IPTC")
                offset += 5 + data_len
        except Exception:
            pass

    # ==================== C2PA 深度检测 ====================

    def detect_c2pa_manifest(self):
        """检测嵌入的 C2PA 清单数据（可能存在于 PNG 的 caBX 或 JPEG 的 APP11）"""
        # PNG caBX chunk (C2PA)
        if self.results["format"] == "PNG":
            chunks = self._read_png_chunks()
            for chunk in chunks:
                if chunk["type"] in ("caBX", "cbBx", "c2pa"):
                    self.results["c2pa"]["manifest_chunk"] = chunk["type"]
                    self.results["c2pa"]["manifest_size"] = chunk["length"]
                    self._add_signature("C2PA", f"PNG {chunk['type']} chunk",
                                        "C2PA 清单数据", "very high")

        # JPEG APP11 (C2PA)
        elif self.results["format"] == "JPEG":
            offset = 2
            while offset < len(self.raw_bytes):
                if self.raw_bytes[offset] != 0xFF:
                    break
                marker = self.raw_bytes[offset + 1]
                if marker == 0xD9:
                    break
                if marker in (0xD8, 0x00, 0x01):
                    offset += 2
                    continue
                length = struct.unpack(">H", self.raw_bytes[offset+2:offset+4])[0]
                if marker == 0xEB:  # APP11
                    segment = self.raw_bytes[offset+4:offset+2+length]
                    if b"JUMD" in segment[:20] or b"c2pa" in segment[:20]:
                        self.results["c2pa"]["app11_detected"] = True
                        self._add_signature("C2PA", "JPEG APP11",
                                            "C2PA JUMBF 数据", "very high")
                offset += 2 + length

        # 通用：搜索 C2PA 相关字节模式
        c2pa_markers = [b"C2PA", b"c2pa", b"contentcredentials", b"claim.signature"]
        for marker in c2pa_markers:
            if marker in self.raw_bytes:
                self.results["c2pa"]["byte_pattern"] = marker.decode("ascii", errors="ignore")
                self._add_signature("C2PA", "字节扫描", f"发现 {marker}", "high")
                break

    # ==================== AI 签名检测 ====================

    def _check_ai_signature(self, field: str, value: str, source: str):
        """检查字段值是否包含 AI 生成标记"""
        value_lower = value.lower()
        for ai_name, keywords in self.AI_SIGNATURES.items():
            for kw in keywords:
                if kw in value_lower:
                    self._add_signature(ai_name, field, value[:200], "high")

    def _add_signature(self, source: str, field: str, value: str, confidence: str):
        sig = SignatureInfo(source, field, value, confidence)
        self.results["signatures"].append(asdict(sig))

    def analyze_signatures(self):
        """综合分析签名，判断 AI 生成概率"""
        if not self.results["signatures"]:
            self.results["ai_generated"] = False
            self.results["ai_confidence"] = "none"
            return

        sources = set(s["source"] for s in self.results["signatures"])
        has_c2pa = "C2PA" in sources
        has_openai = "OpenAI" in sources

        if has_c2pa:
            self.results["ai_generated"] = True
            self.results["ai_confidence"] = "very high"
        elif has_openai:
            self.results["ai_generated"] = True
            self.results["ai_confidence"] = "high"
        elif len(sources) >= 2:
            self.results["ai_generated"] = True
            self.results["ai_confidence"] = "medium"
        else:
            self.results["ai_generated"] = True
            self.results["ai_confidence"] = "low"

    # ==================== 主流程 ====================

    def extract_all(self) -> Dict:
        self.detect_format()

        if self.results["format"] == "PNG":
            self.extract_png_metadata()
        elif self.results["format"] == "JPEG":
            self.extract_jpeg_metadata()

        self.detect_c2pa_manifest()
        self.analyze_signatures()

        return self.results


def print_results(results: Dict):
    """格式化输出结果"""
    print("=" * 60)
    print(f"文件: {results['file']}")
    print(f"格式: {results['format']} | 大小: {results['size']} bytes")
    print(f"AI生成判断: {'是' if results['ai_generated'] else '否'} "
          f"(置信度: {results['ai_confidence']})")
    print("=" * 60)

    if results["signatures"]:
        print("\n[检测到的签名]")
        for sig in results["signatures"]:
            print(f"  来源: {sig['source']} | 字段: {sig['field']} | 置信: {sig['confidence']}")
            print(f"  值: {sig['value'][:150]}...")
            print()

    if results["c2pa"]:
        print("[C2PA 信息]")
        print(json.dumps(results["c2pa"], indent=2, ensure_ascii=False))
        print()

    if results["exif"]:
        print("[EXIF 信息]")
        for k, v in list(results["exif"].items())[:20]:
            print(f"  {k}: {v[:100]}")
        print()

    if results["xmp"]:
        print("[XMP 信息]")
        for k, v in results["xmp"].items():
            if k != "raw_length":
                print(f"  {k}: {v[:100]}")
        print()

    if results["iptc"]:
        print("[IPTC 信息]")
        for k, v in list(results["iptc"].items())[:10]:
            print(f"  {k}: {v[:100]}")
        print()

    print("\n[完整 JSON 输出]")
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))


def main():
    if len(sys.argv) < 2:
        print("用法: python detect_ai_image.py <图片路径>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"文件不存在: {file_path}")
        sys.exit(1)

    extractor = ImageMetadataExtractor(file_path)
    results = extractor.extract_all()
    print_results(results)


if __name__ == "__main__":
    main()
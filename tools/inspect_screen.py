"""Lưu cấu trúc màn hình hiện tại và liệt kê các phần tử quanh một dòng chữ.

    python tools/inspect_screen.py                       # chỉ lưu dump.xml
    python tools/inspect_screen.py --near "Tôi đã hiểu"  # liệt kê phần tử ngang hàng dòng chữ
"""
import argparse
import re
import xml.etree.ElementTree as ET

import uiautomator2 as u2


def bounds(n):
    v = re.findall(r"-?\d+", n.get("bounds", ""))
    return tuple(map(int, v)) if len(v) == 4 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="127.0.0.1:7555")
    ap.add_argument("--near", help="chữ cần tìm, ví dụ 'Tôi đã hiểu'")
    ap.add_argument("--out", default="dump.xml")
    args = ap.parse_args()

    d = u2.connect(args.device)
    xml = d.dump_hierarchy(compressed=False)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Đã lưu {args.out} | màn hình {d.window_size()}")
    if not args.near:
        return

    nodes = list(ET.fromstring(xml).iter("node"))
    label = next((n for n in nodes if args.near in n.get("content-desc", "") + n.get("text", "")), None)
    if label is None:
        print(f"KHÔNG thấy chữ '{args.near}'")
        return
    _, ly1, _, ly2 = bounds(label)
    print(f"Dòng chữ: bounds={label.get('bounds')} clickable={label.get('clickable')}\n" + "-" * 70)
    for n in nodes:
        b = bounds(n)
        if not b or b[3] < ly1 - 50 or b[1] > ly2 + 50:
            continue
        desc = (n.get("content-desc", "") or n.get("text", "")).replace("\n", " ")[:40]
        print(f"{n.get('bounds'):<26} {n.get('class', '').split('.')[-1]:<14} "
              f"click={n.get('clickable'):<5} check={n.get('checkable'):<5} '{desc}'")


if __name__ == "__main__":
    main()

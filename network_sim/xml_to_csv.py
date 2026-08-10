"""
Converteste rezultatele FlowMonitor (ns-3), exportate ca XML, intr-un CSV
de forma "packet_id,latency_ms" - formatul citit de sensor/virtual_sensor.py.

FlowMonitor nu salveaza latenta fiecarui pachet individual, ci un HISTOGRAM
de latente per flux (cate pachete au avut latenta intr-un anumit interval,
ex. "intre 10ms si 11ms au fost 4 pachete"). Scriptul "despacheteaza" acest
histogram: pentru fiecare bin cu N pachete, genereaza N randuri in CSV cu
latenta = mijlocul bin-ului (+ un mic zgomot aleator, ca sa nu fie valori
identice) - o aproximare rezonabila si standard a distributiei reale.

Rulare:
    python xml_to_csv.py scenario_5g.xml latency_output.csv
    python xml_to_csv.py scenario_congestionat.xml latency_congestionat.csv
"""

import csv
import random
import sys
import xml.etree.ElementTree as ET


def extract_delay_bins(xml_path: str):
    """
    Parcurge XML-ul FlowMonitor si intoarce o lista de (latenta_ms, count)
    pentru toate bin-urile de latenta, din toate fluxurile gasite.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    bins = []
    flows_found = 0

    for flow in root.iter("Flow"):
        flows_found += 1
        histogram = flow.find("delayHistogram")
        if histogram is None:
            continue
        for bin_el in histogram.findall("bin"):
            start = float(bin_el.get("start", 0))
            width = float(bin_el.get("width", 0))
            count = int(float(bin_el.get("count", 0)))
            if count <= 0:
                continue
            mid_seconds = start + width / 2.0
            bins.append((mid_seconds * 1000.0, count))  # secunde -> ms

    if flows_found == 0:
        raise RuntimeError(
            f"Nu am gasit niciun element <Flow> in {xml_path}. "
            "Verifica ca fisierul a fost generat cu monitor->SerializeToXmlFile(..., true, true)."
        )

    return bins


def bins_to_csv(bins, csv_path: str, jitter_ms: float = 0.3):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["packet_id", "latency_ms"])

        packet_id = 1
        for mid_ms, count in bins:
            for _ in range(count):
                noise = random.uniform(-jitter_ms, jitter_ms)
                latency = max(mid_ms + noise, 0.0)
                writer.writerow([packet_id, round(latency, 3)])
                packet_id += 1

    return packet_id - 1


def main():
    if len(sys.argv) != 3:
        print("Utilizare: python xml_to_csv.py <input.xml> <output.csv>")
        sys.exit(1)

    xml_path, csv_path = sys.argv[1], sys.argv[2]

    bins = extract_delay_bins(xml_path)
    total_packets = sum(count for _, count in bins)

    if total_packets == 0:
        print(f"[!] Niciun pachet cu latenta gasit in {xml_path} (posibil toate au fost pierdute).")
        sys.exit(1)

    written = bins_to_csv(bins, csv_path)
    print(f"[*] Scris {written} randuri (din {len(bins)} bin-uri de latenta) in {csv_path}")


if __name__ == "__main__":
    main()

"""
Converteste rezultatele FlowMonitor (ns-3), exportate ca XML, intr-un CSV
de forma "packet_id,latency_ms" - formatul citit de sensor/virtual_sensor.py.

FlowMonitor nu salveaza latenta fiecarui pachet individual, ci un HISTOGRAM
de latente per flux (cate pachete au avut latenta intr-un anumit interval,
ex. "intre 10ms si 11ms au fost 4 pachete"). Scriptul "despacheteaza" acest
histogram: pentru fiecare bin cu N pachete, genereaza N randuri in CSV cu
latenta = mijlocul bin-ului (+ un mic zgomot aleator, ca sa nu fie valori
identice) - o aproximare rezonabila si standard a distributiei reale.

Daca scenariul foloseste --enableBackgroundTraffic=true (trafic de fond
care satureaza legatura, pentru jitter real de congestie), XML-ul contine
si fluxul de trafic de fond, pe alt port. Scriptul filtreaza dupa portul
de destinatie (implicit 9, portul folosit de senzori in scenariu.cc) ca in
CSV sa ajunga doar latentele pachetelor de senzor, nu si ale traficului de
fond in sine.

Rulare:
    python xml_to_csv.py scenario_5g.xml latency_output.csv
    python xml_to_csv.py scenario_congestionat.xml latency_congestionat.csv --port 9
"""

import argparse
import csv
import random
import xml.etree.ElementTree as ET


def get_sensor_flow_ids(root, port: int):
    """
    Citeste sectiunea <Ipv4FlowClassifier> a XML-ului si intoarce multimea
    flowId-urilor ale caror flux au portul de DESTINATIE `port` - adica
    fluxurile senzorilor, excluzand traficul de fond (alt port).

    Daca nu gaseste clasificatorul (XML mai vechi / alt format), intoarce
    None, caz in care se folosesc TOATE fluxurile (comportament anterior).
    """
    classifier = root.find("Ipv4FlowClassifier")
    if classifier is None:
        return None

    flow_ids = set()
    for flow in classifier.findall("Flow"):
        dest_port = flow.get("destinationPort")
        flow_id = flow.get("flowId")
        if dest_port == str(port) and flow_id is not None:
            flow_ids.add(flow_id)

    return flow_ids


def extract_delay_bins(xml_path: str, port: int = 9):
    """
    Parcurge XML-ul FlowMonitor si intoarce o lista de (latenta_ms, count)
    pentru bin-urile de latenta ale fluxurilor de pe portul `port`.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    sensor_flow_ids = get_sensor_flow_ids(root, port)

    bins = []
    flows_found = 0
    flows_used = 0

    flow_stats = root.find("FlowStats")
    flow_iter = flow_stats.findall("Flow") if flow_stats is not None else root.iter("Flow")

    for flow in flow_iter:
        histogram = flow.find("delayHistogram")
        if histogram is None:
            continue  # elementele <Flow> din Ipv4FlowClassifier nu au histograme

        flows_found += 1

        flow_id = flow.get("flowId")
        if sensor_flow_ids is not None and flow_id not in sensor_flow_ids:
            continue  # flux de pe alt port (ex. trafic de fond) - il ignoram

        flows_used += 1
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
            f"Nu am gasit niciun element <Flow> cu delayHistogram in {xml_path}. "
            "Verifica ca fisierul a fost generat cu monitor->SerializeToXmlFile(..., true, true)."
        )

    if flows_used == 0:
        raise RuntimeError(
            f"Am gasit {flows_found} fluxuri in {xml_path}, dar niciunul pe portul {port}. "
            "Verifica parametrul --port sau portul folosit in scenariul ns-3."
        )

    return bins, flows_used


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_xml", help="Fisierul XML exportat de FlowMonitor")
    parser.add_argument("output_csv", help="Fisierul CSV de scris (packet_id,latency_ms)")
    parser.add_argument(
        "--port",
        type=int,
        default=9,
        help="Portul de destinatie al fluxurilor de senzor de pastrat (implicit 9)",
    )
    args = parser.parse_args()

    bins, flows_used = extract_delay_bins(args.input_xml, args.port)
    total_packets = sum(count for _, count in bins)

    if total_packets == 0:
        print(f"[!] Niciun pachet cu latenta gasit in {args.input_xml} (posibil toate au fost pierdute).")
        raise SystemExit(1)

    written = bins_to_csv(bins, args.output_csv)
    print(
        f"[*] Scris {written} randuri (din {len(bins)} bin-uri, {flows_used} fluxuri pe portul {args.port}) "
        f"in {args.output_csv}"
    )


if __name__ == "__main__":
    main()

/*
 * Scenariu ns-3 pentru proiectul "water-filter-monitor".
 *
 * Topologie:
 *
 *   senzor_0 ─┐
 *   senzor_1 ─┤                      legatura "backhaul"
 *   senzor_2 ─┼── AP (hub) ─────────────────────────────── Server
 *   senzor_3 ─┤   (star, legaturi locale rapide,           (parametrizabila:
 *   senzor_4 ─┤    100Mbps / 1ms, gen WiFi/LAN)              dataRate, delay,
 *   senzor_5 ─┘                                              dimensiune coada)
 *   interferer┘ (opțional, --enableBackgroundTraffic=true)
 *
 * Fiecare senzor trimite pachete UDP mici, la interval fix, catre server
 * pe portul `sensorPort` (simuland raportarile periodice ale senzorului
 * virtual din aplicatie). FlowMonitor inregistreaza statistici de latenta
 * pentru toate fluxurile, exportate la final intr-un fisier XML.
 *
 * Optional (--enableBackgroundTraffic=true), un nod suplimentar
 * ("interferer") trimite continuu trafic UDP de volum mare pe portul
 * `backgroundPort`, saturand legatura backhaul - astfel pachetele
 * senzorilor asteapta variabil in coada, generand jitter real de
 * congestie (nu doar o latenta de propagare constanta).
 *
 * xml_to_csv.py filtreaza dupa `sensorPort`, ca traficul de fond sa nu
 * ajunga in CSV-ul de latente al senzorilor.
 *
 * Rulare tipica (din ~/ns-3, cu ./ns3 run):
 *
 *   # retea rapida, neincarcata ("5G-like")
 *   ./ns3 run "iot_water_filter_scenario --backhaulDataRate=50Mbps --backhaulDelay=10ms --outputXml=scenario_5g.xml"
 *
 *   # retea congestionata, cu trafic de fond care satureaza legatura
 *   ./ns3 run "iot_water_filter_scenario --backhaulDataRate=5Mbps --backhaulDelay=40ms --backhaulQueueSize=15 \
 *       --enableBackgroundTraffic=true --backgroundDataRate=4.5Mbps --outputXml=scenario_congestionat.xml"
 *
 * XML-urile rezultate se convertesc apoi in CSV cu network_sim/xml_to_csv.py.
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/point-to-point-layout-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"

#include <sstream>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("IotWaterFilterScenario");

int
main(int argc, char* argv[])
{
    uint32_t numSensors = 6;
    double simTime = 60.0;
    double packetInterval = 0.2;
    uint32_t packetSize = 100;
    std::string backhaulDataRate = "50Mbps";
    std::string backhaulDelay = "10ms";
    uint32_t backhaulQueueSize = 20;
    std::string outputXml = "flowmon-results.xml";

    bool enableBackgroundTraffic = false;
    std::string backgroundDataRate = "10Mbps";
    uint32_t backgroundPacketSize = 1000;
    double backgroundOnTimeMean = 1.0;  // durata medie a unei rafale (secunde)
    double backgroundOffTimeMean = 0.7; // durata medie a unei pauze intre rafale (secunde)

    uint16_t sensorPort = 9;
    uint16_t backgroundPort = 10;

    CommandLine cmd;
    cmd.AddValue("numSensors", "Numarul de noduri senzor IoT", numSensors);
    cmd.AddValue("simTime", "Durata simularii, in secunde", simTime);
    cmd.AddValue("packetInterval", "Interval intre pachetele unui senzor, in secunde", packetInterval);
    cmd.AddValue("packetSize", "Dimensiunea unui pachet de senzor, in octeti", packetSize);
    cmd.AddValue("backhaulDataRate", "Debitul legaturii AP->Server (ex: 50Mbps)", backhaulDataRate);
    cmd.AddValue("backhaulDelay", "Latenta legaturii AP->Server (ex: 10ms)", backhaulDelay);
    cmd.AddValue("backhaulQueueSize", "Dimensiunea cozii legaturii AP->Server, in pachete", backhaulQueueSize);
    cmd.AddValue("outputXml", "Fisierul XML de iesire pentru statisticile FlowMonitor", outputXml);
    cmd.AddValue("enableBackgroundTraffic",
                 "Activeaza un nod suplimentar care satureaza legatura backhaul (jitter de congestie)",
                 enableBackgroundTraffic);
    cmd.AddValue("backgroundDataRate", "Debitul traficului de fond in timpul unei rafale (ex: 10Mbps)", backgroundDataRate);
    cmd.AddValue("backgroundPacketSize", "Dimensiunea pachetelor de fond, in octeti", backgroundPacketSize);
    cmd.AddValue("backgroundOnTimeMean", "Durata medie a unei rafale de trafic de fond, in secunde", backgroundOnTimeMean);
    cmd.AddValue("backgroundOffTimeMean", "Durata medie a unei pauze intre rafale, in secunde", backgroundOffTimeMean);
    cmd.Parse(argc, argv);

    uint32_t totalSpokes = numSensors + (enableBackgroundTraffic ? 1 : 0);

    // --- Star locala: senzori (+ eventual interferer) -> AP ---
    PointToPointHelper localLink;
    localLink.SetDeviceAttribute("DataRate", StringValue("100Mbps"));
    localLink.SetChannelAttribute("Delay", StringValue("1ms"));

    PointToPointStarHelper star(totalSpokes, localLink);

    InternetStackHelper stack;
    star.InstallStack(stack);
    star.AssignIpv4Addresses(Ipv4AddressHelper("10.1.1.0", "255.255.255.0"));

    // --- Nodul server, conectat la AP prin legatura "backhaul" (bottleneck-ul studiat) ---
    NodeContainer serverNode;
    serverNode.Create(1);
    stack.Install(serverNode);

    PointToPointHelper backhaulLink;
    backhaulLink.SetDeviceAttribute("DataRate", StringValue(backhaulDataRate));
    backhaulLink.SetChannelAttribute("Delay", StringValue(backhaulDelay));
    backhaulLink.SetQueue("ns3::DropTailQueue",
                           "MaxSize",
                           StringValue(std::to_string(backhaulQueueSize) + "p"));

    NetDeviceContainer backhaulDevices = backhaulLink.Install(star.GetHub(), serverNode.Get(0));

    Ipv4AddressHelper backhaulAddrHelper;
    // subretea separata, in afara intervalului 10.1.x.0/24 alocat automat
    // de PointToPointStarHelper pentru fiecare spoke (10.1.1.0/24, 10.1.2.0/24, ...)
    backhaulAddrHelper.SetBase("10.2.1.0", "255.255.255.0");
    Ipv4InterfaceContainer backhaulInterfaces = backhaulAddrHelper.Assign(backhaulDevices);

    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    Ipv4Address serverAddress = backhaulInterfaces.GetAddress(1);

    // --- Aplicatii senzor: fiecare senzor trimite catre server, periodic, pe sensorPort ---
    UdpServerHelper sensorServer(sensorPort);
    ApplicationContainer sensorServerApps = sensorServer.Install(serverNode.Get(0));
    sensorServerApps.Start(Seconds(0.0));
    sensorServerApps.Stop(Seconds(simTime + 1.0));

    uint32_t maxPackets = static_cast<uint32_t>(simTime / packetInterval);

    for (uint32_t i = 0; i < numSensors; ++i)
    {
        UdpClientHelper client(serverAddress, sensorPort);
        client.SetAttribute("MaxPackets", UintegerValue(maxPackets));
        client.SetAttribute("Interval", TimeValue(Seconds(packetInterval)));
        client.SetAttribute("PacketSize", UintegerValue(packetSize));

        ApplicationContainer clientApp = client.Install(star.GetSpokeNode(i));
        // mic decalaj de start intre senzori, sa nu porneasca perfect sincronizat
        double startOffset = static_cast<double>(i) * 0.05;
        clientApp.Start(Seconds(1.0 + startOffset));
        clientApp.Stop(Seconds(simTime));
    }

    // --- Trafic de fond (optional): satureaza legatura backhaul, ca sa apara
    //     jitter real de congestie pe pachetele senzorilor, nu doar delay fix ---
    if (enableBackgroundTraffic)
    {
        PacketSinkHelper bgSink("ns3::UdpSocketFactory",
                                 InetSocketAddress(Ipv4Address::GetAny(), backgroundPort));
        ApplicationContainer bgSinkApp = bgSink.Install(serverNode.Get(0));
        bgSinkApp.Start(Seconds(0.0));
        bgSinkApp.Stop(Seconds(simTime + 1.0));

        OnOffHelper bgClient("ns3::UdpSocketFactory", InetSocketAddress(serverAddress, backgroundPort));
        bgClient.SetAttribute("DataRate", StringValue(backgroundDataRate));
        bgClient.SetAttribute("PacketSize", UintegerValue(backgroundPacketSize));
        // rafale aleatoare (exponential): perioade de trafic intens, alternand
        // cu pauze - produce jitter real (nu doar o coada plina, constanta)
        std::ostringstream onTimeAttr;
        onTimeAttr << "ns3::ExponentialRandomVariable[Mean=" << backgroundOnTimeMean << "]";
        std::ostringstream offTimeAttr;
        offTimeAttr << "ns3::ExponentialRandomVariable[Mean=" << backgroundOffTimeMean << "]";
        bgClient.SetAttribute("OnTime", StringValue(onTimeAttr.str()));
        bgClient.SetAttribute("OffTime", StringValue(offTimeAttr.str()));

        ApplicationContainer bgClientApp = bgClient.Install(star.GetSpokeNode(numSensors));
        bgClientApp.Start(Seconds(0.5));
        bgClientApp.Stop(Seconds(simTime));
    }

    // --- FlowMonitor: statistici de latenta pentru toate fluxurile ---
    FlowMonitorHelper flowmonHelper;
    Ptr<FlowMonitor> monitor = flowmonHelper.InstallAll();
    monitor->SetAttribute("DelayBinWidth", DoubleValue(0.001)); // bin-uri de 1 ms

    Simulator::Stop(Seconds(simTime + 2.0));
    Simulator::Run();

    monitor->CheckForLostPackets();
    monitor->SerializeToXmlFile(outputXml, true, true);

    Simulator::Destroy();

    std::cout << "Simulare terminata. Rezultate scrise in: " << outputXml << std::endl;
    return 0;
}

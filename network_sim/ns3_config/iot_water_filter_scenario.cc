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
 *
 * Fiecare senzor trimite pachete UDP mici, la interval fix, catre server
 * (simuland raportarile periodice ale senzorului virtual din aplicatie).
 * FlowMonitor inregistreaza statistici de latenta pentru toate fluxurile,
 * exportate la final intr-un fisier XML.
 *
 * Rulare tipica (din ~/ns-3, cu ./ns3 run):
 *
 *   ./ns3 run "iot_water_filter_scenario --backhaulDataRate=50Mbps --backhaulDelay=10ms --outputXml=scenario_5g.xml"
 *   ./ns3 run "iot_water_filter_scenario --backhaulDataRate=5Mbps --backhaulDelay=40ms --backhaulQueueSize=10 --outputXml=scenario_congestionat.xml"
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

    CommandLine cmd;
    cmd.AddValue("numSensors", "Numarul de noduri senzor IoT", numSensors);
    cmd.AddValue("simTime", "Durata simularii, in secunde", simTime);
    cmd.AddValue("packetInterval", "Interval intre pachetele unui senzor, in secunde", packetInterval);
    cmd.AddValue("packetSize", "Dimensiunea unui pachet, in octeti", packetSize);
    cmd.AddValue("backhaulDataRate", "Debitul legaturii AP->Server (ex: 50Mbps)", backhaulDataRate);
    cmd.AddValue("backhaulDelay", "Latenta legaturii AP->Server (ex: 10ms)", backhaulDelay);
    cmd.AddValue("backhaulQueueSize", "Dimensiunea cozii legaturii AP->Server, in pachete", backhaulQueueSize);
    cmd.AddValue("outputXml", "Fisierul XML de iesire pentru statisticile FlowMonitor", outputXml);
    cmd.Parse(argc, argv);

    // --- Star locala: senzori -> AP ---
    PointToPointHelper localLink;
    localLink.SetDeviceAttribute("DataRate", StringValue("100Mbps"));
    localLink.SetChannelAttribute("Delay", StringValue("1ms"));

    PointToPointStarHelper star(numSensors, localLink);

    InternetStackHelper stack;
    star.InstallStack(stack);
    star.AssignIpv4Addresses(Ipv4AddressHelper("10.1.1.0", "255.255.255.0"));

    // --- Nodul server, conectat la AP prin legatura "backhaul" ---
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
    // de PointToPointStarHelper pentru fiecare senzor (10.1.1.0/24, 10.1.2.0/24, ...)
    backhaulAddrHelper.SetBase("10.2.1.0", "255.255.255.0");
    Ipv4InterfaceContainer backhaulInterfaces = backhaulAddrHelper.Assign(backhaulDevices);

    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    // --- Aplicatii: fiecare senzor trimite catre server, periodic ---
    uint16_t port = 9;
    UdpServerHelper serverApp(port);
    ApplicationContainer serverApps = serverApp.Install(serverNode.Get(0));
    serverApps.Start(Seconds(0.0));
    serverApps.Stop(Seconds(simTime + 1.0));

    uint32_t maxPackets = static_cast<uint32_t>(simTime / packetInterval);
    Ipv4Address serverAddress = backhaulInterfaces.GetAddress(1);

    for (uint32_t i = 0; i < numSensors; ++i)
    {
        UdpClientHelper client(serverAddress, port);
        client.SetAttribute("MaxPackets", UintegerValue(maxPackets));
        client.SetAttribute("Interval", TimeValue(Seconds(packetInterval)));
        client.SetAttribute("PacketSize", UintegerValue(packetSize));

        ApplicationContainer clientApp = client.Install(star.GetSpokeNode(i));
        // mic decalaj de start intre senzori, sa nu porneasca perfect sincronizat
        double startOffset = static_cast<double>(i) * 0.05;
        clientApp.Start(Seconds(1.0 + startOffset));
        clientApp.Stop(Seconds(simTime));
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

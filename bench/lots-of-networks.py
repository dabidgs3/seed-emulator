from seedemu import *
from typing import List, Dict
from ipaddress import IPv4Network
from math import ceil

def createEmulation(asCount: int, asEachIx: int, netEachAs: int, hostEachNet: int, hostService: Service, hostCommands: List[str], hostFiles: List[File]) -> Emulator:
    asNetworkPool = IPv4Network('16.0.0.0/4').subnets(new_prefix = 16)
    linkNetworkPool = IPv4Network('32.0.0.0/4').subnets(new_prefix = 24)
    ixNetworkPool = IPv4Network('100.0.0.0/13').subnets(new_prefix = 24)
    ixCount = ceil(asCount / asEachIx)

    aac = AddressAssignmentConstraint(hostStart = 2, hostEnd = 255, hostStep = 1, routerStart = 1, routerEnd = 2, routerStep = 0)

    assert asCount <= 4096, 'too many ASes.'
    assert ixCount <= 2048, 'too many IXs.'
    assert hostEachNet <= 253, 'too many hosts.'
    assert netEachAs <= 256, 'too many local nets.'

    emu = Emulator()
    emu.addLayer(Routing())
    emu.addLayer(Ibgp())
    emu.addLayer(Ospf())

    base = Base()
    ebgp = Ebgp()

    ases: Dict[int, AutonomousSystem]
    asRouters: Dict[int, List[Router]] = {}

    # create ASes
    for i in range(0, asCount):
        asn = 5000 + i
        asObject = base.createAutonomousSystem(asn)
        
        ases[asn] = asObject
        asRouters[asn] = []

        localNetPool = next(asNetworkPool).subnets(new_prefix = 24)

        # create host networks
        for j in range(0, netEachAs):
            prefix = next(localNetPool)
            netname = 'net{}'.format(j)
            asObject.createNetwork(netname, str(prefix), aac = aac)

            router = asObject.createRouter('router{}'.format(j))
            router.joinNetwork(netname)

            asRouters[asn].append(router)

            # create hosts
            for k in range(0, hostEachNet):
                hostname = 'host{}_{}'.format(j, k)
                host = asObject.createRouter(hostname)
                host.joinNetwork(netname)

                vnode = 'as{}_{}'.format(asn, hostname)
                hostService.install(vnode)
                emu.addBinding(Binding(vnode, action = Action.FIRST, filter = Filter(asn = asn, nodeName = hostname)))

                for cmd in hostCommands:
                    host.appendStartCommand(cmd.format(
                        randomHostIp = 'todo'
                    ))

                for file in hostFiles:
                    path, body = file.get()
                    host.setFile(path, body)
        
        routers = asRouters[asn]

        # link routers        
        for i in range (1, len(routers)):
            linkname = 'link_{}_{}'.format(i - 1, i)
            asObject.createNetwork(linkname, str(next(linkNetworkPool)))
            routers[i - 1].joinNetwork(linkname)
            routers[i].joinNetwork(linkname)

    lastRouter = None
    asnPtr = 5000

    # create and join exchanges
    for ix in range(1, ixCount + 1):
        ixPrefix = next(ixNetworkPool)
        ixHosts = ixPrefix.hosts()
        ixNetName = base.createInternetExchange(ix, str(ixPrefix), rsAddress = str(next(ixHosts))).getPeeringLan().getName()

        if lastRouter != None:
            lastRouter.joinNetwork(ixNetName, str(next(ixHosts)))

        for i in range(0, asEachIx):
            router = asRouters[asnPtr][0]
            router.joinNetwork(ixNetName, str(next(ixHosts)))

            asnPtr += 1
            lastRouter = router


    return emu